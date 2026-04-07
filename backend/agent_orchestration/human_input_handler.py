"""
Human Input Handler
==================

Handles human input pause/resume functionality for conversation orchestration.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from django.utils import timezone
from asgiref.sync import sync_to_async

from users.models import WorkflowExecution, WorkflowExecutionMessage, WorkflowExecutionStatus, HumanInputInteraction

logger = logging.getLogger('conversation_orchestrator')


class HumanInputHandler:
    """
    Handles workflow pause/resume for human input
    """
    
    def __init__(self, workflow_parser, docaware_handler, llm_provider_manager, reflection_handler, websearch_handler=None):
        self.workflow_parser = workflow_parser
        self.docaware_handler = docaware_handler
        self.llm_provider_manager = llm_provider_manager
        self.reflection_handler = reflection_handler
        self.websearch_handler = websearch_handler
    
    async def pause_for_human_input(self, workflow, node, executed_nodes, conversation_history, execution_record):
        """
        Pause workflow execution and prepare human input interface data
        
        This is called when a UserProxyAgent with require_human_input=True is encountered
        """
        node_id = node.get('id')
        node_name = node.get('data', {}).get('name', 'User Proxy')
        node_data = node.get('data', {})
        
        logger.info(f"⏸️ HUMAN INPUT: Pausing workflow at {node_name} ({node_id})")
        
        # CRITICAL FIX: Refresh executed_nodes from database to get latest state
        # This ensures we have outputs from any parallel executions that just completed
        await sync_to_async(execution_record.refresh_from_db)()
        latest_executed_nodes = execution_record.executed_nodes or {}
        
        # Merge with local executed_nodes (local might have newer updates)
        merged_executed_nodes = {**latest_executed_nodes, **executed_nodes}
        logger.info(f"💾 HUMAN INPUT: Refreshed executed_nodes - {len(merged_executed_nodes)} entries (DB: {len(latest_executed_nodes)}, Local: {len(executed_nodes)})")
        
        # Find input sources (connected agents that feed into this UserProxyAgent)
        input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, workflow.graph_json)
        aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, merged_executed_nodes)
        
        logger.info(f"📥 HUMAN INPUT: Found {len(input_sources)} input sources for {node_name}")
        
        # Log which inputs are available/missing
        for input_source in input_sources:
            source_id = input_source.get('source_id')
            source_name = input_source.get('name', source_id)
            if source_id in merged_executed_nodes:
                from agent_orchestration.executed_nodes_codec import plain_executed_output
                _plain = plain_executed_output(merged_executed_nodes[source_id])
                logger.info(f"✅ HUMAN INPUT: Input from {source_name} available ({len(_plain)} chars)")
            else:
                logger.warning(f"⚠️ HUMAN INPUT: Input from {source_name} (node_id: {source_id}) NOT available in executed_nodes")
                logger.warning(f"⚠️ HUMAN INPUT: Available node_ids in executed_nodes: {list(merged_executed_nodes.keys())}")
        
        # Update execution record to paused state
        await sync_to_async(self.update_execution_for_human_input)(
            execution_record, node_id, node_name, aggregated_context
        )
        
        return {
            'status': 'awaiting_human_input',
            'execution_id': execution_record.execution_id,
            'agent_name': node_name,
            'agent_id': node_id,
            'input_context': aggregated_context,
            'conversation_history': conversation_history,
            'message': f'Workflow paused - {node_name} requires human input'
        }
    
    def update_execution_for_human_input(self, execution_record, agent_id, agent_name, context):
        """
        Update execution record to indicate human input required (sync function)
        """
        execution_record.human_input_required = True
        execution_record.awaiting_human_input_agent = agent_name
        execution_record.human_input_agent_id = agent_id
        execution_record.human_input_context = {
            'agent_id': agent_id,
            'input_sources': context['all_inputs'],
            'input_count': context['input_count'],
            'primary_input': context['primary_input']
        }
        execution_record.human_input_requested_at = timezone.now()
        execution_record.save()
        
        logger.info(f"💾 HUMAN INPUT: Updated execution record {execution_record.execution_id} for human input")
    
    async def resume_workflow_with_human_input(self, execution_id: str, human_input: str, user):
        """
        Resume paused workflow with human input
        """
        logger.info(f"▶️ HUMAN INPUT: Resuming workflow {execution_id} with human input")
        
        # Load paused execution
        # First try with human_input_required=True (standard case)
        try:
            execution_record = await sync_to_async(WorkflowExecution.objects.get)(
                execution_id=execution_id,
                human_input_required=True
            )
            logger.info(f"✅ HUMAN INPUT: Found execution {execution_id} with human_input_required=True")
        except WorkflowExecution.DoesNotExist:
            # Fallback: try without the flag (for deployment context edge cases)
            logger.warning(f"⚠️ HUMAN INPUT: Execution {execution_id} not found with human_input_required=True, trying without flag")
            try:
                execution_record = await sync_to_async(WorkflowExecution.objects.get)(
                    execution_id=execution_id
                )
                logger.info(f"✅ HUMAN INPUT: Found execution {execution_id} without human_input_required flag")
                # Verify it's in a valid state for resuming
                if execution_record.status not in [WorkflowExecutionStatus.RUNNING, WorkflowExecutionStatus.PENDING]:
                    raise ValueError(f"Execution {execution_id} is in {execution_record.status} state, cannot resume")
            except WorkflowExecution.DoesNotExist:
                logger.error(f"❌ HUMAN INPUT: Execution {execution_id} not found at all")
                raise
        
        # Record human input interaction
        await sync_to_async(HumanInputInteraction.objects.create)(
            execution=execution_record,
            agent_name=execution_record.awaiting_human_input_agent,
            agent_id=execution_record.human_input_agent_id,
            input_messages=execution_record.human_input_context.get('input_sources', []),
            human_response=human_input,
            conversation_context=execution_record.conversation_history,
            requested_at=execution_record.human_input_requested_at,
            input_sources_count=execution_record.human_input_context.get('input_count', 0),
            workflow_paused_at_sequence=execution_record.total_messages,
            aggregated_input_summary=f"{execution_record.human_input_context.get('input_count', 0)} input sources processed"
        )
        
        # Update execution state
        execution_record.human_input_required = False
        execution_record.human_input_received_at = timezone.now()
        await sync_to_async(execution_record.save)()
        
        logger.info(f"✅ HUMAN INPUT: Recorded interaction and updated execution state")
        
        # Resume workflow execution from where we left off
        return await self.continue_workflow_from_resumed_state(execution_record, human_input)
    
    async def continue_workflow_from_resumed_state(self, execution_record, human_input):
        """
        Continue workflow execution after human input is provided
        """
        logger.info(f"🚀 HUMAN INPUT: Resuming workflow execution for {execution_record.execution_id}")
        
        # Get workflow and rebuild execution state
        workflow = await sync_to_async(lambda: execution_record.workflow)()
        graph_json = await sync_to_async(lambda: workflow.graph_json)()
        project_id = str(await sync_to_async(lambda: workflow.project.project_id)())
        
        # 📚 USERPROXY DOCAWARE INTEGRATION: Check if DocAware is enabled for UserProxyAgent
        user_proxy_agent_id = execution_record.human_input_agent_id
        user_proxy_node = None
        docaware_enabled = False
        
        if user_proxy_agent_id:
            # Find the UserProxyAgent node in the graph
            for node in graph_json.get('nodes', []):
                if node.get('id') == user_proxy_agent_id:
                    user_proxy_node = node
                    node_data = node.get('data', {})
                    docaware_enabled = self.docaware_handler.is_docaware_enabled(node)
                    logger.info(f"📚 USERPROXY DOCAWARE CHECK: UserProxyAgent {execution_record.awaiting_human_input_agent} - DocAware enabled: {docaware_enabled}")
                    break
        
        # Process DocAware if enabled
        processed_human_input = human_input
        if docaware_enabled and user_proxy_node and project_id:
            try:
                logger.info(f"📚 USERPROXY DOCAWARE: Processing human input with DocAware for {execution_record.awaiting_human_input_agent}")
                processed_human_input = await self.process_userproxy_docaware(
                    user_proxy_node, human_input, project_id, execution_record
                )
                logger.info(f"📚 USERPROXY DOCAWARE: DocAware processing completed - result length: {len(processed_human_input)} chars")
            except Exception as e:
                logger.error(f"❌ USERPROXY DOCAWARE: Failed to process with DocAware: {e}")
                import traceback
                logger.error(f"❌ USERPROXY DOCAWARE: Traceback: {traceback.format_exc()}")
                # Fall back to original human input if DocAware processing fails
                processed_human_input = human_input
        
        # Add human input (or DocAware-processed input) to conversation history
        # Format: "AgentName: human_input" for proper conversation flow
        updated_conversation = execution_record.conversation_history + f"\n{execution_record.awaiting_human_input_agent}: {processed_human_input}"
        
        logger.info(f"📝 HUMAN INPUT: Added user input to conversation history: {execution_record.awaiting_human_input_agent}: {processed_human_input[:100]}...")
        
        # CRITICAL FIX: Add human input message to messages array for proper conversation history display
        messages = execution_record.messages_data or []
        
        # Get the next sequence number
        next_sequence = len(messages)
        
        # ROOT CAUSE FIX: Check if UserProxyAgent has outgoing edges to determine if input is routed
        # (graph_json and user_proxy_agent_id already retrieved above for DocAware processing)
        user_proxy_agent_id = execution_record.human_input_agent_id
        outgoing_edges = []
        if user_proxy_agent_id:
            outgoing_edges = self.workflow_parser.find_outgoing_edges_from_node(user_proxy_agent_id, graph_json)
        
        # Add human input message (use processed_human_input which may have been enhanced by DocAware)
        messages.append({
            'sequence': next_sequence,
            'agent_name': execution_record.awaiting_human_input_agent,
            'agent_type': 'UserProxyAgent',
            'content': processed_human_input,
            'message_type': 'human_input',
            'timestamp': timezone.now().isoformat(),
            'response_time_ms': 0,
            'metadata': {
                'input_method': 'reflection_feedback' if execution_record.human_input_context.get('reflection_source') else 'human_input',
                'reflection_source': execution_record.human_input_context.get('reflection_source'),
                'iteration': execution_record.human_input_context.get('iteration'),
                'has_outgoing_edges': len(outgoing_edges) > 0,
                'outgoing_edge_count': len(outgoing_edges),
                'target_agents': [edge['name'] for edge in outgoing_edges] if outgoing_edges else [],
                'docaware_processed': docaware_enabled,
                'original_input_length': len(human_input),
                'processed_input_length': len(processed_human_input)
            }
        })
        
        # Update the execution record with human input in conversation and messages
        execution_record.conversation_history = updated_conversation
        execution_record.messages_data = messages
        await sync_to_async(execution_record.save)()
        
        # Continue workflow execution from the paused state
        try:
            # Check if this is a reflection workflow that needs special handling
            reflection_source = execution_record.human_input_context.get('reflection_source')
            if reflection_source:
                logger.info(f"🔄 WORKFLOW RESUME: This is a reflection workflow, calling reflection handler")
                
                # This is a reflection workflow - call the reflection handler to complete the reflection
                final_response, updated_conversation = await self.reflection_handler.resume_reflection_workflow_execution(
                    execution_record, human_input
                )
                
                logger.info(f"✅ REFLECTION RESUME: Reflection completed with final response length: {len(final_response)} chars")
                
                # CRITICAL FIX: Get reflection_source_id and reflection_source from human_input_context BEFORE clearing it
                # This is needed for accurate position calculation and message preservation
                human_input_context = execution_record.human_input_context or {}
                reflection_source_id = human_input_context.get('reflection_source_id')
                reflection_source = human_input_context.get('reflection_source')  # Store for message preservation check
                user_proxy_agent_id = human_input_context.get('agent_id') or execution_record.human_input_agent_id
                
                # CRITICAL FIX: Refresh execution record from database to get updated executed_nodes
                # But preserve messages_data that was just saved by reflection handler
                messages_data_before_refresh = execution_record.messages_data
                logger.info(f"💾 REFLECTION RESUME: messages_data before refresh has {len(messages_data_before_refresh) if messages_data_before_refresh else 0} messages")
                await sync_to_async(execution_record.refresh_from_db)()
                
                # CRITICAL FIX: Restore messages_data after refresh to preserve reflection response message
                # The refresh might have loaded an older version, so we need to ensure the latest is preserved
                current_messages = execution_record.messages_data or []
                logger.info(f"💾 REFLECTION RESUME: messages_data after refresh has {len(current_messages)} messages")
                
                if messages_data_before_refresh:
                    # Check if reflection response is already in current_messages
                    reflection_message_exists = any(
                        msg.get('message_type') == 'reflection_final' and 
                        msg.get('agent_name') == reflection_source
                        for msg in current_messages
                    )
                    logger.info(f"💾 REFLECTION RESUME: Reflection message exists in current_messages: {reflection_message_exists}")
                    
                    if not reflection_message_exists:
                        # Reflection message is missing, restore from before refresh
                        execution_record.messages_data = messages_data_before_refresh
                        logger.info(f"💾 REFLECTION RESUME: Restored messages_data after refresh to preserve reflection response (restored {len(messages_data_before_refresh)} messages)")
                    elif len(messages_data_before_refresh) > len(current_messages):
                        # Use the longer list (should have reflection message)
                        execution_record.messages_data = messages_data_before_refresh
                        logger.info(f"💾 REFLECTION RESUME: Using messages_data from before refresh (has {len(messages_data_before_refresh)} messages vs {len(current_messages)})")
                    else:
                        logger.info(f"💾 REFLECTION RESUME: messages_data is up to date, no restoration needed")
                
                # CRITICAL FIX: Mark UserProxyAgent as executed after reflection completes
                # This prevents it from being executed again in the main workflow sequence
                executed_nodes = execution_record.executed_nodes or {}
                if user_proxy_agent_id:
                    # Mark UserProxyAgent as executed so it's skipped in main sequence
                    executed_nodes[user_proxy_agent_id] = f"UserProxyAgent processed reflection input: {human_input}"
                    execution_record.executed_nodes = executed_nodes
                    logger.info(f"✅ REFLECTION RESUME: Marked UserProxyAgent {user_proxy_agent_id} as executed after reflection completion")
                
                # CRITICAL FIX: Ensure human input context is cleared after reflection
                # This prevents UserProxyAgent nodes from being incorrectly skipped in the main workflow
                execution_record.awaiting_human_input_agent = ""
                execution_record.human_input_context = {}
                # CRITICAL FIX: Include messages_data in save to ensure reflection response is preserved
                await sync_to_async(execution_record.save)(update_fields=['executed_nodes', 'awaiting_human_input_agent', 'human_input_context', 'messages_data'])
                logger.info(f"🧹 REFLECTION RESUME: Cleared human input context and marked UserProxyAgent as executed, preserved messages_data")
                
                # CRITICAL FIX: Check if there are remaining agents in the execution sequence
                workflow = await sync_to_async(lambda: execution_record.workflow)()
                graph_json = await sync_to_async(lambda: workflow.graph_json)()
                execution_sequence = self.workflow_parser.parse_workflow_graph(graph_json)
                
                # Find current position in execution sequence based on executed nodes
                # CRITICAL FIX: Read executed_nodes AFTER refresh to get the updated reflection response
                executed_nodes = execution_record.executed_nodes or {}
                logger.info(f"📊 REFLECTION RESUME: Loaded executed_nodes with {len(executed_nodes)} entries after reflection")
                
                # CRITICAL FIX: Verify reflection response is in executed_nodes before continuing
                if reflection_source_id:
                    if reflection_source_id not in executed_nodes:
                        logger.error(f"❌ REFLECTION RESUME: Reflection source {reflection_source_id} not in executed_nodes after reflection!")
                        logger.error(f"❌ REFLECTION RESUME: Available nodes: {list(executed_nodes.keys())}")
                        # Wait a bit and refresh
                        await asyncio.sleep(0.5)
                        await sync_to_async(execution_record.refresh_from_db)()
                        executed_nodes = execution_record.executed_nodes or {}
                        if reflection_source_id not in executed_nodes:
                            raise Exception(f"Reflection response for {reflection_source_id} not saved properly")
                    else:
                        logger.info(f"✅ REFLECTION RESUME: Verified reflection source {reflection_source_id} in executed_nodes")
                
                # CRITICAL FIX: Use node_id instead of node_name for accurate position calculation
                # This prevents matching the wrong node when multiple nodes have the same name
                current_position = 0
                
                # CRITICAL FIX: Find position by checking which nodes have all dependencies satisfied
                # This ensures we don't skip nodes that are waiting for reflection responses
                edges = graph_json.get('edges', [])
                dependency_map = {}
                for edge in edges:
                    edge_type = edge.get('type', 'sequential')
                    source_id = edge.get('source')
                    target_id = edge.get('target')
                    target_node = next((n for n in graph_json.get('nodes', []) if n.get('id') == target_id), None)
                    is_user_proxy = (target_node and 
                                    target_node.get('type') == 'UserProxyAgent' and
                                    target_node.get('data', {}).get('require_human_input', True))
                    if edge_type == 'sequential' or (edge_type == 'reflection' and is_user_proxy):
                        if target_id not in dependency_map:
                            dependency_map[target_id] = set()
                        dependency_map[target_id].add(source_id)
                
                # Find first node that has all dependencies satisfied
                for i, node in enumerate(execution_sequence):
                    node_id = node.get('id')
                    node_type = node.get('type')
                    
                    # Skip if already executed
                    if node_type not in ['StartNode', 'EndNode'] and node_id in executed_nodes:
                        continue
                    
                    # Check if all dependencies are satisfied
                    dependencies = dependency_map.get(node_id, set())
                    all_dependencies_satisfied = all(dep_id in executed_nodes for dep_id in dependencies)
                    
                    if all_dependencies_satisfied:
                        current_position = i
                        logger.info(f"📍 REFLECTION RESUME: Found first node with satisfied dependencies: {node.get('data', {}).get('name', node_id)} at position {current_position}")
                        break
                else:
                    # All nodes executed, start from end
                    current_position = len(execution_sequence)
                    logger.info(f"📍 REFLECTION RESUME: All nodes executed, starting from end at position {current_position}")
                
                remaining_agents = execution_sequence[current_position:]
                logger.info(f"🔍 REFLECTION RESUME: Found {len(remaining_agents)} remaining agents after reflection: {[agent.get('data', {}).get('name') for agent in remaining_agents]}")
                
                if remaining_agents:
                    # Continue workflow execution with remaining agents
                    logger.info(f"▶️ REFLECTION RESUME: Continuing workflow execution from position {current_position}")
                    
                    # Import workflow executor to continue execution
                    from .workflow_executor import WorkflowExecutor
                    from .chat_manager import ChatManager
                    
                    # Create chat manager instance (needed for workflow executor)
                    chat_manager = ChatManager(
                        self.llm_provider_manager,
                        self.workflow_parser,
                        self.docaware_handler,
                        self.websearch_handler
                    )
                    
                    # Create workflow executor instance
                    workflow_executor = WorkflowExecutor(
                        self.workflow_parser,
                        self.llm_provider_manager,
                        chat_manager,
                        self.docaware_handler,
                        self,  # human_input_handler
                        self.reflection_handler
                    )
                    
                    # Continue execution from current position
                    continuation_result = await workflow_executor.continue_workflow_execution(
                        workflow, execution_record, execution_sequence, current_position, executed_nodes
                    )
                    
                    return continuation_result
                else:
                    # No remaining agents - mark workflow as completed
                    logger.info(f"🏁 REFLECTION RESUME: No remaining agents, marking workflow as completed")
                    
                    execution_record.status = 'completed'
                    execution_record.end_time = timezone.now()
                    
                    # CRITICAL: Calculate duration_seconds for proper execution time display
                    if execution_record.start_time and execution_record.end_time:
                        duration = (execution_record.end_time - execution_record.start_time).total_seconds()
                        execution_record.duration_seconds = duration
                        logger.info(f"📊 REFLECTION COMPLETE: Calculated duration: {duration:.2f} seconds")
                    
                    execution_record.total_messages = len(execution_record.messages_data or [])
                    execution_record.total_agents_involved = len(set(msg.get('agent_name') for msg in (execution_record.messages_data or []) if msg.get('agent_type') not in ['StartNode', 'EndNode']))
                    execution_record.result_summary = f"Reflection workflow completed: {reflection_source} → {execution_record.awaiting_human_input_agent}"
                    await sync_to_async(execution_record.save)()
                    
                    return {
                        'status': 'success',
                        'message': 'Reflection workflow completed successfully',
                        'execution_id': execution_record.execution_id,
                        'updated_conversation': updated_conversation,
                        'conversation_history': updated_conversation,
                        'workflow_completed': True,
                        'final_response': final_response,
                        'messages': execution_record.messages_data or [],  # Include messages for deployment executor
                        'response': final_response
                    }
            else:
                # This is a regular human input workflow - continue with remaining nodes after UserProxyAgent
                logger.info(f"🔄 WORKFLOW RESUME: Regular human input workflow - continuing execution with remaining nodes")
                
                # CRITICAL FIX: Continue workflow execution from the node after UserProxyAgent
                workflow = await sync_to_async(lambda: execution_record.workflow)()
                graph_json = await sync_to_async(lambda: workflow.graph_json)()
                execution_sequence = self.workflow_parser.parse_workflow_graph(graph_json)
                
                # Get executed nodes from execution record first
                executed_nodes = execution_record.executed_nodes or {}
                
                # Find the position of the UserProxyAgent that just received input
                user_proxy_agent_id = execution_record.human_input_agent_id
                user_proxy_agent_name = execution_record.awaiting_human_input_agent
                current_position = 0
                
                # ROOT CAUSE FIX: Check if UserProxyAgent has outgoing edges in the workflow graph
                # If it has no outgoing edges, the human input should NOT be routed to any agent
                # It should just be logged in conversation history, and workflow should continue normally
                outgoing_edges = []
                if user_proxy_agent_id:
                    outgoing_edges = self.workflow_parser.find_outgoing_edges_from_node(user_proxy_agent_id, graph_json)
                    logger.info(f"🔍 WORKFLOW RESUME: UserProxyAgent {user_proxy_agent_name} has {len(outgoing_edges)} outgoing edges")
                    
                    if len(outgoing_edges) == 0:
                        logger.info(f"⚠️ WORKFLOW RESUME: UserProxyAgent {user_proxy_agent_name} has NO outgoing edges - human input will NOT be routed to any agent")
                        logger.info(f"📝 WORKFLOW RESUME: Human input will be logged in conversation history only")
                    else:
                        target_names = [edge['name'] for edge in outgoing_edges]
                        logger.info(f"✅ WORKFLOW RESUME: UserProxyAgent {user_proxy_agent_name} has outgoing edges to: {target_names}")
                        logger.info(f"📤 WORKFLOW RESUME: Human input will be routed to these target agents")
                
                # CRITICAL FIX: Find position by checking which nodes are already in executed_nodes
                # This ensures we continue from the correct position, even if nodes have the same name
                if user_proxy_agent_id:
                    # Find the UserProxyAgent by node_id
                    for i, node in enumerate(execution_sequence):
                        if node.get('id') == user_proxy_agent_id:
                            current_position = i + 1  # Move to next node after UserProxyAgent
                            logger.info(f"📍 WORKFLOW RESUME: Found UserProxyAgent by node_id at position {i}, continuing from position {current_position}")
                            break
                    else:
                        # UserProxyAgent not found by id, use executed_nodes to find position
                        logger.warning(f"⚠️ WORKFLOW RESUME: UserProxyAgent node_id {user_proxy_agent_id} not found in execution sequence, using executed_nodes to find position")
                        # Find first node that hasn't been executed
                        for i, node in enumerate(execution_sequence):
                            node_id = node.get('id')
                            node_type = node.get('type')
                            if node_type not in ['StartNode', 'EndNode'] and node_id not in executed_nodes:
                                current_position = i
                                logger.info(f"📍 WORKFLOW RESUME: Found first unexecuted node at position {current_position}")
                                break
                        else:
                            # All nodes executed, start from end
                            current_position = len(execution_sequence)
                            logger.info(f"📍 WORKFLOW RESUME: All nodes executed, starting from end at position {current_position}")
                else:
                    # Fallback: Find first node that hasn't been executed
                    logger.info(f"📍 WORKFLOW RESUME: No user_proxy_agent_id found, using executed_nodes to find position")
                    for i, node in enumerate(execution_sequence):
                        node_id = node.get('id')
                        node_type = node.get('type')
                        if node_type not in ['StartNode', 'EndNode'] and node_id not in executed_nodes:
                            current_position = i
                            logger.info(f"📍 WORKFLOW RESUME: Found first unexecuted node {node.get('data', {}).get('name', node_id)} at position {current_position}")
                            break
                    else:
                        # All nodes executed, start from end
                        current_position = len(execution_sequence)
                        logger.info(f"📍 WORKFLOW RESUME: All nodes executed, starting from end at position {current_position}")
                
                # ROOT CAUSE FIX: Add the human input (or DocAware-processed input) to executed_nodes only if UserProxyAgent has outgoing edges
                # If it has no outgoing edges, the human input should just be logged in conversation history
                # and NOT be added to executed_nodes (since no agent will use it as input)
                if user_proxy_agent_id:
                    if len(outgoing_edges) > 0:
                        # UserProxyAgent has outgoing edges - route input to target agents
                        # Use processed_human_input (which may have been enhanced by DocAware)
                        executed_nodes[user_proxy_agent_id] = processed_human_input
                        # CRITICAL FIX: Save executed_nodes to database before continuing workflow
                        # This ensures continue_workflow_execution sees the human input when it refreshes
                        execution_record.executed_nodes = executed_nodes
                        await sync_to_async(execution_record.save)(update_fields=['executed_nodes'])
                        logger.info(f"💾 WORKFLOW RESUME: Saved human input to executed_nodes for UserProxyAgent {user_proxy_agent_name} (node_id: {user_proxy_agent_id}) - will be routed to target agents")
                    else:
                        # UserProxyAgent has NO outgoing edges - human input is standalone, not routed to any agent
                        logger.info(f"📝 WORKFLOW RESUME: UserProxyAgent {user_proxy_agent_name} has no outgoing edges - human input logged in conversation history only, NOT added to executed_nodes")
                        logger.info(f"📝 WORKFLOW RESUME: Workflow will continue with next agent using its normal input sources (not from UserProxyAgent)")
                
                remaining_agents = execution_sequence[current_position:]
                logger.info(f"🔍 WORKFLOW RESUME: Found {len(remaining_agents)} remaining nodes after UserProxyAgent: {[agent.get('data', {}).get('name') for agent in remaining_agents]}")
                
                if remaining_agents:
                    # Continue workflow execution with remaining agents
                    logger.info(f"▶️ WORKFLOW RESUME: Continuing workflow execution from position {current_position}")
                    
                    # Import workflow executor to continue execution
                    from .workflow_executor import WorkflowExecutor
                    from .chat_manager import ChatManager
                    
                    # Create chat manager instance (needed for workflow executor)
                    chat_manager = ChatManager(
                        self.llm_provider_manager,
                        self.workflow_parser,
                        self.docaware_handler,
                        self.websearch_handler
                    )
                    
                    # Create workflow executor instance
                    workflow_executor = WorkflowExecutor(
                        self.workflow_parser,
                        self.llm_provider_manager,
                        chat_manager,
                        self.docaware_handler,
                        self,  # human_input_handler
                        self.reflection_handler
                    )
                    
                    # Continue execution from current position
                    continuation_result = await workflow_executor.continue_workflow_execution(
                        workflow, execution_record, execution_sequence, current_position, executed_nodes
                    )
                    
                    return continuation_result
                else:
                    # No remaining agents - mark workflow as completed
                    logger.info(f"🏁 WORKFLOW RESUME: No remaining agents, marking workflow as completed")
                    
                    execution_record.status = 'completed'
                    execution_record.end_time = timezone.now()
                    
                    # CRITICAL: Calculate duration_seconds for proper execution time display
                    if execution_record.start_time and execution_record.end_time:
                        duration = (execution_record.end_time - execution_record.start_time).total_seconds()
                        execution_record.duration_seconds = duration
                        logger.info(f"📊 WORKFLOW COMPLETE: Calculated duration: {duration:.2f} seconds")
                    
                    execution_record.total_messages = len(execution_record.messages_data or [])
                    
                    # CRITICAL FIX: Calculate total_agents_involved from messages_data
                    agent_names = set()
                    for msg in (execution_record.messages_data or []):
                        agent_type = msg.get('agent_type', '')
                        # Count only actual agents, not system nodes
                        if agent_type not in ['StartNode', 'EndNode']:
                            agent_names.add(msg.get('agent_name'))
                    execution_record.total_agents_involved = len(agent_names)
                    logger.info(f"📊 WORKFLOW COMPLETE: Calculated {len(agent_names)} agents involved: {list(agent_names)}")
                    
                    execution_record.result_summary = f"Human input workflow completed"
                    await sync_to_async(execution_record.save)()
                    
                    return {
                        'status': 'success',
                        'message': 'Human input workflow completed successfully',
                        'execution_id': execution_record.execution_id,
                        'updated_conversation': updated_conversation,
                        'workflow_completed': True
                    }
            
        except Exception as e:
            logger.error(f"❌ WORKFLOW RESUME: Failed to continue workflow: {e}")
            import traceback
            logger.error(f"❌ WORKFLOW RESUME: Traceback: {traceback.format_exc()}")
            return {
                'status': 'partial_success',
                'message': f'Human input recorded but workflow continuation failed: {str(e)}',
                'execution_id': execution_record.execution_id,
                'updated_conversation': updated_conversation,
                'error': str(e)
            }
    
    async def pause_for_human_input_reflection(self, execution_record, target_node, reflection_context, conversation_history):
        """
        Pause workflow execution for human input during cross-agent reflection
        """
        target_name = target_node.get('data', {}).get('name', 'User Proxy Agent')
        
        logger.info(f"👤 REFLECTION HUMAN INPUT: Pausing for human input from {target_name}")
        
        # Log pause for internal tracking but don't add to visible messages_data
        # These workflow pause messages should not appear in execution history
        reflection_source = reflection_context.get('reflection_source', 'Unknown')
        iteration_num = reflection_context.get('iteration', 1)
        
        logger.info(f"📝 REFLECTION HUMAN INPUT: Workflow paused for reflection input from {target_name}")
        logger.info(f"📝 REFLECTION HUMAN INPUT: Reflection source: {reflection_source}, Iteration: {iteration_num}")
        
        # Update execution record for human input during reflection
        execution_record.human_input_required = True
        execution_record.awaiting_human_input_agent = target_name
        execution_record.human_input_agent_id = target_node.get('id')
        execution_record.human_input_context = reflection_context
        execution_record.human_input_requested_at = timezone.now()
        execution_record.conversation_history = conversation_history
        await sync_to_async(execution_record.save)()
        
        logger.info(f"💾 REFLECTION HUMAN INPUT: Updated execution record for reflection human input")

    async def process_userproxy_docaware(self, userproxy_node, human_input, project_id, execution_record):
        """
        Process UserProxy agent human input with DocAware functionality
        Uses human input as the query for document search and then summarizes with LLM
        """
        logger.info(f"📚 USERPROXY DOCAWARE: Processing human input '{human_input[:100]}...' for UserProxy agent")
        
        node_data = userproxy_node.get('data', {})
        
        # Get DocAware configuration from the node
        search_method = node_data.get('search_method', 'hybrid_search')
        search_parameters = node_data.get('search_parameters', {})

        # Get multi-select content filters
        content_filters = node_data.get('content_filters', [])
        
        # Get LLM configuration for summarization
        llm_provider = node_data.get('llm_provider', 'openai')
        llm_model = node_data.get('llm_model', 'gpt-3.5-turbo')
        system_message = node_data.get('system_message', 'You are a helpful assistant that summarizes retrieved documents to answer user questions.')
        temperature = node_data.get('temperature', 0.3)
        max_tokens = node_data.get('max_tokens', 1024)
        
        logger.info(f"📚 USERPROXY DOCAWARE: Configuration - search_method: {search_method}, llm_provider: {llm_provider}")
        
        try:
            # 1. Perform DocAware search using human input as query
            from .docaware import EnhancedDocAwareAgentService, SearchMethod
            
            # Initialize DocAware service with project_id (required parameter)
            def create_docaware_service():
                return EnhancedDocAwareAgentService(project_id)
            
            docaware_service = await sync_to_async(create_docaware_service)()
            
            logger.info(f"📚 USERPROXY DOCAWARE: Performing document search with query: {human_input}")
            
            # Execute the document search using search_documents method
            def perform_search():
                return docaware_service.search_documents(
                    query=human_input,
                    search_method=SearchMethod(search_method),
                    method_parameters=search_parameters,
                    conversation_context=None,
                    content_filters=content_filters
                )
            
            search_results = await sync_to_async(perform_search)()
            
            if not search_results:
                logger.warning(f"⚠️ USERPROXY DOCAWARE: No search results returned")
                return f"I searched for information about '{human_input}' but couldn't find relevant documents."
            
            # Filter out documents with failed extraction status
            valid_results = []
            failed_results = []
            
            for result in search_results:
                content = result.get('content', '')
                # Check if content indicates failed extraction
                if content and ('Extraction Status: FAILED' in content or 
                               'This document could not be processed' in content):
                    failed_results.append(result)
                    logger.warning(f"⚠️ USERPROXY DOCAWARE: Filtering out document with failed extraction: {result.get('metadata', {}).get('source', 'Unknown')}")
                else:
                    valid_results.append(result)
            
            if failed_results:
                logger.warning(f"⚠️ USERPROXY DOCAWARE: Filtered out {len(failed_results)} document(s) with failed extraction status")
            
            if not valid_results:
                logger.error(f"❌ USERPROXY DOCAWARE: All {len(search_results)} search results have failed extraction status!")
                return f"I searched for information about '{human_input}' but all documents have failed extraction status. Please re-upload and re-process the documents."
            
            retrieved_documents = valid_results
            logger.info(f"📚 USERPROXY DOCAWARE: Found {len(retrieved_documents)} valid relevant documents (filtered {len(failed_results)} failed)")
            
            # 2. Format retrieved documents for LLM
            context_text = "\n\n=== RETRIEVED DOCUMENTS ===\n"
            # Use search_limit from parameters, default to 5
            search_limit = search_parameters.get('search_limit', 5)
            limit = min(len(retrieved_documents), search_limit)
            
            for i, doc in enumerate(retrieved_documents[:limit], 1):
                metadata = doc.get('metadata', {})
                source = metadata.get('source', 'Unknown source')
                content = doc.get('content', '')  # Use full content, not truncated
                score = metadata.get('score', 0)
                
                context_text += f"\nDocument {i} (Source: {source}, Relevance: {score:.3f}):\n{content}\n"
            
            context_text += "\n=== END RETRIEVED DOCUMENTS ===\n"
            
            # 3. Create LLM provider for summarization
            agent_config = {
                'llm_provider': llm_provider,
                'llm_model': llm_model,
                'max_tokens': max_tokens,
                'temperature': temperature
            }
            
            llm_provider_instance = self.llm_provider_manager.get_llm_provider(agent_config)
            if not llm_provider_instance:
                logger.error(f"❌ USERPROXY DOCAWARE: Failed to create LLM provider for summarization")
                return f"I found relevant documents about '{human_input}' but couldn't process them due to LLM configuration issues."
            
            # 4. Create prompt for LLM summarization
            summarization_prompt = f"""{system_message}

The user asked: "{human_input}"

I have retrieved the following relevant documents from the project knowledge base:

{context_text}

Please provide a comprehensive and helpful response to the user's question based on the retrieved documents. If the documents don't contain sufficient information to answer the question, please say so clearly.

Response:"""
            
            logger.info(f"📚 USERPROXY DOCAWARE: Generating LLM summary with {llm_provider} model {llm_model}")
            
            # 5. Generate LLM response
            llm_response = await llm_provider_instance.generate_response(
                prompt=summarization_prompt,
                temperature=temperature
            )
            
            if llm_response.error:
                logger.error(f"❌ USERPROXY DOCAWARE: LLM generation failed: {llm_response.error}")
                return f"I found relevant documents about '{human_input}' but encountered an error while processing them."
            
            summary_result = llm_response.text.strip()
            logger.info(f"✅ USERPROXY DOCAWARE: Successfully generated summary - length: {len(summary_result)} chars")
            
            return summary_result
            
        except Exception as e:
            logger.error(f"❌ USERPROXY DOCAWARE: Processing failed: {e}")
            import traceback
            logger.error(f"❌ USERPROXY DOCAWARE: Traceback: {traceback.format_exc()}")
            return f"I attempted to search for information about '{human_input}' but encountered an error during processing."