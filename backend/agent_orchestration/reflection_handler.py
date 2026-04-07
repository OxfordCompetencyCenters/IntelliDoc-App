"""
Reflection Handler
==================

Handles reflection connections and cross-agent reflection for conversation orchestration.
"""

import logging
import asyncio
import time
import traceback
from typing import Dict, List, Any, Optional
from asgiref.sync import sync_to_async
from django.utils import timezone

from users.models import WorkflowExecutionMessage

logger = logging.getLogger(__name__)


def _latest_citations_for_agent(messages: Optional[List[Dict[str, Any]]], agent_name: str) -> List[Any]:
    """
    Walk messages newest-first; return the first non-empty metadata.citations list
    for the given agent (e.g. pre-reflection chat message before reflection_revision).
    """
    if not messages or not agent_name:
        return []
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if m.get("agent_name") != agent_name:
            continue
        meta = m.get("metadata")
        if not isinstance(meta, dict):
            continue
        cites = meta.get("citations")
        if isinstance(cites, list) and len(cites) > 0:
            return list(cites)
    return []

class ReflectionHandler:
    """
    Handles reflection connections and cross-agent reflection for conversation orchestration.
    """
    
    def __init__(self, llm_provider_manager):
        self.llm_provider_manager = llm_provider_manager
        self.human_input_handler = None  # Will be set by orchestrator
    
    def set_human_input_handler(self, human_input_handler):
        """Set the human input handler reference"""
        self.human_input_handler = human_input_handler

    async def handle_reflection_connections(self, agent_node, agent_response, graph_json, llm_provider):
        """
        Handle reflection connections for an agent
        Implements self-review and iteration cycles
        """
        agent_id = agent_node.get('id')
        agent_name = agent_node.get('data', {}).get('name', 'Agent')
        edges = graph_json.get('edges', [])

        # Find reflection connections from this agent
        reflection_connections = []
        for edge in edges:
            if (edge.get('source') == agent_id and
                edge.get('type') == 'reflection'):
                reflection_connections.append(edge)

        if not reflection_connections:
            return agent_response  # No reflection connections

        logger.info(f"🔄 REFLECTION: Found {len(reflection_connections)} reflection connections for {agent_name}")

        # Filter to only self-reflection connections (same agent)
        self_reflection_connections = [conn for conn in reflection_connections
                                     if conn.get('target') == agent_id]
        cross_agent_reflection_connections = [conn for conn in reflection_connections
                                            if conn.get('target') != agent_id]

        logger.info(f"🔄 REFLECTION: Self-reflection connections: {len(self_reflection_connections)}, Cross-agent: {len(cross_agent_reflection_connections)}")
        logger.info(f"🔄 REFLECTION: Cross-agent reflections will be handled separately in workflow execution")

        if not self_reflection_connections:
            return agent_response  # No self-reflection to process

        # Process only self-reflection connections
        current_response = agent_response
        for connection in self_reflection_connections:
            connection_data = connection.get('data', {})
            max_iterations = connection_data.get('max_iterations', 2)
            reflection_prompt = connection_data.get('reflection_prompt',
                'Please review and improve your previous response. Consider if there are any ways to make it better, more accurate, or more helpful.')

            logger.info(f"🔄 REFLECTION: Starting reflection iteration for {agent_name} (max: {max_iterations})")

            # Perform reflection iterations
            for iteration in range(max_iterations - 1):  # -1 because we already have the initial response
                logger.info(f"🔄 REFLECTION: Iteration {iteration + 2}/{max_iterations} for {agent_name}")

                reflection_full_prompt = f"""
Original Response:
{current_response}

{reflection_prompt}

Please provide your improved response:
"""

                # Generate reflected response
                reflected_response = await llm_provider.generate_response(
                    prompt=reflection_full_prompt,
                    temperature=0.5  # Slightly lower temperature for reflection
                )

                if reflected_response.error:
                    logger.error(f"❌ REFLECTION: Error in iteration {iteration + 2}: {reflected_response.error}")
                    break

                current_response = reflected_response.text.strip()
                logger.info(f"✅ REFLECTION: Completed iteration {iteration + 2}/{max_iterations} - response length: {len(current_response)} chars")

        logger.info(f"🎯 SELF-REFLECTION: Completed {len(self_reflection_connections)} self-reflection iterations for {agent_name}")
        return current_response

    async def handle_cross_agent_reflection(self, source_node, source_response, reflection_edge, graph_json, execution_record, conversation_history, deployment_context: Optional[Dict[str, Any]] = None):
        """
        Handle cross-agent reflection where one agent sends a message to another agent for reflection/feedback

        Flow: Source Agent → Target Agent (reflection) → Source Agent (processes reflection) → Continue workflow
        
        Args:
            deployment_context: Optional deployment context to check input_mode for UserProxyAgent
        """
        source_id = source_node.get('id')
        source_name = source_node.get('data', {}).get('name', 'Source Agent')
        target_id = reflection_edge.get('target')

        # Find target node
        target_node = None
        for node in graph_json.get('nodes', []):
            if node.get('id') == target_id:
                target_node = node
                break

        if not target_node:
            logger.error(f"❌ CROSS-AGENT-REFLECTION: Target node {target_id} not found")
            return source_response, conversation_history

        target_name = target_node.get('data', {}).get('name', 'Target Agent')
        target_type = target_node.get('type')

        logger.info(f"🔄 CROSS-AGENT-REFLECTION: {source_name} → {target_name} (reflection)")

        # Get reflection configuration
        connection_data = reflection_edge.get('data', {})
        max_iterations = connection_data.get('max_iterations', 1)
        reflection_prompt = connection_data.get('reflection_prompt',
            f'Please review this message from {source_name} and provide feedback or suggestions:')

        current_conversation = conversation_history
        final_response = source_response
        original_source_response = source_response  # Preserve original for context

        for iteration in range(max_iterations):
            logger.info(f"🔄 CROSS-AGENT-REFLECTION: Iteration {iteration + 1}/{max_iterations}")

            # Step 1: Send message to target agent
            # CRITICAL FIX: Use chat manager to craft proper prompt with agent's system message
            reflection_context = f"""
{reflection_prompt}

Message from {source_name}:
{final_response}

Current conversation context:
{current_conversation[-1000:]}  # Last 1000 chars for context

Please provide your feedback, suggestions, or response:
"""

            # Handle different target agent types
            if target_type == 'UserProxyAgent':
                # Check if UserProxy requires human input
                target_data = target_node.get('data', {})
                if target_data.get('require_human_input', True):
                    # Get input mode (default to 'user' for backward compatibility)
                    input_mode = target_data.get('input_mode', 'user')
                    is_deployment = deployment_context is not None and deployment_context.get('is_deployment', False)
                    
                    logger.info(f"👤 CROSS-AGENT-REFLECTION: UserProxy {target_name} requires human input - input_mode={input_mode}, is_deployment={is_deployment}")
                    logger.info(f"🔍 CROSS-AGENT-REFLECTION: Original source response length: {len(original_source_response)} chars")
                    logger.info(f"🔍 CROSS-AGENT-REFLECTION: Original source response content: {original_source_response[:500]}...")

                    # Prepare context for human input in the format expected by frontend
                    human_input_context = {
                        'agent_id': target_node.get('id'),
                        'input_sources': [
                            {
                                'agent_name': source_name,
                                'agent_type': source_node.get('type', 'Agent'),
                                'content': source_response,
                                'priority': 1,
                                'node_id': source_node.get('id')
                            }
                        ],
                        'input_count': 1,
                        'primary_input': original_source_response,
                        # Reflection-specific context
                        'reflection_source': source_name,
                        'reflection_source_id': source_node.get('id'),  # CRITICAL FIX: Store node_id for accurate position calculation
                        'source_message': original_source_response,
                        'iteration': iteration + 1,
                        'max_iterations': max_iterations,
                        'prompt': f"Please review this message from {source_name} and provide feedback:",
                        # Store input_mode and deployment context for filtering
                        'input_mode': input_mode,
                        'is_deployment': is_deployment
                    }

                    # Pause workflow for human input
                    await self.human_input_handler.pause_for_human_input_reflection(
                        execution_record, target_node, human_input_context, current_conversation
                    )

                    # Check if this is user input mode in deployment context
                    if input_mode == 'user' and is_deployment:
                        # Return special indicator for deployment context
                        return 'AWAITING_DEPLOYMENT_INPUT', current_conversation
                    else:
                        # Return special indicator that we're waiting for human input in reflection (admin UI)
                        return 'AWAITING_REFLECTION_INPUT', current_conversation
                else:
                    # UserProxy without human input - generate automatic response
                    target_response = f"Feedback from {target_name}: This looks good, please proceed."
            else:
                # Handle other agent types (AssistantAgent, etc.) - SHOULD COMPLETE AUTOMATICALLY
                logger.info(f"🤖 CROSS-AGENT-REFLECTION: Processing AssistantAgent {target_name} reflection automatically")
                
                target_data = target_node.get('data', {})
                target_config = {
                    'llm_provider': target_data.get('llm_provider', 'openai'),
                    'llm_model': target_data.get('llm_model', 'gpt-3.5-turbo'),
                    'temperature': target_data.get('temperature', 0.7),
                    'max_tokens': target_data.get('max_tokens', 2048)
                }

                # CRITICAL FIX: Include target agent's system message in reflection prompt
                target_system_message = target_data.get('system_message', target_data.get('prompt', ''))
                if target_system_message:
                    full_target_prompt = f"System: {target_system_message}\n\n{reflection_context}"
                else:
                    full_target_prompt = reflection_context

                # Get LLM provider for target agent
                try:
                    # Try to get project-specific provider first
                    from users.models import IntelliDocProject
                    project = None
                    try:
                        # Safely access workflow and project using sync_to_async with select_related
                        # Use Django's select_related to avoid additional database queries
                        def get_project_from_execution():
                            try:
                                # Refresh the execution record with related workflow and project
                                execution_with_relations = execution_record.__class__.objects.select_related(
                                    'workflow', 'workflow__project'
                                ).get(pk=execution_record.pk)
                                return execution_with_relations.workflow.project
                            except Exception as e:
                                logger.error(f"Error getting project: {e}")
                                return None
                        
                        project = await sync_to_async(get_project_from_execution)()
                        if project:
                            logger.info(f"✅ CROSS-AGENT-REFLECTION: Successfully retrieved project context: {project.name}")
                        else:
                            logger.warning(f"⚠️ CROSS-AGENT-REFLECTION: Could not retrieve project context")
                    except Exception as project_access_error:
                        logger.warning(f"⚠️ CROSS-AGENT-REFLECTION: Could not access project context: {project_access_error}")
                        project = None
                    
                    target_llm = await self.llm_provider_manager.get_llm_provider(target_config, project)
                        
                except Exception as provider_error:
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Provider error for {target_name}: {provider_error}")
                    import traceback
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Provider traceback: {traceback.format_exc()}")
                    target_llm = None

                if not target_llm:
                    # More detailed error logging to help diagnose the issue
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Failed to get LLM provider for {target_name}")
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Target config: {target_config}")
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Project context: {project.name if project else 'None'}")
                    
                    # No fallback - require project-specific API keys
                    provider_type = target_config.get('llm_provider', 'unknown')
                    if not project:
                        target_response = f"Error: No project context available for {target_name}. Cannot access project-specific {provider_type} API key."
                    else:
                        target_response = f"Error: Could not create {provider_type} provider for reflection from {target_name}. Please ensure project-specific {provider_type} API key is configured for project '{project.name}'."
                else:
                    logger.info(f"🤖 CROSS-AGENT-REFLECTION: Generating {target_name} reflection response")
                    target_llm_response = await target_llm.generate_response(
                        prompt=full_target_prompt,
                        temperature=target_config.get('temperature', 0.7)
                    )

                    if target_llm_response.error:
                        logger.error(f"❌ CROSS-AGENT-REFLECTION: Error from {target_name}: {target_llm_response.error}")
                        target_response = f"Error processing reflection from {target_name}"
                    else:
                        target_response = target_llm_response.text.strip()
                        logger.info(f"✅ CROSS-AGENT-REFLECTION: {target_name} generated reflection ({len(target_response)} chars)")

            # Update conversation history
            current_conversation += f"\n{target_name} (Reflection): {target_response}"
            
            # CRITICAL FIX: Save reflection message to messages_data for conversation history
            if execution_record and execution_record.messages_data is not None:
                # Calculate current message sequence - refresh from database to avoid duplicates
                await sync_to_async(execution_record.refresh_from_db)()
                current_messages = execution_record.messages_data or []
                message_sequence = len(current_messages)
                
                # Add reflection message to messages_data
                reflection_message = {
                    'sequence': message_sequence,
                    'agent_name': target_name,
                    'agent_type': target_node.get('type', 'AssistantAgent'),
                    'content': target_response,
                    'message_type': 'reflection_feedback',
                    'timestamp': timezone.now().isoformat(),
                    'response_time_ms': getattr(target_llm_response, 'response_time_ms', 0) if 'target_llm_response' in locals() and hasattr(target_llm_response, 'response_time_ms') else 0,
                    'token_count': getattr(target_llm_response, 'token_count', None) if 'target_llm_response' in locals() and hasattr(target_llm_response, 'token_count') else None,
                    'metadata': {
                        'is_reflection': True,
                        'reflection_source': source_name,
                        'iteration': iteration + 1,
                        'max_iterations': max_iterations,
                        'llm_provider': target_config.get('llm_provider', 'unknown') if 'target_config' in locals() else 'unknown',
                        'llm_model': target_config.get('llm_model', 'unknown') if 'target_config' in locals() else 'unknown',
                        'temperature': target_config.get('temperature', 0.7) if 'target_config' in locals() else 0.7,
                        'cost_estimate': getattr(target_llm_response, 'cost_estimate', None) if 'target_llm_response' in locals() and hasattr(target_llm_response, 'cost_estimate') else None
                    }
                }
                
                current_messages.append(reflection_message)
                logger.info(f"📝 CROSS-AGENT-REFLECTION: Added {target_name} reflection message (sequence {message_sequence})")
                
                # Save immediately
                execution_record.messages_data = current_messages
                await sync_to_async(execution_record.save)()
                logger.info(f"💾 CROSS-AGENT-REFLECTION: Saved {target_name} reflection message to database")

            # Step 2: Send reflection back to source agent for processing
            # CRITICAL FIX: Process reflection from target back to source 
            # For AssistantAgent reflections, always process to get final response
            should_process_source_revision = True
            if target_type == 'UserProxyAgent' and target_data.get('require_human_input', True):
                # For human input reflections, we've already paused - don't process here
                should_process_source_revision = False
            
            if should_process_source_revision:
                source_reflection_prompt = f"""
You previously said:
{final_response}

{target_name} provided this feedback:
{target_response}

Please revise your response based on this feedback:
"""

                # Send reflection back to source agent for processing
                source_data = source_node.get('data', {})
                source_config = {
                    'llm_provider': source_data.get('llm_provider', 'openai'),
                    'llm_model': source_data.get('llm_model', 'gpt-3.5-turbo'),
                    'temperature': source_data.get('temperature', 0.7),
                    'max_tokens': source_data.get('max_tokens', 2048)
                }

                # CRITICAL FIX: Get source LLM provider with proper async handling
                try:
                    # Try to get project-specific provider first  
                    project = None
                    try:
                        # Safely access workflow and project using sync_to_async with select_related
                        def get_project_from_execution():
                            try:
                                # Refresh the execution record with related workflow and project
                                execution_with_relations = execution_record.__class__.objects.select_related(
                                    'workflow', 'workflow__project'
                                ).get(pk=execution_record.pk)
                                return execution_with_relations.workflow.project
                            except Exception as e:
                                logger.error(f"Error getting project for source: {e}")
                                return None
                        
                        project = await sync_to_async(get_project_from_execution)()
                        if project:
                            logger.info(f"✅ CROSS-AGENT-REFLECTION: Successfully retrieved project context for source: {project.name}")
                        else:
                            logger.warning(f"⚠️ CROSS-AGENT-REFLECTION: Could not retrieve project context for source")
                    except Exception as project_access_error:
                        logger.warning(f"⚠️ CROSS-AGENT-REFLECTION: Could not access project context for source: {project_access_error}")
                        project = None
                    
                    source_llm = await self.llm_provider_manager.get_llm_provider(source_config, project)
                        
                except Exception as source_provider_error:
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Source provider error for {source_name}: {source_provider_error}")
                    import traceback
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Source provider traceback: {traceback.format_exc()}")
                    source_llm = None
                
                # Check if source LLM provider was created successfully
                if not source_llm:
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Failed to get source LLM provider for {source_name}")
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Source config: {source_config}")
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Project context: {project.name if project else 'None'}")
                    
                    # No fallback - require project-specific API keys
                    provider_type = source_config.get('llm_provider', 'unknown')
                    if not project:
                        logger.error(f"❌ CROSS-AGENT-REFLECTION: No project context available for {source_name}. Cannot access project-specific {provider_type} API key.")
                    else:
                        logger.error(f"❌ CROSS-AGENT-REFLECTION: Could not create {provider_type} provider for {source_name}. Please ensure project-specific {provider_type} API key is configured for project '{project.name}'.")
                if source_llm:
                    logger.info(f"🔄 CROSS-AGENT-REFLECTION: Generating {source_name} revised response")
                    try:
                        revised_response = await source_llm.generate_response(
                            prompt=source_reflection_prompt,
                            temperature=source_config.get('temperature', 0.7)
                        )

                        if not revised_response.error:
                            final_response = revised_response.text.strip()
                            current_conversation += f"\n{source_name} (Revised): {final_response}"
                            logger.info(f"✅ CROSS-AGENT-REFLECTION: {source_name} revised response based on {target_name} feedback")
                            
                            # CRITICAL FIX: Save revised response to messages_data for conversation history
                            if execution_record and execution_record.messages_data is not None:
                                # Refresh from database to get latest messages and avoid sequence conflicts
                                await sync_to_async(execution_record.refresh_from_db)()
                                current_messages = execution_record.messages_data or []
                                message_sequence = len(current_messages)
                                
                                # Get source config for metadata
                                source_data = source_node.get('data', {})
                                
                                _rev_meta: Dict[str, Any] = {
                                    'is_reflection_revision': True,
                                    'reflection_target': target_name,
                                    'iteration': iteration + 1,
                                    'max_iterations': max_iterations,
                                    'llm_provider': source_data.get('llm_provider', 'unknown'),
                                    'llm_model': source_data.get('llm_model', 'unknown'),
                                    'temperature': source_data.get('temperature', 0.7),
                                    'cost_estimate': getattr(revised_response, 'cost_estimate', None) if hasattr(revised_response, 'cost_estimate') else None,
                                    'based_on_feedback': True,
                                }
                                inherited_cites = _latest_citations_for_agent(current_messages, source_name)
                                if inherited_cites:
                                    _rev_meta['citations'] = inherited_cites
                                    _rev_meta['citations_inherited_from'] = 'pre_reflection_chat'

                                revised_message = {
                                    'sequence': message_sequence,
                                    'agent_name': source_name,
                                    'agent_type': source_node.get('type', 'AssistantAgent'),
                                    'content': final_response,
                                    'message_type': 'reflection_revision',
                                    'timestamp': timezone.now().isoformat(),
                                    'response_time_ms': getattr(revised_response, 'response_time_ms', 0) if hasattr(revised_response, 'response_time_ms') else 0,
                                    'token_count': getattr(revised_response, 'token_count', None) if hasattr(revised_response, 'token_count') else None,
                                    'metadata': _rev_meta,
                                }
                                
                                current_messages.append(revised_message)
                                logger.info(f"📝 CROSS-AGENT-REFLECTION: Added {source_name} revised response (sequence {message_sequence})")
                                
                                execution_record.messages_data = current_messages
                                await sync_to_async(execution_record.save)()
                                logger.info(f"💾 CROSS-AGENT-REFLECTION: Saved {source_name} revised response to database")
                        else:
                            logger.error(f"❌ CROSS-AGENT-REFLECTION: Error in {source_name} revision: {revised_response.error}")
                    except Exception as revision_error:
                        logger.error(f"❌ CROSS-AGENT-REFLECTION: Exception in {source_name} revision: {revision_error}")
                        import traceback
                        logger.error(f"❌ CROSS-AGENT-REFLECTION: Revision traceback: {traceback.format_exc()}")
                else:
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: No LLM provider available for {source_name} revision")
                    logger.error(f"❌ CROSS-AGENT-REFLECTION: Source agent {source_name} cannot process reflection feedback from {target_name}")
                    # Continue with original response since we can't process the reflection
                    logger.warning(f"⚠️ CROSS-AGENT-REFLECTION: Continuing with original response from {source_name} due to provider failure")

        logger.info(f"🎯 CROSS-AGENT-REFLECTION: Completed {max_iterations} iterations between {source_name} and {target_name}")
        logger.info(f"🎯 CROSS-AGENT-REFLECTION: Final response length: {len(final_response)} chars")
        logger.info(f"🎯 CROSS-AGENT-REFLECTION: Target type was: {target_type}")
        
        # CRITICAL: For AssistantAgent reflections, return the final response normally (NOT 'AWAITING_REFLECTION_INPUT')
        # Only UserProxyAgent reflections with human input should return 'AWAITING_REFLECTION_INPUT'
        return final_response, current_conversation

    async def resume_reflection_workflow_execution(self, execution_record, human_input):
        """
        Resume workflow execution after human input during cross-agent reflection
        """
        logger.info(f"🔄 REFLECTION RESUME: Processing reflection human input for {execution_record.execution_id}")

        # Get reflection context
        reflection_context = execution_record.human_input_context
        source_name = reflection_context.get('reflection_source')
        source_message = reflection_context.get('source_message')
        target_name = execution_record.awaiting_human_input_agent

        logger.info(f"🔄 REFLECTION RESUME: {target_name} provided feedback to {source_name}")

        # Update conversation history with human feedback
        updated_conversation = execution_record.conversation_history + f"\n{target_name} (Reflection): {human_input}"

        # Get workflow and graph
        workflow = await sync_to_async(lambda: execution_record.workflow)()
        graph_json = await sync_to_async(lambda: workflow.graph_json)()

        # Find the source node to send reflection back
        source_node = None
        for node in graph_json.get('nodes', []):
            node_name = node.get('data', {}).get('name')
            if node_name == source_name:
                source_node = node
                break

        if not source_node:
            logger.error(f"❌ REFLECTION RESUME: Could not find source node {source_name}")
            # Continue with regular workflow - this method needs to be implemented
            # For now, return the human input as the final response
            return human_input, updated_conversation

        # Send reflection back to source agent for final processing
        source_data = source_node.get('data', {})
        source_config = {
            'llm_provider': source_data.get('llm_provider', 'openai'),
            'llm_model': source_data.get('llm_model', 'gpt-3.5-turbo'),
            'temperature': source_data.get('temperature', 0.7),
            'max_tokens': source_data.get('max_tokens', 2048)
        }

        # Get project context
        try:
            from users.models import IntelliDocProject
            project = None
            try:
                # Safely access workflow and project using sync_to_async with select_related
                def get_project_from_execution():
                    try:
                        execution_with_relations = execution_record.__class__.objects.select_related(
                            'workflow', 'workflow__project'
                        ).get(pk=execution_record.pk)
                        return execution_with_relations.workflow.project
                    except Exception as e:
                        logger.error(f"Error getting project for reflection resume: {e}")
                        return None
                
                project = await sync_to_async(get_project_from_execution)()
                if project:
                    logger.info(f"✅ REFLECTION RESUME: Successfully retrieved project context: {project.name}")
                else:
                    logger.warning(f"⚠️ REFLECTION RESUME: Could not retrieve project context")
            except Exception as project_access_error:
                logger.warning(f"⚠️ REFLECTION RESUME: Could not access project context: {project_access_error}")
                project = None
        except Exception as project_error:
            logger.error(f"❌ REFLECTION RESUME: Error getting project: {project_error}")
            project = None
            
        source_llm = await self.llm_provider_manager.get_llm_provider(source_config, project)
        revised_response = None  # Initialize to track response metadata
        if source_llm:
            source_reflection_prompt = f"""
            You previously said:
{source_message}

{target_name} provided this feedback:
{human_input}

Please provide your final response, taking this feedback into account:
"""

            logger.info(f"🔄 REFLECTION RESUME: Sending feedback back to {source_name} for final processing")
            logger.info(f"🔄 REFLECTION RESUME: Prompt length: {len(source_reflection_prompt)} chars, model: {source_config.get('llm_model')}")

            try:
                llm_start_time = time.time()
                logger.info(f"⏱️ REFLECTION RESUME: Starting LLM call for {source_name} at {time.strftime('%H:%M:%S')}")
                
                revised_response = await source_llm.generate_response(
                    prompt=source_reflection_prompt,
                    temperature=source_config.get('temperature', 0.7)
                )
                
                llm_end_time = time.time()
                llm_duration = llm_end_time - llm_start_time
                logger.info(f"⏱️ REFLECTION RESUME: LLM call completed in {llm_duration:.2f} seconds")

                if not revised_response.error:
                    final_response = revised_response.text.strip()
                    updated_conversation += f"\n{source_name} (Final): {final_response}"
                    logger.info(f"✅ REFLECTION RESUME: {source_name} provided final response based on {target_name} feedback ({len(final_response)} chars)")
                else:
                    logger.error(f"❌ REFLECTION RESUME: Error from {source_name}: {revised_response.error}")
                    final_response = source_message  # Fallback to original
                    revised_response = None  # Clear on error
            except asyncio.TimeoutError as e:
                logger.error(f"❌ REFLECTION RESUME: Timeout waiting for {source_name} response: {e}")
                final_response = source_message  # Fallback to original
                revised_response = None  # Clear on error
            except Exception as e:
                logger.error(f"❌ REFLECTION RESUME: Exception processing {source_name} reflection: {e}")
                logger.error(f"❌ REFLECTION RESUME: Traceback: {traceback.format_exc()}")
                final_response = source_message  # Fallback to original
                revised_response = None  # Clear on error
        else:
            logger.error(f"❌ REFLECTION RESUME: Could not get LLM provider for {source_name}")
            final_response = source_message  # Fallback to original
            revised_response = None  # Clear on error

        # Clear human input requirements
        execution_record.human_input_required = False
        execution_record.awaiting_human_input_agent = ""
        execution_record.human_input_context = {}
        execution_record.conversation_history = updated_conversation

        # Update executed_nodes with the final response from reflection
        executed_nodes = execution_record.executed_nodes or {}
        if source_node:
            source_node_id = source_node.get('id')
            executed_nodes[source_node_id] = final_response
            logger.info(f"💾 REFLECTION RESUME: Updated executed_nodes[{source_node_id}] with final response ({len(final_response)} chars)")
            logger.info(f"💾 REFLECTION RESUME: executed_nodes now contains {len(executed_nodes)} entries: {list(executed_nodes.keys())}")
        execution_record.executed_nodes = executed_nodes
        execution_record.conversation_history = updated_conversation

        # CRITICAL FIX: Save executed_nodes and conversation_history BEFORE adding message
        await sync_to_async(execution_record.save)(update_fields=['executed_nodes', 'conversation_history'])
        logger.info(f"💾 REFLECTION RESUME: Saved executed_nodes and conversation_history for {source_name}")

        # CRITICAL FIX: Add the final reflection response to messages array
        # Refresh from database to get latest messages and avoid sequence conflicts
        await sync_to_async(execution_record.refresh_from_db)()
        # CRITICAL FIX: Restore executed_nodes after refresh (refresh overwrites it)
        execution_record.executed_nodes = executed_nodes
        messages = execution_record.messages_data or []
        
        # Get the next sequence number
        next_sequence = len(messages)

        _final_meta: Dict[str, Any] = {
            'input_method': 'reflection_completion',
            'reflection_target': target_name,
            'based_on_feedback': True,
            'llm_provider': source_config.get('llm_provider'),
            'llm_model': source_config.get('llm_model'),
        }
        inherited_final = _latest_citations_for_agent(messages, source_name)
        if inherited_final:
            _final_meta['citations'] = inherited_final
            _final_meta['citations_inherited_from'] = 'pre_reflection_chat'

        # Add final reflection response message with proper metadata
        messages.append({
            'sequence': next_sequence,
            'agent_name': source_name,
            'agent_type': source_node.get('type', 'Agent') if source_node else 'Agent',
            'content': final_response,
            'message_type': 'reflection_final',
            'timestamp': timezone.now().isoformat(),
            'response_time_ms': getattr(revised_response, 'response_time_ms', 0) if revised_response and hasattr(revised_response, 'response_time_ms') else 0,
            'token_count': getattr(revised_response, 'token_count', None) if revised_response and hasattr(revised_response, 'token_count') else None,
            'metadata': _final_meta,
        })
        
        # CRITICAL FIX: Save messages immediately with executed_nodes
        execution_record.messages_data = messages
        await sync_to_async(execution_record.save)(update_fields=['messages_data', 'executed_nodes'])
        logger.info(f"💾 REFLECTION RESUME: Saved reflection response message for {source_name} (sequence {next_sequence}, {len(final_response)} chars)")
        logger.info(f"💾 REFLECTION RESUME: Total messages in messages_data: {len(messages)}")
        logger.info(f"💾 REFLECTION RESUME: Last message type: {messages[-1].get('message_type') if messages else 'N/A'}, agent: {messages[-1].get('agent_name') if messages else 'N/A'}")

        # Return the final response and updated conversation
        return final_response, updated_conversation

    async def iterate_reflection_workflow(self, execution_record, human_input):
        """
        Handle iteration flow: Send feedback back to source agent for another round of reflection
        """
        logger.info(f"🔄 REFLECTION ITERATE: Processing iteration for {execution_record.execution_id}")

        # Get reflection context
        reflection_context = execution_record.human_input_context
        source_name = reflection_context.get('reflection_source')
        source_message = reflection_context.get('source_message')
        target_name = execution_record.awaiting_human_input_agent

        logger.info(f"🔄 REFLECTION ITERATE: {target_name} providing feedback to {source_name} for iteration")

        # Update conversation history with human feedback
        updated_conversation = execution_record.conversation_history + f"\n{target_name} (Iteration Feedback): {human_input}"

        # CRITICAL: Add human feedback message to messages_data first  
        # Refresh from database to get latest messages and avoid sequence conflicts
        await sync_to_async(execution_record.refresh_from_db)()
        messages = execution_record.messages_data or []
        feedback_sequence = len(messages)
        
        messages.append({
            'sequence': feedback_sequence,
            'agent_name': target_name,
            'agent_type': 'UserProxyAgent',
            'content': human_input,
            'message_type': 'iteration_feedback',
            'timestamp': timezone.now().isoformat(),
            'response_time_ms': 0,
            'metadata': {
                'input_method': 'iteration_feedback',
                'reflection_target': source_name,
                'iteration_cycle': True
            }
        })
        
        logger.info(f"📝 REFLECTION ITERATE: Added human feedback message to sequence {feedback_sequence}")

        # Get workflow and graph
        workflow = await sync_to_async(lambda: execution_record.workflow)()
        graph_json = await sync_to_async(lambda: workflow.graph_json)()

        # Find the source node to send reflection back
        source_node = None
        for node in graph_json.get('nodes', []):
            node_name = node.get('data', {}).get('name')
            if node_name == source_name:
                source_node = node
                break

        if not source_node:
            logger.error(f"❌ REFLECTION ITERATE: Could not find source node {source_name}")
            return human_input, updated_conversation

        # Send feedback back to source agent for revision
        source_data = source_node.get('data', {})
        source_config = {
            'llm_provider': source_data.get('llm_provider', 'openai'),
            'llm_model': source_data.get('llm_model', 'gpt-3.5-turbo'),
            'temperature': source_data.get('temperature', 0.7),
            'max_tokens': source_data.get('max_tokens', 2048)
        }

        # Get project context for LLM provider
        try:
            from users.models import IntelliDocProject
            project = None
            try:
                # Safely access workflow and project using sync_to_async with select_related
                def get_project_from_execution():
                    try:
                        execution_with_relations = execution_record.__class__.objects.select_related(
                            'workflow', 'workflow__project'
                        ).get(pk=execution_record.pk)
                        return execution_with_relations.workflow.project
                    except Exception as e:
                        logger.error(f"Error getting project for reflection iterate: {e}")
                        return None
                
                project = await sync_to_async(get_project_from_execution)()
                if project:
                    logger.info(f"✅ REFLECTION ITERATE: Successfully retrieved project context: {project.name}")
                else:
                    logger.warning(f"⚠️ REFLECTION ITERATE: Could not retrieve project context")
            except Exception as project_access_error:
                logger.warning(f"⚠️ REFLECTION ITERATE: Could not access project context: {project_access_error}")
                project = None
        except Exception as project_error:
            logger.error(f"❌ REFLECTION ITERATE: Error getting project: {project_error}")
            project = None
            
        source_llm = await self.llm_provider_manager.get_llm_provider(source_config, project)
        if source_llm:
            source_iteration_prompt = f"""
            You previously said:
            {source_message}

            {target_name} provided this feedback for iteration:
            {human_input}

            Please revise your response based on this feedback and continue with the task:
            """

            logger.info(f"🔄 REFLECTION ITERATE: Sending iteration feedback back to {source_name}")

            try:
                revised_response = await source_llm.generate_response(
                    prompt=source_iteration_prompt,
                    temperature=source_config.get('temperature', 0.7)
                )

                if not revised_response.error:
                    iteration_response = revised_response.text.strip()
                    updated_conversation += f"\n{source_name} (Iteration): {iteration_response}"
                    logger.info(f"✅ REFLECTION ITERATE: {source_name} provided iteration response")
                    
                    # Update execution record for continued workflow
                    execution_record.conversation_history = updated_conversation
                    
                    # Update executed_nodes with the iteration response
                    executed_nodes = execution_record.executed_nodes or {}
                    executed_nodes[source_node.get('id')] = iteration_response
                    execution_record.executed_nodes = executed_nodes
                    
                    # Clear human input requirements for iteration continuation
                    execution_record.human_input_required = False
                    execution_record.awaiting_human_input_agent = ""
                    execution_record.human_input_context = {}
                    
                    # Add iteration response to messages array (messages already has human feedback)
                    iteration_sequence = len(messages)

                    _iter_meta: Dict[str, Any] = {
                        'input_method': 'reflection_iteration',
                        'iteration_feedback': True,
                        'feedback_from': target_name,
                        'responding_to_sequence': feedback_sequence,
                    }
                    inherited_iter = _latest_citations_for_agent(messages, source_name)
                    if inherited_iter:
                        _iter_meta['citations'] = inherited_iter
                        _iter_meta['citations_inherited_from'] = 'pre_reflection_chat'

                    messages.append({
                        'sequence': iteration_sequence,
                        'agent_name': source_name,
                        'agent_type': source_node.get('type', 'Agent'),
                        'content': iteration_response,
                        'message_type': 'reflection_iteration',
                        'timestamp': timezone.now().isoformat(),
                        'response_time_ms': 0,
                        'metadata': _iter_meta,
                    })
                    
                    logger.info(f"📝 REFLECTION ITERATE: Added iteration response message to sequence {iteration_sequence}")
                    
                    execution_record.messages_data = messages
                    await sync_to_async(execution_record.save)()
                    
                    # Now we need to continue the workflow by sending the iteration response back through the reflection flow
                    # This creates the loop: Source Agent -> UserProxy -> Source Agent (iteration) -> UserProxy (again)
                    logger.info(f"🔄 REFLECTION ITERATE: Sending iteration response back through reflection connection")
                    
                    # Find reflection edge back to UserProxy
                    reflection_edges = []
                    for edge in graph_json.get('edges', []):
                        if (edge.get('source') == source_node.get('id') and
                            edge.get('type') == 'reflection'):
                            reflection_edges.append(edge)
                    
                    if reflection_edges:
                        # Process reflection with iteration response (this will pause at UserProxy again)
                        for reflection_edge in reflection_edges:
                            target_id = reflection_edge.get('target')
                            target_node = None
                            for node in graph_json.get('nodes', []):
                                if node.get('id') == target_id:
                                    target_node = node
                                    break
                            
                            if target_node and target_node.get('type') == 'UserProxyAgent':
                                logger.info(f"🔄 REFLECTION ITERATE: Sending iteration response to {target_node.get('data', {}).get('name')}")
                                
                                # This will create another reflection pause at UserProxy
                                reflection_result, updated_conv = await self.handle_cross_agent_reflection(
                                    source_node, iteration_response, reflection_edge, graph_json, execution_record, updated_conversation
                                )
                                
                                if reflection_result == 'AWAITING_REFLECTION_INPUT':
                                    logger.info(f"🔄 REFLECTION ITERATE: UserProxy awaiting input for next iteration cycle")
                                    return 'AWAITING_REFLECTION_INPUT', updated_conv
                                else:
                                    # Log iteration completion for internal tracking
                                    logger.info(f"📝 REFLECTION ITERATE: Iteration cycle completed - workflow resuming from {source_name}")
                                    return reflection_result, updated_conv
                    
                    # If no reflection edges found, just continue normally
                    logger.info(f"🔄 REFLECTION ITERATE: No reflection edges found, workflow continues normally")
                    return iteration_response, updated_conversation
                else:
                    logger.error(f"❌ REFLECTION ITERATE: Error from {source_name}: {revised_response.error}")
                    return source_message, updated_conversation
            except Exception as e:
                logger.error(f"❌ REFLECTION ITERATE: Exception processing {source_name} iteration: {e}")
                return source_message, updated_conversation
        else:
            logger.error(f"❌ REFLECTION ITERATE: Could not get LLM provider for {source_name}")
            return source_message, updated_conversation