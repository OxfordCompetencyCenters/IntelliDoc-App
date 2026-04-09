"""
Workflow Executor
================

Main workflow execution engine for conversation orchestration.
"""

import logging
import time
import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from django.utils import timezone
from asgiref.sync import sync_to_async

from users.models import WorkflowExecution, WorkflowExecutionMessage, WorkflowExecutionStatus, AgentWorkflow
from llm_eval.providers.base import LLMResponse
from mcp_servers.manager import get_mcp_server_manager

from .executed_nodes_codec import (
    pack_executed_output,
    plain_executed_output,
    format_upstream_citations_block,
)

logger = logging.getLogger('conversation_orchestrator')


class MessageSequenceManager:
    """
    Manages message sequencing to prevent duplicate sequence numbers
    """
    
    def __init__(self, existing_messages=None):
        self.messages = existing_messages or []
        self.sequence_counter = len(self.messages)
    
    def add_message(self, agent_name, agent_type, content, message_type, **kwargs):
        """Add message with auto-incrementing sequence number"""
        message = {
            'sequence': self.sequence_counter,
            'agent_name': agent_name,
            'agent_type': agent_type,
            'content': content,
            'message_type': message_type,
            'timestamp': timezone.now().isoformat(),
            'response_time_ms': kwargs.get('response_time_ms', 0),
            'token_count': kwargs.get('token_count', None),
            'metadata': kwargs.get('metadata', {})
        }
        
        self.messages.append(message)
        self.sequence_counter += 1
        
        return message, self.sequence_counter - 1  # Return message and its sequence
    
    def get_messages(self):
        return self.messages
    
    def get_next_sequence(self):
        return self.sequence_counter


class WorkflowExecutor:
    """
    Main workflow execution engine
    """
    
    def __init__(self, workflow_parser, llm_provider_manager, chat_manager, docaware_handler, human_input_handler, reflection_handler):
        self.workflow_parser = workflow_parser
        self.llm_provider_manager = llm_provider_manager
        self.chat_manager = chat_manager
        self.docaware_handler = docaware_handler
        self.human_input_handler = human_input_handler
        self.reflection_handler = reflection_handler
    
    @staticmethod
    def _is_last_agent_before_end(node_id, execution_sequence):
        """Check if this node is the last agent before EndNode in execution order."""
        for i, node in enumerate(execution_sequence):
            if node.get('id') == node_id:
                # Check if the next node is EndNode
                if i + 1 < len(execution_sequence):
                    next_node = execution_sequence[i + 1]
                    return next_node.get('type') == 'EndNode'
                # Last node in sequence
                return True
        return False

    async def execute_workflow(self, workflow: AgentWorkflow, executed_by, deployment_context: Optional[Dict[str, Any]] = None, event_callback=None, stream_callback=None) -> Dict[str, Any]:
        """
        Execute the complete workflow with REAL LLM calls and conversation chaining
        Returns execution results as dictionary instead of database records

        Args:
            stream_callback: Optional async callable(chunk: str) for streaming final agent output

        Args:
            workflow: The AgentWorkflow instance to execute
            executed_by: User who initiated the execution
            deployment_context: Optional deployment context with user query for UserProxyAgent handling
        """
        # Get workflow data using sync_to_async to avoid async context issues
        workflow_id = await sync_to_async(lambda: workflow.workflow_id)()
        graph_json = await sync_to_async(lambda: workflow.graph_json)()
        workflow_name = await sync_to_async(lambda: workflow.name)()
        project_id = await sync_to_async(lambda: workflow.project.project_id)()
        
        is_deployment = deployment_context is not None and deployment_context.get('is_deployment', False)
        if is_deployment:
            logger.info(f"🚀 DEPLOYMENT: Starting workflow execution for {workflow_id} (deployment mode)")
        else:
            logger.info(f"🚀 ORCHESTRATOR: Starting REAL workflow execution for {workflow_id}")
        
        start_time = timezone.now()
        # Generate unique execution_id with UUID to prevent collisions in parallel execution
        execution_id = f"exec_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        
        # CRITICAL FIX: Create execution record IMMEDIATELY so it's available for human input pausing
        execution_record = await sync_to_async(WorkflowExecution.objects.create)(
            workflow=workflow,
            execution_id=execution_id,
            start_time=start_time,
            status=WorkflowExecutionStatus.RUNNING,
            executed_by=executed_by,
            conversation_history="",
            total_messages=0,
            total_agents_involved=0,
            providers_used=[],
            result_summary=""
        )
        logger.info(f"💾 ORCHESTRATOR: Created execution record {execution_id}")
        
        try:
            # Parse workflow into execution sequence
            execution_sequence = self.workflow_parser.parse_workflow_graph(graph_json)
            
            if not execution_sequence:
                raise Exception("No execution sequence could be built from workflow graph")
            
            # CRITICAL FIX: Validate execution sequence before starting
            # Check that all nodes from graph are in sequence (except reflection-only targets)
            graph_node_ids = {node['id'] for node in graph_json.get('nodes', [])}
            sequence_node_ids = {node['id'] for node in execution_sequence}
            
            # Find nodes missing from sequence (excluding reflection-only targets which are intentionally excluded)
            missing_nodes = graph_node_ids - sequence_node_ids
            if missing_nodes:
                missing_node_names = [next((n.get('data', {}).get('name', nid) for n in graph_json.get('nodes', []) if n['id'] == nid), nid) for nid in missing_nodes]
                logger.warning(f"⚠️ ORCHESTRATOR: {len(missing_nodes)} nodes not in execution sequence: {missing_node_names}")
                # Don't fail here - reflection-only targets are intentionally excluded
                # But log for debugging
            
            # Validate sequence order: check that dependencies are satisfied
            sequence_node_map = {node['id']: node for node in execution_sequence}
            for i, node in enumerate(execution_sequence):
                node_id = node['id']
                # Check all incoming sequential edges
                for edge in graph_json.get('edges', []):
                    if edge.get('target') == node_id and edge.get('type') == 'sequential':
                        source_id = edge.get('source')
                        if source_id in sequence_node_map:
                            # Source should appear before target in sequence
                            source_index = next((idx for idx, n in enumerate(execution_sequence) if n['id'] == source_id), -1)
                            if source_index >= i:
                                source_name = sequence_node_map[source_id].get('data', {}).get('name', source_id)
                                target_name = node.get('data', {}).get('name', node_id)
                                logger.error(f"❌ ORCHESTRATOR: Dependency violation: {target_name} (position {i}) depends on {source_name} (position {source_index})")
                                raise Exception(f"Execution sequence violation: {target_name} appears before dependency {source_name}")
            
            logger.info(f"✅ ORCHESTRATOR: Execution sequence validated - {len(execution_sequence)} nodes in correct dependency order")
            
            # Initialize conversation tracking
            conversation_history = ""
            messages = execution_record.messages_data or [] # Load existing messages
            agents_involved = set()
            total_response_time = 0
            providers_used = []
            executed_nodes = execution_record.executed_nodes or {} # Load existing executed nodes
            
            # CRITICAL FIX: Use separate message sequence counter for chronological ordering
            # This ensures messages are logged in actual execution order, not graph parsing order
            message_sequence = len(messages)  # Continue from existing messages
            
            # Execute nodes with parallel execution support
            node_index = 0

            # Experiment helpers for execution analysis (sequential vs parallel)
            parallel_batches = 0
            parallel_nodes_executed = 0
            sequential_nodes_executed = 0
            
            # CRITICAL FIX: Handle StartNode first (it's skipped by _find_ready_nodes)
            if node_index < len(execution_sequence):
                start_node = execution_sequence[node_index]
                if start_node.get('type') == 'StartNode':
                    start_node_data = start_node.get('data', {})
                    start_node_id = start_node.get('id')
                    start_prompt = start_node_data.get('prompt', 'Please begin the conversation.')
                    conversation_history = f"Start Node: {start_prompt}"
                    
                    # Store node output for multi-input support
                    executed_nodes[start_node_id] = f"Start Node: {start_prompt}"
                    
                    # Track start message
                    messages.append({
                        'sequence': message_sequence,
                        'agent_name': 'Start',
                        'agent_type': 'StartNode',
                        'content': start_prompt,
                        'message_type': 'workflow_start',
                        'timestamp': timezone.now().isoformat(),
                        'response_time_ms': 0
                    })
                    message_sequence += 1
                    
                    # Save conversation history to execution record
                    execution_record.conversation_history = conversation_history
                    execution_record.executed_nodes = executed_nodes
                    await sync_to_async(execution_record.save)(update_fields=['conversation_history', 'executed_nodes'])
                    
                    logger.info(f"✅ ORCHESTRATOR: StartNode executed - prompt: '{start_prompt[:100]}...'")
                    node_index += 1  # Move past StartNode
            
            while node_index < len(execution_sequence):
                # Check if execution has been stopped
                await sync_to_async(execution_record.refresh_from_db)()
                if execution_record.status == WorkflowExecutionStatus.STOPPED:
                    logger.info(f"🛑 ORCHESTRATOR: Execution {execution_id} has been stopped, terminating workflow")
                    return {
                        'status': 'stopped',
                        'message': 'Workflow execution was stopped by user',
                        'execution_id': execution_id
                    }
                
                # PARALLEL EXECUTION: Find all nodes ready to execute in parallel
                ready_nodes = self._find_ready_nodes(execution_sequence, executed_nodes, graph_json, node_index)
                
                if not ready_nodes:
                    # No ready nodes, move to next
                    node_index += 1
                    continue
                
                # If only one node is ready, execute it sequentially
                if len(ready_nodes) == 1:
                    node_index, node = ready_nodes[0]
                    sequential_nodes_executed += 1
                    node_index += 1  # Move to next after execution
                else:
                    # Multiple nodes ready - execute in parallel
                    logger.info(f"🔀 PARALLEL: Executing {len(ready_nodes)} nodes in parallel")
                    node_names = [n[1].get('data', {}).get('name', n[1].get('id')) for n in ready_nodes]
                    logger.info(f"🔀 PARALLEL: Nodes: {', '.join(node_names)}")
                    parallel_batches += 1
                    parallel_nodes_executed += len(ready_nodes)
                    
                    # CRITICAL FIX: Check if UserProxyAgent's dependencies are actually satisfied
                    # Build dependency map to check UserProxyAgent dependencies
                    edges = graph_json.get('edges', [])
                    nodes = graph_json.get('nodes', [])
                    node_map = {node.get('id'): node for node in nodes}
                    dependency_map = {}
                    for edge in edges:
                        edge_type = edge.get('type', 'sequential')
                        source_id = edge.get('source')
                        target_id = edge.get('target')
                        target_node = node_map.get(target_id)
                        is_user_proxy = (target_node and 
                                        target_node.get('type') == 'UserProxyAgent' and
                                        target_node.get('data', {}).get('require_human_input', True))
                        if edge_type == 'sequential' or (edge_type == 'reflection' and is_user_proxy):
                            if target_id not in dependency_map:
                                dependency_map[target_id] = set()
                            dependency_map[target_id].add(source_id)
                    
                    # Separate UserProxyAgent nodes from other nodes
                    ready_user_proxy_nodes = []
                    other_ready_nodes = []
                    
                    for idx, node in ready_nodes:
                        if node.get('type') == 'UserProxyAgent' and node.get('data', {}).get('require_human_input', True):
                            node_id = node.get('id')
                            dependencies = dependency_map.get(node_id, set())
                            # Check if all dependencies (including reflection edges) are satisfied
                            if all(dep_id in executed_nodes for dep_id in dependencies):
                                ready_user_proxy_nodes.append((idx, node))
                                logger.info(f"✅ PARALLEL: UserProxyAgent {node.get('data', {}).get('name')} dependencies satisfied")
                            else:
                                # Dependencies not satisfied - don't execute yet
                                missing_deps = [dep_id for dep_id in dependencies if dep_id not in executed_nodes]
                                logger.info(f"⏳ PARALLEL: UserProxyAgent {node.get('data', {}).get('name')} waiting for dependencies: {missing_deps}")
                        else:
                            other_ready_nodes.append((idx, node))
                    
                    # CRITICAL FIX: Always execute other nodes first if available
                    # This ensures parallel execution happens before UserProxyAgent pauses
                    if other_ready_nodes:
                        # Execute other nodes in parallel first, UserProxyAgent will wait
                        parallel_results = await self._execute_nodes_in_parallel(
                            other_ready_nodes, workflow, graph_json, executed_nodes, conversation_history,
                            execution_record, messages, message_sequence, agents_involved,
                            total_response_time, providers_used, project_id,
                            deployment_context=deployment_context,
                        )
                        
                        # Update state from parallel execution results
                        for result in parallel_results:
                            if result.get('executed'):
                                out_val = result['output']
                                executed_nodes[result['node_id']] = out_val
                                conversation_history += f"\n{result['node_name']}: {plain_executed_output(out_val)}"
                                agents_involved.update(result.get('agents_involved', []))
                                total_response_time += result.get('response_time_ms', 0)
                                for provider in result.get('providers_used', []):
                                    if provider not in providers_used:
                                        providers_used.append(provider)
                        
                        # Update message sequence
                        executed_count = sum(1 for r in parallel_results if r.get('executed'))
                        message_sequence += executed_count
                        
                        # Save updated state
                        execution_record.executed_nodes = executed_nodes
                        execution_record.conversation_history = conversation_history
                        execution_record.messages_data = messages
                        await sync_to_async(execution_record.save)(update_fields=['executed_nodes', 'conversation_history', 'messages_data'])
                        
                        # Move past all executed nodes
                        max_index = max(idx for idx, _ in other_ready_nodes)
                        node_index = max_index + 1
                        # Continue loop to check UserProxyAgent again after parallel execution
                        continue
                    elif ready_user_proxy_nodes:
                        # Only UserProxyAgent nodes ready (dependencies satisfied) - execute sequentially to pause
                        node_index, node = ready_user_proxy_nodes[0]
                        # Will be handled in single node execution below
                    else:
                        # No ready nodes (shouldn't happen)
                        node_index += 1
                        continue
                
                # Single node execution - node is already set from ready_nodes[0] or ready_user_proxy_nodes[0]
                node_type = node.get('type')
                node_data = node.get('data', {})
                node_name = node_data.get('name', f'Node_{node.get("id", "unknown")}')
                node_id = node.get('id')
                
                # Add validation for GroupChatManager to ensure correct name extraction
                if node_type == 'GroupChatManager':
                    # Ensure we have a valid name
                    if not node_name or node_name.startswith('Node_'):
                        # Fallback to a more descriptive name
                        node_name = node_data.get('label', 'Group Chat Manager')
                    logger.info(f"🔍 DEBUG: GroupChatManager node_name before execution: {node_name}")
                
                logger.info(f"🎯 ORCHESTRATOR: Executing node {node_name} (type: {node_type}) [SEQUENTIAL]")
                
                if node_type == 'StartNode':
                    # Handle start node
                    start_prompt = node_data.get('prompt', 'Please begin the conversation.')
                    conversation_history = f"Start Node: {start_prompt}"
                    
                    # 🔍 DEBUG: Log StartNode details
                    logger.info(f"📝 STARTNODE DEBUG: Raw node_data: {node_data}")
                    logger.info(f"📝 STARTNODE DEBUG: Extracted prompt: '{start_prompt}'")
                    logger.info(f"📝 STARTNODE DEBUG: Conversation history set to: '{conversation_history}'")
                    
                    # CRITICAL: Validate StartNode prompt is not hardcoded test query
                    if start_prompt.lower().strip() in ['test query', 'test query for document search', 'sample query', 'example query']:
                        logger.error(f"❌ STARTNODE ERROR: StartNode contains forbidden hardcoded query: '{start_prompt}'")
                        logger.error(f"❌ STARTNODE ERROR: This should never happen! Check frontend/workflow definition.")
                        # Force replace with a valid query to prevent system failure
                        start_prompt = "Please provide information about the requested topic."
                        conversation_history = f"Start Node: {start_prompt}"
                        logger.info(f"🔧 STARTNODE FIX: Replaced with safe prompt: '{start_prompt}'")
                    
                    # Store node output for multi-input support
                    executed_nodes[node_id] = f"Start Node: {start_prompt}"
                    
                    # Track start message
                    messages.append({
                        'sequence': message_sequence,
                        'agent_name': 'Start',
                        'agent_type': 'StartNode',
                        'content': start_prompt,
                        'message_type': 'workflow_start',
                        'timestamp': timezone.now().isoformat(),
                        'response_time_ms': 0
                    })
                    message_sequence += 1  # Increment for chronological ordering
                    
                    # CRITICAL FIX: Save conversation history to execution record after each node
                    execution_record.conversation_history = conversation_history
                    await sync_to_async(execution_record.save)()
                    
                elif node_type in ['AssistantAgent', 'UserProxyAgent', 'GroupChatManager', 'DelegateAgent']:
                    # ============================================================================
                    # PHASE 2: USERPROXYAGENT HUMAN INPUT DETECTION AND DOCAWARE PROCESSING
                    # ============================================================================
                    if node_type == 'UserProxyAgent' and node_data.get('require_human_input', True):
                        # Get input mode (default to 'user' for backward compatibility)
                        input_mode = node_data.get('input_mode', 'user')
                        
                        # Admin Input Mode: Always use internal pause mechanism (admin UI)
                        if input_mode == 'admin':
                            logger.info(f"👤 ADMIN INPUT: UserProxyAgent {node_name} requires admin input (input_mode=admin)")
                            
                            # PAUSE WORKFLOW - Use internal pause mechanism
                            human_input_data = await self.human_input_handler.pause_for_human_input(
                                workflow, node, executed_nodes, conversation_history, execution_record
                            )
                            
                            # If in deployment context, also store in deployment session for admin to provide input
                            if is_deployment and deployment_context:
                                session_id = deployment_context.get('session_id')
                                if session_id:
                                    last_message = self._extract_last_conversation_message(messages, conversation_history)
                                    await self._store_deployment_pause_state(
                                        session_id, execution_record, node_id, node_name, last_message
                                    )
                                    logger.info(f"💾 DEPLOYMENT: Stored admin input pause state in session {session_id[:8]}")
                            
                            return human_input_data  # Return paused state
                        
                        # User Input Mode: Check context
                        elif input_mode == 'user':
                            # In deployment context: Use deployment pause mechanism (client-side)
                            if is_deployment and deployment_context:
                                logger.info(f"👤 DEPLOYMENT: UserProxyAgent {node_name} requires user input in deployment context")
                                
                                # Extract the last conversation message to show to the user
                                last_message = self._extract_last_conversation_message(messages, conversation_history)
                                
                                # Get the description from UserProxyAgent node data (default to "USER INPUT REQUIRED")
                                agent_description = node_data.get('description', 'USER INPUT REQUIRED')
                                if not agent_description or not agent_description.strip():
                                    agent_description = 'USER INPUT REQUIRED'
                                
                                # Find input sources (connected agents that feed into this UserProxyAgent)
                                # This is needed to properly update the execution record
                                input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                                aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
                                
                                # Update execution record to indicate human input required
                                # This is critical for resume_workflow_with_human_input to find the execution
                                # Store input_mode in context so we can filter deployment executions from admin UI
                                aggregated_context['input_mode'] = input_mode
                                aggregated_context['is_deployment'] = True
                                await sync_to_async(self.human_input_handler.update_execution_for_human_input)(
                                    execution_record, node_id, node_name, aggregated_context
                                )
                                
                                # Store execution state in deployment session (non-blocking)
                                session_id = deployment_context.get('session_id')
                                if session_id:
                                    await self._store_deployment_pause_state(
                                        session_id, execution_record, node_id, node_name, last_message
                                    )
                                
                                # Return special response indicating human input is required
                                return {
                                    'status': 'awaiting_human_input',
                                    'execution_id': execution_record.execution_id,
                                    'agent_name': node_name,
                                    'agent_id': node_id,
                                    'human_input_required': True,
                                    'title': agent_description.strip(),
                                    'last_conversation_message': last_message,
                                    'message': f'UserProxyAgent {node_name} requires your input',
                                    'conversation_history': conversation_history
                                }
                            else:
                                # In admin UI context: Use internal pause mechanism (for testing)
                                logger.info(f"👤 USER INPUT: UserProxyAgent {node_name} requires user input in admin UI")
                                
                                # PAUSE WORKFLOW - Use internal pause mechanism
                                human_input_data = await self.human_input_handler.pause_for_human_input(
                                    workflow, node, executed_nodes, conversation_history, execution_record
                                )
                                return human_input_data  # Return paused state
                        else:
                            # Unknown input_mode, default to user input behavior
                            logger.warning(f"⚠️ USERPROXY: Unknown input_mode '{input_mode}', defaulting to user input behavior")
                            # Fall through to regular pause
                            logger.info(f"👤 HUMAN INPUT: UserProxyAgent {node_name} requires human input")
                            
                            # PAUSE WORKFLOW - NEW IMPLEMENTATION
                            human_input_data = await self.human_input_handler.pause_for_human_input(
                                workflow, node, executed_nodes, conversation_history, execution_record
                            )
                            return human_input_data  # Return paused state
                    
                    # Handle agent nodes with real LLM calls
                    agent_config = {
                        'llm_provider': node_data.get('llm_provider', 'openai'),
                        'llm_model': node_data.get('llm_model', 'gpt-3.5-turbo')
                    }
                    
                    # Get LLM provider for this agent with project context for API keys
                    project = await sync_to_async(lambda: workflow.project)()
                    llm_provider = await self.llm_provider_manager.get_llm_provider(agent_config, project)
                    if not llm_provider:
                        raise Exception(f"Failed to create LLM provider for agent {node_name} - check project API key configuration")
                    
                    # Special handling for GroupChatManager with multiple inputs support
                    if node_type == 'GroupChatManager':
                        logger.info(f"👥 ORCHESTRATOR: Executing GroupChatManager {node_name}")
                        
                        # Check for multiple inputs to this GroupChatManager
                        input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                        
                        try:
                            project = await sync_to_async(lambda: workflow.project)()

                            # Always use multi-input path (handles single input too)
                            if len(input_sources) > 1:
                                logger.info(f"📥 ORCHESTRATOR: GroupChatManager {node_name} has {len(input_sources)} input sources")
                            else:
                                logger.info(f"📥 ORCHESTRATOR: GroupChatManager {node_name} has 1 input source")

                            chat_result = await self.chat_manager.execute_group_chat_manager_with_multiple_inputs(
                                node, llm_provider, input_sources, executed_nodes, execution_sequence, graph_json, str(project_id), project, execution_id, event_callback=event_callback
                            )

                            logger.info(f"✅ ORCHESTRATOR: GroupChatManager {node_name} completed successfully")

                            agent_response_text = chat_result['final_response']
                            delegate_conversations = chat_result['delegate_conversations']
                            delegate_status = chat_result['delegate_status']
                            total_iterations = chat_result['total_iterations']

                            node_name = node_data.get('name', node_data.get('label', 'Group Chat Manager'))

                            gcm_metadata = {
                                    'llm_provider': agent_config['llm_provider'],
                                    'llm_model': agent_config['llm_model'],
                                    'is_group_chat_manager': True,
                                    'total_iterations': total_iterations,
                                    'delegate_count': len(delegate_status),
                                    'expandable': True,
                                    'delegate_conversations': delegate_conversations,
                                    'delegate_status': delegate_status,
                                    'manager_plan': chat_result.get('manager_plan', ''),
                            }
                            if chat_result.get('citations'):
                                gcm_metadata['citations'] = chat_result['citations']

                            messages.append({
                                'sequence': message_sequence,
                                'agent_name': node_name,
                                'agent_type': node_type,
                                'content': agent_response_text,
                                'message_type': 'group_chat_summary',
                                'timestamp': timezone.now().isoformat(),
                                'response_time_ms': 0,
                                'token_count': None,
                                'metadata': gcm_metadata,
                            })
                            message_sequence += 1

                            # Log individual delegate messages from conversation log
                            for conv_entry in delegate_conversations:
                                if isinstance(conv_entry, str) and ':' in conv_entry:
                                    parts = conv_entry.split(':', 1)
                                    if len(parts) == 2:
                                        delegate_name = parts[0].strip()
                                        response_text = parts[1].strip()
                                        messages.append({
                                            'sequence': message_sequence,
                                            'agent_name': delegate_name,
                                            'agent_type': 'DelegateAgent',
                                            'content': response_text,
                                            'message_type': 'delegate_response',
                                            'timestamp': timezone.now().isoformat(),
                                            'response_time_ms': 0,
                                            'token_count': None,
                                            'metadata': {
                                                'parent_manager': node_name,
                                                'delegation_mode': 'tool_calling',
                                                'llm_provider': agent_config.get('llm_provider', 'unknown'),
                                                'llm_model': agent_config.get('llm_model', 'unknown')
                                            }
                                        })
                                        message_sequence += 1

                            execution_record.messages_data = messages
                            await sync_to_async(execution_record.save)()
                            logger.info(f"💾 ORCHESTRATOR: Saved GroupChatManager {node_name} message with {len(delegate_conversations)} delegate conversations")

                            conversation_history += f"\n{node_name}: {agent_response_text}"
                            executed_nodes[node_id] = agent_response_text
                            agents_involved.add(node_name)
                            if agent_config['llm_provider'] not in providers_used:
                                providers_used.append(agent_config['llm_provider'])

                            execution_record.conversation_history = conversation_history
                            await sync_to_async(execution_record.save)()
                        except Exception as gcm_error:
                            logger.error(f"❌ ORCHESTRATOR: GroupChatManager {node_name} failed: {gcm_error}")
                            raise gcm_error
                    else:
                        # Handle regular agents (AssistantAgent, UserProxyAgent, and standalone DelegateAgent)
                        # Note: DelegateAgent can run standalone OR be coordinated by GroupChatManager
                        
                        # Handle regular agents (AssistantAgent, UserProxyAgent, DelegateAgent)
                        logger.info(f"🤖 ORCHESTRATOR: Executing agent {node_name} (type: {node_type})")
                        
                        # Check for multiple inputs to this agent
                        input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                        
                        # CRITICAL FIX: Validate all required inputs are available before executing
                        if len(input_sources) > 0:
                            missing_inputs = []
                            for input_source in input_sources:
                                source_id = input_source.get('source_id')
                                source_name = input_source.get('name', source_id)
                                if source_id not in executed_nodes:
                                    missing_inputs.append(f"{source_name} (node_id: {source_id})")
                            
                            if missing_inputs:
                                error_msg = f"Cannot execute {node_name}: Missing required inputs from {', '.join(missing_inputs)}. Available inputs: {list(executed_nodes.keys())}"
                                logger.error(f"❌ ORCHESTRATOR: {error_msg}")
                                raise Exception(error_msg)
                        
                        try:
                            if len(input_sources) > 1:
                                # Use multi-input processing
                                logger.info(f"📥 ORCHESTRATOR: Agent {node_name} has {len(input_sources)} input sources - using multi-input mode")
                                aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
                                prompt_result = await self.chat_manager.craft_conversation_prompt_with_docaware(
                                    aggregated_context, node, str(project_id), conversation_history
                                )
                                # Handle dict return with potential file_references (Full Document Mode)
                                llm_messages = prompt_result.get('messages', prompt_result) if isinstance(prompt_result, dict) else prompt_result
                                
                                # Apply file reference formatting if file attachments are enabled
                                if isinstance(prompt_result, dict) and prompt_result.get('file_references'):
                                    logger.info(f"📎 FILE ATTACHMENTS: Formatting {len(prompt_result['file_references'])} file references for {node_name}")
                                    llm_messages = self.chat_manager.format_messages_with_file_refs(
                                        llm_messages,
                                        prompt_result['file_references'],
                                        prompt_result.get('provider', 'openai')
                                    )
                            else:
                                # Use traditional single-input processing
                                logger.info(f"📥 ORCHESTRATOR: Agent {node_name} has {len(input_sources)} input source - using single-input mode")
                                prompt_result_single = await self.chat_manager.craft_conversation_prompt(
                                    conversation_history, node, str(project_id)
                                )
                                # Handle dict return with potential file_references (File Attachments)
                                llm_messages = prompt_result_single.get('messages', prompt_result_single) if isinstance(prompt_result_single, dict) else prompt_result_single
                                
                                # Apply file reference formatting if file attachments are enabled
                                if isinstance(prompt_result_single, dict) and prompt_result_single.get('file_references'):
                                    logger.info(f"📎 FILE ATTACHMENTS: Formatting {len(prompt_result_single['file_references'])} file references for {node_name}")
                                    llm_messages = self.chat_manager.format_messages_with_file_refs(
                                        llm_messages,
                                        prompt_result_single['file_references'],
                                        prompt_result_single.get('provider', 'openai')
                                    )
                            
                            # --- Chat file references (deployment chatbot uploads) ---
                            if is_deployment and deployment_context:
                                # Attach file API references to ALL agents via File API
                                if deployment_context.get('chat_file_references'):
                                    _chat_refs = deployment_context['chat_file_references']
                                    _provider = node_data.get('llm_provider', 'openai').lower()
                                    logger.info(f"📎 CHAT FILES: Attaching {len(_chat_refs)} session files to {node_name} ({_provider})")
                                    llm_messages = self.chat_manager.format_messages_with_file_refs(
                                        llm_messages, _chat_refs, _provider
                                    )
                                # Inject text-extracted attachments (fallback for files without File API support)
                                if deployment_context.get('chat_text_attachments'):
                                    for _att in deployment_context['chat_text_attachments']:
                                        _text_block = f"\n\n--- Attached Document: {_att['filename']} ---\n{_att['text']}\n--- End Document ---"
                                        for _msg in reversed(llm_messages):
                                            if _msg.get('role') == 'user':
                                                if isinstance(_msg['content'], str):
                                                    _msg['content'] += _text_block
                                                elif isinstance(_msg['content'], list):
                                                    for _part in _msg['content']:
                                                        if isinstance(_part, dict) and _part.get('type') == 'text':
                                                            _part['text'] += _text_block
                                                            break
                                                break
                                    logger.info(f"📎 CHAT TEXT: Injected {len(deployment_context['chat_text_attachments'])} text attachments into {node_name}")

                            # --- Tool Calling Mode (document tools, web search, and/or DocAware) ---
                            _synthesis_citations = []
                            _ws_handler = getattr(self.chat_manager, 'websearch_handler', None)
                            _ws_enabled = _ws_handler and _ws_handler.is_websearch_enabled(node)
                            # URL mode injects content into the context window — no tool loop needed
                            _ws_needs_tool_loop = _ws_enabled and _ws_handler.get_websearch_mode(node) != 'urls'
                            _da_handler = getattr(self.chat_manager, 'docaware_handler', None)
                            _da_enabled = _da_handler and _da_handler.is_docaware_enabled(node)
                            # Bypass: skip doc tool loop when chat uploads are the only content
                            # (no project docs selected → info tools return ALL project docs, confusing the LLM)
                            _doc_selected = node_data.get('doc_tool_calling_documents')
                            _no_project_docs = isinstance(_doc_selected, list) and len(_doc_selected) == 0
                            _has_chat_files = bool(
                                is_deployment and deployment_context
                                and (deployment_context.get('chat_file_references') or deployment_context.get('chat_text_attachments'))
                            )
                            _skip_doc_tool_for_chat_upload = (
                                node_data.get('doc_tool_calling')
                                and _no_project_docs
                                and _has_chat_files
                                and not _ws_needs_tool_loop
                                and not _da_enabled
                            )
                            if _skip_doc_tool_for_chat_upload:
                                logger.info(
                                    f"⏭️ DOC TOOL BYPASS: Skipping tool loop for {node_name} — "
                                    f"no project docs selected, "
                                    f"{len(deployment_context.get('chat_text_attachments', []))} "
                                    f"chat text attachment(s) already in context"
                                )

                            if (node_data.get('doc_tool_calling') or _ws_needs_tool_loop or _da_enabled) and not _skip_doc_tool_for_chat_upload:
                                agent_response_text, _synthesis_citations = await self._execute_doc_tool_calling(
                                    node=node,
                                    node_name=node_name,
                                    node_type=node_type,
                                    llm_messages=llm_messages,
                                    llm_provider=llm_provider,
                                    agent_config=agent_config,
                                    project_id=str(project_id),
                                    messages=messages,
                                    message_sequence=message_sequence,
                                    execution_record=execution_record,
                                    event_callback=event_callback,
                                )
                                # Advance message_sequence past any intermediate messages saved
                                message_sequence = max(
                                    (m.get('sequence', 0) for m in messages),
                                    default=message_sequence,
                                ) + 1
                                # Create a stub so downstream code can access agent_response attrs
                                from llm_eval.providers.base import LLMResponse
                                agent_response = LLMResponse(
                                    text=agent_response_text,
                                    model=agent_config.get('llm_model', 'unknown'),
                                    provider=agent_config.get('llm_provider', 'unknown'),
                                    response_time_ms=0,
                                )
                            else:
                                # Standard single LLM call (existing path)
                                # Check if we should stream this response
                                _should_stream = (
                                    stream_callback
                                    and hasattr(llm_provider, 'generate_response_stream')
                                    and self._is_last_agent_before_end(node_id, execution_sequence)
                                )
                                if _should_stream:
                                    # Stream the response token-by-token
                                    import time as _time
                                    _stream_start = _time.time()
                                    _chunks = []
                                    async for chunk in llm_provider.generate_response_stream(messages=llm_messages):
                                        _chunks.append(chunk)
                                        await stream_callback(chunk)
                                    _full_text = ''.join(_chunks)
                                    from llm_eval.providers.base import LLMResponse
                                    agent_response = LLMResponse(
                                        text=_full_text,
                                        model=agent_config.get('llm_model', 'unknown'),
                                        provider=agent_config.get('llm_provider', 'unknown'),
                                        response_time_ms=int((_time.time() - _stream_start) * 1000),
                                    )
                                    agent_response_text = _full_text.strip()
                                else:
                                    agent_response = await llm_provider.generate_response(
                                        messages=llm_messages
                                    )

                                    if agent_response.error:
                                        raise Exception(f"Agent {node_name} error: {agent_response.error}")

                                    agent_response_text = agent_response.text.strip()
                            
                                if not agent_response_text:
                                    provider_error = getattr(agent_response, "error", None)
                                    if provider_error == "":
                                        logger.error("❌ ORCHESTRATOR: Provider returned empty error string; API may have signalled failure with no message.")
                                    error_msg = f"Agent {node_name} returned an empty response. This indicates an LLM error or configuration issue."
                                    logger.error(f"❌ ORCHESTRATOR: {error_msg}")
                                    logger.error(f"❌ ORCHESTRATOR: LLM Provider: {type(llm_provider).__name__}, Model: {agent_config.get('llm_model', 'unknown')}")
                                    logger.error(f"❌ ORCHESTRATOR: agent_response.error={provider_error!r}, agent_response.text (first 200 chars)={repr((agent_response.text or '')[:200])}")
                                    raise Exception(error_msg)
                            
                            logger.info(f"✅ ORCHESTRATOR: Agent {node_name} completed successfully - response length: {len(agent_response_text)} chars")
                            logger.info(f"🔍 DEBUG: Raw agent response for {node_name}: {agent_response_text[:200]}...")
                            
                            # CRITICAL FIX: Save agent message BEFORE reflection processing
                            # This ensures the message is recorded even if workflow pauses for reflection
                            # NOTE: Use 'messages' array (structured messages for storage), NOT 'llm_messages' (LLM-formatted)
                            _msg_metadata = {
                                'llm_provider': agent_config['llm_provider'],
                                'llm_model': agent_config['llm_model'],
                                'cost_estimate': getattr(agent_response, 'cost_estimate', None) if hasattr(agent_response, 'cost_estimate') else None,
                            }
                            if _synthesis_citations:
                                _msg_metadata['citations'] = _synthesis_citations

                            messages.append({
                                'sequence': message_sequence,
                                'agent_name': node_name,
                                'agent_type': node_type,
                                'content': agent_response_text,
                                'message_type': 'chat',
                                'timestamp': timezone.now().isoformat(),
                                'response_time_ms': getattr(agent_response, 'response_time_ms', 0) if hasattr(agent_response, 'response_time_ms') else 0,
                                'token_count': getattr(agent_response, 'token_count', None) if hasattr(agent_response, 'token_count') else None,
                                'metadata': _msg_metadata,
                            })
                            message_sequence += 1  # Increment for chronological ordering
                            
                            # Save messages to execution record
                            execution_record.messages_data = messages
                            await sync_to_async(execution_record.save)()
                            logger.info(f"💾 ORCHESTRATOR: Saved {node_name} message before reflection processing")
                            
                            # Track agent involvement and provider usage
                            agents_involved.add(node_name)
                            if hasattr(agent_response, 'response_time_ms'):
                                total_response_time += agent_response.response_time_ms
                            
                            # Track provider usage
                            if agent_config['llm_provider'] not in providers_used:
                                providers_used.append(agent_config['llm_provider'])
                            
                            # Handle reflection connections if present
                            try:
                                # Preserve original response before any reflection processing
                                original_agent_response = agent_response_text
                                
                                # First handle self-reflection
                                self_reflected_response = await self.reflection_handler.handle_reflection_connections(
                                    node, agent_response_text, graph_json, llm_provider
                                )
                                if self_reflected_response != agent_response_text:
                                    logger.info(f"🔄 SELF-REFLECTION: {node_name} response updated through self-reflection - new length: {len(self_reflected_response)} chars")
                                    agent_response_text = self_reflected_response
                                
                                # Check for cross-agent reflection connections
                                node_id = node.get('id')
                                
                                cross_agent_reflection_edges = []
                                for edge in graph_json.get('edges', []):
                                    if (edge.get('source') == node_id and 
                                        edge.get('type') == 'reflection' and 
                                        edge.get('target') != node_id):  # Cross-agent reflection
                                        cross_agent_reflection_edges.append(edge)
                                
                                # Process cross-agent reflections using original response
                                for reflection_edge in cross_agent_reflection_edges:
                                    logger.info(f"🔄 CROSS-AGENT-REFLECTION: Processing cross-agent reflection from {node_name}")
                                    
                                    reflection_result, updated_conversation = await self.reflection_handler.handle_cross_agent_reflection(
                                        node, original_agent_response, reflection_edge, graph_json, execution_record, conversation_history, deployment_context
                                    )
                                    
                                    logger.info(f"🔍 CROSS-AGENT-REFLECTION: Reflection result type: {type(reflection_result)}, value: {reflection_result}")
                                    
                                    # Check if we're waiting for human input in reflection
                                    if reflection_result == 'AWAITING_REFLECTION_INPUT':
                                        logger.info(f"👤 CROSS-AGENT-REFLECTION: Pausing workflow - awaiting human input for reflection (admin UI)")
                                        return {
                                            'status': 'paused_for_reflection_input',
                                            'conversation_history': updated_conversation,
                                            'message': f'Workflow paused - {execution_record.awaiting_human_input_agent} needs to provide reflection feedback',
                                            'execution_id': execution_record.execution_id
                                        }
                                    elif reflection_result == 'AWAITING_DEPLOYMENT_INPUT':
                                        # User input mode in deployment context - return deployment pause status
                                        logger.info(f"👤 CROSS-AGENT-REFLECTION: Pausing workflow - awaiting user input for reflection in deployment")
                                        
                                        # Get target node info for response
                                        target_node_id = execution_record.human_input_agent_id
                                        target_node_name = execution_record.awaiting_human_input_agent
                                        
                                        # Find target node to get description
                                        target_node = None
                                        for n in graph_json.get('nodes', []):
                                            if n.get('id') == target_node_id:
                                                target_node = n
                                                break
                                        
                                        target_data = target_node.get('data', {}) if target_node else {}
                                        agent_description = target_data.get('description', 'USER INPUT REQUIRED')
                                        if not agent_description or not agent_description.strip():
                                            agent_description = 'USER INPUT REQUIRED'
                                        
                                        # Extract last message
                                        last_message = self._extract_last_conversation_message(messages, updated_conversation)
                                        
                                        # Store execution state in deployment session
                                        session_id = deployment_context.get('session_id') if deployment_context else None
                                        if session_id:
                                            await self._store_deployment_pause_state(
                                                session_id, execution_record, target_node_id, target_node_name, last_message
                                            )
                                        
                                        logger.info(f"✅ CROSS-AGENT-REFLECTION: Returning awaiting_human_input status - stopping execution")
                                        logger.info(f"✅ CROSS-AGENT-REFLECTION: Title: {agent_description.strip()}, Last message: {last_message[:100] if last_message else 'N/A'}...")
                                        
                                        # CRITICAL: Return immediately to stop execution - do not continue processing
                                        return {
                                            'status': 'awaiting_human_input',
                                            'execution_id': execution_record.execution_id,
                                            'agent_name': target_node_name,
                                            'agent_id': target_node_id,
                                            'human_input_required': True,
                                            'title': agent_description.strip(),
                                            'last_conversation_message': last_message,
                                            'message': f'UserProxyAgent {target_node_name} requires your input (reflection)',
                                            'conversation_history': updated_conversation,
                                            'messages': messages  # Include messages so far for debugging
                                        }
                                    else:
                                        # Reflection completed successfully
                                        agent_response_text = reflection_result
                                        conversation_history = updated_conversation
                                        logger.info(f"✅ CROSS-AGENT-REFLECTION: Completed cross-agent reflection - final response length: {len(agent_response_text)} chars")
                                
                            except Exception as reflection_error:
                                logger.error(f"❌ REFLECTION: Error processing reflection for {node_name}: {reflection_error}")
                                import traceback
                                logger.error(f"❌ REFLECTION: Traceback: {traceback.format_exc()}")
                                # Continue with original response if reflection fails
                            
                            # CRITICAL FIX: Update conversation history with agent response (plain text + optional citation appendix for downstream single-input prompts)
                            conversation_history += f"\n{node_name}: {agent_response_text}"
                            if _synthesis_citations:
                                conversation_history += format_upstream_citations_block(
                                    node_name, _synthesis_citations
                                )
                            
                            # Store node output for multi-input support (pack citations for aggregate_multiple_inputs)
                            handoff_cites = _synthesis_citations if _synthesis_citations else None
                            executed_nodes[node_id] = pack_executed_output(
                                agent_response_text, handoff_cites
                            )
                            
                            # CRITICAL FIX: Save executed_nodes immediately to prevent duplicate execution
                            execution_record.executed_nodes = executed_nodes
                            
                            # CRITICAL FIX: Save updated conversation history to database
                            execution_record.conversation_history = conversation_history
                            await sync_to_async(execution_record.save)(update_fields=['executed_nodes', 'conversation_history'])
                            logger.info(f"💾 ORCHESTRATOR: Saved executed_nodes and conversation_history for {node_name} (node_id: {node_id})")
                            
                        except Exception as agent_error:
                            logger.error(f"❌ ORCHESTRATOR: Agent {node_name} failed: {agent_error}")
                            raise agent_error
                
                elif node_type == 'MCPServer':
                    # Handle MCP Server node
                    server_type = node_data.get('server_type')
                    selected_tools = node_data.get('selected_tools', [])
                    server_config = node_data.get('server_config', {})
                    
                    if not server_type:
                        error_msg = f"MCP Server node {node_name} missing required 'server_type' field"
                        logger.error(f"❌ ORCHESTRATOR: {error_msg}")
                        raise ValueError(error_msg)
                    
                    logger.info(f"🔧 MCP SERVER: Executing {node_name} (server_type: {server_type})")
                    
                    try:
                        # Get MCP server manager
                        mcp_manager = get_mcp_server_manager()
                        
                        # Get input from previous nodes
                        input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                        aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
                        
                        # For MCP Server nodes, we expect the input to contain tool execution requests
                        # The input should be in format: {"tool": "tool_name", "arguments": {...}}
                        # If not in that format, we'll try to extract tool calls from the text
                        # Note: json is already imported at module level
                        tool_request = None
                        
                        # Get primary input from aggregated context (prefer plain text for MCP tool args)
                        if isinstance(aggregated_context, dict):
                            primary_input = aggregated_context.get('primary_plain') or aggregated_context.get('primary_input', '')
                        else:
                            primary_input = str(aggregated_context)
                        
                        # Try to parse as JSON first (tool request format)
                        if isinstance(primary_input, str):
                            try:
                                parsed = json.loads(primary_input)
                                if isinstance(parsed, dict) and 'tool' in parsed:
                                    tool_request = parsed
                            except (json.JSONDecodeError, ValueError):
                                pass
                        
                        # If not a tool request, try to create one from available tools
                        if not tool_request:
                            available_tools = await mcp_manager.get_available_tools(workflow.project, server_type)
                            if available_tools and len(available_tools) > 0:
                                # Filter by selected_tools if specified
                                if selected_tools and len(selected_tools) > 0:
                                    available_tools = [t for t in available_tools if t.get('name') in selected_tools]
                                
                                if available_tools:
                                    # Use first available tool with primary input as query/search term
                                    first_tool = available_tools[0]
                                    tool_params = first_tool.get('parameters', {}).get('properties', {})
                                    
                                    # Build arguments based on tool parameters
                                    tool_arguments = {}
                                    if 'query' in tool_params:
                                        tool_arguments['query'] = str(primary_input)[:500] if primary_input else ''
                                    elif 'file_id' in tool_params:
                                        # Try to extract file ID from input
                                        tool_arguments['file_id'] = str(primary_input).strip()
                                    else:
                                        # Generic argument - use primary input
                                        tool_arguments = {'input': str(primary_input)[:500] if primary_input else ''}
                                    
                                    tool_request = {
                                        'tool': first_tool['name'],
                                        'arguments': tool_arguments
                                    }
                        
                        if not tool_request or 'tool' not in tool_request:
                            error_msg = f"No valid tool request found for MCP Server {node_name}"
                            logger.warning(f"⚠️ MCP SERVER: {error_msg}")
                            node_output = f"MCP Server {node_name}: {error_msg}"
                        else:
                            # Execute the tool
                            tool_name = tool_request['tool']
                            tool_arguments = tool_request.get('arguments', {})
                            
                            logger.info(f"🔧 MCP SERVER: Executing tool {tool_name} on {server_type}")
                            tool_result = await mcp_manager.execute_tool(
                                workflow.project,
                                server_type,
                                tool_name,
                                tool_arguments
                            )
                            
                            if tool_result.get('success'):
                                result_data = tool_result.get('result', {})
                                # Format result for output
                                if isinstance(result_data, dict):
                                    node_output = json.dumps(result_data, indent=2)
                                else:
                                    node_output = str(result_data)
                                logger.info(f"✅ MCP SERVER: Tool {tool_name} executed successfully")
                            else:
                                error_msg = tool_result.get('error', 'Unknown error')
                                node_output = f"MCP Server {node_name} error: {error_msg}"
                                logger.error(f"❌ MCP SERVER: Tool {tool_name} failed: {error_msg}")
                        
                        # Store node output
                        executed_nodes[node_id] = node_output
                        conversation_history += f"\n{node_name} (MCP Server): {node_output}"
                        
                        # Add message
                        messages.append({
                            'sequence': message_sequence,
                            'agent_name': node_name,
                            'agent_type': 'MCPServer',
                            'content': node_output,
                            'message_type': 'mcp_server_response',
                            'timestamp': timezone.now().isoformat(),
                            'response_time_ms': 0,
                            'metadata': {
                                'server_type': server_type,
                                'tool': tool_request.get('tool') if tool_request else None
                            }
                        })
                        message_sequence += 1
                        
                        # Save execution state
                        execution_record.executed_nodes = executed_nodes
                        execution_record.conversation_history = conversation_history
                        await sync_to_async(execution_record.save)(update_fields=['executed_nodes', 'conversation_history'])
                        
                    except Exception as mcp_error:
                        logger.error(f"❌ MCP SERVER: Node {node_name} failed: {mcp_error}")
                        error_output = f"MCP Server {node_name} error: {str(mcp_error)}"
                        executed_nodes[node_id] = error_output
                        conversation_history += f"\n{node_name} (MCP Server): {error_output}"
                        raise mcp_error
                    
                elif node_type == 'EndNode':
                    # Handle end node
                    end_message = node_data.get('message', 'Workflow completed successfully.')
                    
                    # Store node output for completeness
                    executed_nodes[node_id] = end_message
                    
                    messages.append({
                        'sequence': message_sequence,
                        'agent_name': 'End',
                        'agent_type': 'EndNode',
                        'content': end_message,
                        'message_type': 'workflow_end',
                        'timestamp': timezone.now().isoformat(),
                        'response_time_ms': 0
                    })
                    message_sequence += 1  # Increment for chronological ordering
                    
                else:
                    logger.warning(f"⚠️ ORCHESTRATOR: Unknown node type {node_type}, skipping")
            
            # Calculate execution metrics
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            # Update workflow execution stats using sync_to_async
            def update_workflow_stats():
                workflow.total_executions += 1
                workflow.successful_executions += 1
                workflow.last_executed_at = timezone.now()
                
                # Update average execution time
                if workflow.average_execution_time:
                    workflow.average_execution_time = (
                        (workflow.average_execution_time * (workflow.total_executions - 1) + duration) 
                        / workflow.total_executions
                    )
                else:
                    workflow.average_execution_time = duration
                
                workflow.save()
            
            await sync_to_async(update_workflow_stats)()
            
            # CRITICAL FIX: Get the latest messages_data from database first
            await sync_to_async(execution_record.refresh_from_db)()
            stored_messages = execution_record.messages_data or []
            logger.info(f"🔍 ORCHESTRATOR: Retrieved {len(stored_messages)} stored messages from database")
            
            # CRITICAL FIX: Clean stored messages - remove or fix messages with "Unknown" agent_name
            cleaned_stored_messages = []
            for stored_msg in stored_messages:
                if not isinstance(stored_msg, dict):
                    logger.warning(f"⚠️ ORCHESTRATOR: Skipping non-dict stored message: {type(stored_msg)}")
                    continue
                
                agent_name = stored_msg.get('agent_name', '')
                # Skip messages with "Unknown" or empty agent_name - these are likely malformed
                if not agent_name or agent_name.strip() == '' or agent_name == 'Unknown':
                    # Try to infer from agent_type or content
                    agent_type = stored_msg.get('agent_type', '')
                    if agent_type and agent_type != 'Unknown':
                        stored_msg['agent_name'] = agent_type
                        logger.debug(f"🔧 ORCHESTRATOR: Fixed stored message - inferred agent_name '{agent_type}' from agent_type")
                    else:
                        # Skip messages that can't be fixed
                        logger.warning(f"⚠️ ORCHESTRATOR: Skipping stored message with invalid agent_name: {stored_msg.get('content', '')[:50]}")
                        continue
                
                cleaned_stored_messages.append(stored_msg)
            
            logger.info(f"🔍 ORCHESTRATOR: Cleaned {len(stored_messages)} stored messages to {len(cleaned_stored_messages)} valid messages")
            
            # Find the highest sequence number in cleaned stored messages
            max_stored_sequence = max([msg.get('sequence', -1) for msg in cleaned_stored_messages], default=-1)
            logger.info(f"🔍 ORCHESTRATOR: Max stored sequence: {max_stored_sequence}")
            
            # Merge messages: Start with cleaned stored messages, then add any new messages with updated sequences
            final_messages = cleaned_stored_messages.copy()
            
            # Add workflow messages that aren't already stored, updating their sequences if needed
            for message in messages:
                # CRITICAL FIX: Skip messages that are LLM-formatted (only have 'role' and 'content')
                # These are for LLM consumption only, not for storage in messages_data
                if isinstance(message, dict) and 'role' in message and 'content' in message:
                    # Check if this is an LLM-formatted message (missing agent_name, agent_type, etc.)
                    if 'agent_name' not in message and 'agent_type' not in message:
                        logger.debug(f"⏭️ ORCHESTRATOR: Skipping LLM-formatted message (role: {message.get('role')}) - not for storage")
                        continue
                
                message_sequence = message.get('sequence', -1)
                
                # Check if this message already exists in cleaned stored messages
                already_stored = any(
                    stored_msg.get('sequence') == message_sequence and 
                    stored_msg.get('agent_name') == message.get('agent_name') and
                    stored_msg.get('message_type') == message.get('message_type')
                    for stored_msg in cleaned_stored_messages
                )
                
                if not already_stored:
                    # Ensure message has all required fields before adding
                    if not isinstance(message, dict):
                        logger.warning(f"⚠️ ORCHESTRATOR: Skipping non-dict message: {type(message)}")
                        continue
                    
                    # CRITICAL FIX: Require proper agent_name - skip messages without it or with "Unknown"
                    # Messages without agent_name are likely LLM-formatted or malformed
                    agent_name = message.get('agent_name')
                    
                    # Check if agent_name is missing, empty, or "Unknown"
                    if not agent_name or not isinstance(agent_name, str) or agent_name.strip() == '' or agent_name.strip() == 'Unknown':
                        # Try to infer from agent_type if available
                        agent_type = message.get('agent_type', '')
                        if agent_type and agent_type != 'Unknown' and agent_type.strip() != '':
                            agent_name = agent_type
                            logger.debug(f"🔧 ORCHESTRATOR: Inferred agent_name '{agent_name}' from agent_type")
                        else:
                            # Skip messages without proper agent_name - these shouldn't be stored
                            logger.warning(f"⚠️ ORCHESTRATOR: Skipping message without proper agent_name (agent_type: {agent_type}): {message.get('content', '')[:50]}")
                            continue
                    
                    # Final check: reject "Unknown" even after inference
                    if agent_name.strip() == 'Unknown':
                        logger.warning(f"⚠️ ORCHESTRATOR: Skipping message with 'Unknown' agent_name: {message.get('content', '')[:50]}")
                        continue
                    
                    # Ensure required fields have proper values (not "Unknown" defaults)
                    message['agent_name'] = agent_name.strip()
                    if 'agent_type' not in message or not message.get('agent_type') or message.get('agent_type') == 'Unknown':
                        # Try to infer from agent_name if it's a known node type
                        if 'Start' in agent_name or agent_name == 'Start':
                            message['agent_type'] = 'StartNode'
                        elif 'End' in agent_name or agent_name == 'End':
                            message['agent_type'] = 'EndNode'
                        else:
                            message['agent_type'] = 'AssistantAgent'  # Default to AssistantAgent instead of Unknown
                    if 'message_type' not in message or message.get('message_type') is None:
                        message['message_type'] = 'chat'
                    if 'content' not in message:
                        message['content'] = ''
                    if 'timestamp' not in message:
                        message['timestamp'] = timezone.now().isoformat()
                    
                    # If this is a workflow message (like EndNode) that needs to be added after reflection
                    if message_sequence <= max_stored_sequence:
                        # Update sequence to come after all stored messages
                        message['sequence'] = max_stored_sequence + 1
                        max_stored_sequence += 1
                        logger.info(f"➕ ORCHESTRATOR: Updated sequence for {message.get('agent_name')} to {message['sequence']}")
                    
                    # Final validation before adding - ensure agent_name is not "Unknown"
                    if message.get('agent_name', '').strip() == 'Unknown':
                        logger.error(f"❌ ORCHESTRATOR: CRITICAL - Attempted to add message with 'Unknown' agent_name! Content: {message.get('content', '')[:50]}")
                        logger.error(f"❌ ORCHESTRATOR: Message data: {message}")
                        continue
                    
                    final_messages.append(message)
                    logger.info(f"➕ ORCHESTRATOR: Added missing message: {message.get('agent_name')} ({message.get('message_type')}) seq:{message.get('sequence')}")
            
            # Sort by sequence to maintain chronological order
            final_messages.sort(key=lambda x: x.get('sequence', 0))
            
            execution_record.messages_data = final_messages
            logger.info(f"✅ ORCHESTRATOR: Merged messages - final count: {len(final_messages)} messages")
            
            # Update execution record with final details
            execution_record.status = WorkflowExecutionStatus.COMPLETED
            execution_record.end_time = end_time
            execution_record.duration_seconds = duration
            execution_record.total_messages = len(final_messages)
            execution_record.total_agents_involved = len(agents_involved)
            execution_record.average_response_time_ms = total_response_time / len(agents_involved) if agents_involved else 0
            execution_record.providers_used = providers_used
            execution_record.conversation_history = conversation_history
            execution_record.result_summary = f"Successfully executed {len(execution_sequence)} nodes with {len(agents_involved)} agents"
            
            # Debug logging for execution completion
            logger.info(f"🔍 ORCHESTRATOR: Final execution stats - Messages: {len(final_messages)}, Agents: {len(agents_involved)}, Status: {execution_record.status}")
            logger.info(f"🔍 ORCHESTRATOR: Agents involved: {list(agents_involved)}")
            
            await sync_to_async(execution_record.save)()
            logger.info(f"✅ ORCHESTRATOR: Execution record saved with status: {execution_record.status}")
            logger.info(f"💾 ORCHESTRATOR: Saved final {len(final_messages)} messages to execution record")
            
            # ✅ SAVE MESSAGES TO DATABASE
            await self._save_messages_to_database(final_messages, execution_record)
            
            # Return execution results
            execution_result = {
                'execution_id': execution_id,
                'workflow_id': str(workflow_id),
                'workflow_name': workflow_name,
                'status': 'completed',
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration,
                'total_messages': len(final_messages),
                'total_agents_involved': len(agents_involved),
                'average_response_time_ms': total_response_time / len(agents_involved) if agents_involved else 0,
                'providers_used': providers_used,
                'conversation_history': conversation_history,
                'messages': final_messages,
                'result_summary': f"Successfully executed {len(execution_sequence)} nodes with {len(agents_involved)} agents"
            }
            
            logger.info(f"✅ ORCHESTRATOR: REAL workflow execution completed successfully - {len(final_messages)} total messages logged")
            logger.info(f"📊 MESSAGE COUNT VERIFICATION: Expected ~{len(execution_sequence)} nodes, logged {len(final_messages)} messages")

            # Structured experiment log for workflow execution performance (sequential vs parallel)
            try:
                # Extract configuration: agent count and RAG status
                nodes = graph_json.get('nodes', [])
                agent_count = sum(1 for node in nodes if node.get('type') in ['AssistantAgent', 'DelegateAgent'])
                has_rag = any(
                    node.get('data', {}).get('doc_aware', False) 
                    for node in nodes 
                    if node.get('type') == 'AssistantAgent'
                )
                
                configuration = {
                    "agent_count": agent_count,
                    "total_nodes": len(nodes),
                    "has_rag": has_rag,
                    "is_deployment": is_deployment,
                }
                
                # Extract evaluation_id from deployment_context if available
                evaluation_id_value = ''
                if deployment_context and isinstance(deployment_context, dict):
                    evaluation_id_value = deployment_context.get('evaluation_id', '')
                
                exp_payload = {
                    "experiment": "workflow_execution",
                    "workflow_id": str(workflow_id),
                    "workflow_name": workflow_name,
                    "project_id": str(project_id),
                    "execution_id": execution_id,
                    "is_deployment": is_deployment,
                    "evaluation_id": evaluation_id_value,  # Include in payload for logging
                    "duration_s": duration,
                    "total_nodes": len(nodes),
                    "parallel_batches": parallel_batches,
                    "parallel_nodes_executed": parallel_nodes_executed,
                    "sequential_nodes_executed": sequential_nodes_executed,
                }
                
                # Log with deployment/evaluation context
                if is_deployment:
                    logger.info(f"🚀 EXP_METRIC_WORKFLOW_EXECUTION [DEPLOYMENT] | {json.dumps(exp_payload, default=str)}")
                elif evaluation_id_value:
                    logger.info(f"📊 EXP_METRIC_WORKFLOW_EXECUTION [EVALUATION:{evaluation_id_value}] | {json.dumps(exp_payload, default=str)}")
                else:
                    logger.info(f"EXP_METRIC_WORKFLOW_EXECUTION | {json.dumps(exp_payload, default=str)}")
                
                # Store in database
                logger.info(f"📊 METRIC SAVE CHECK: project_id={project_id}, execution_id={execution_id}, will_save={bool(project_id)}")
                try:
                    from users.models import IntelliDocProject, ExperimentMetric
                    
                    # evaluation_id_value already extracted above
                    
                    def save_metric():
                        try:
                            project_obj = IntelliDocProject.objects.get(project_id=project_id)
                            logger.info(f"📊 METRIC SAVE: Project found, creating ExperimentMetric for workflow_execution...")
                            metric = ExperimentMetric.objects.create(
                                project=project_obj,
                                experiment_type='workflow_execution',
                                metric_data=exp_payload,
                                configuration=configuration,
                                execution_id=execution_id,
                                evaluation_id=evaluation_id_value,
                            )
                            logger.info(f"✅ Stored workflow execution experiment metric: id={metric.id}, project={project_id}, execution={execution_id}, evaluation={evaluation_id_value or 'N/A'}")
                            return metric.id
                        except IntelliDocProject.DoesNotExist:
                            logger.warning(f"⚠️ Could not save experiment metric: Project {project_id} not found")
                            return None
                        except Exception as e:
                            logger.error(f"❌ Failed to save experiment metric to database: {e}", exc_info=True)
                            import traceback
                            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                            return None
                    
                    # Use sync_to_async for database write
                    metric_id = await sync_to_async(save_metric)()
                    if metric_id:
                        logger.info(f"✅ METRIC SAVE SUCCESS: Workflow execution metric saved with ID {metric_id}")
                    else:
                        logger.warning(f"⚠️ METRIC SAVE FAILED: Metric was not saved (check logs above)")
                except Exception as db_error:
                    logger.error(f"❌ Failed to store experiment metric in database: {db_error}", exc_info=True)
                    import traceback
                    logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            except Exception as metric_error:
                logger.error(f"❌ EXP_METRIC_WORKFLOW_EXECUTION: Failed to log metrics: {metric_error}")
            
            # Debug: Log all message types for verification
            message_types = [msg.get('message_type', 'unknown') for msg in final_messages if isinstance(msg, dict)]
            agent_names = [msg.get('agent_name', 'N/A') for msg in final_messages if isinstance(msg, dict)]
            logger.info(f"📋 MESSAGE TYPES: {message_types}")
            logger.info(f"👥 AGENT NAMES: {agent_names}")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"❌ ORCHESTRATOR: REAL workflow execution failed: {e}")
            
            # Update workflow stats for failed execution using sync_to_async
            def update_failed_stats():
                workflow.total_executions += 1
                workflow.last_executed_at = timezone.now()
                workflow.save()
            
            await sync_to_async(update_failed_stats)()
            
            # Update existing execution record for failure
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            execution_record.status = 'failed'
            execution_record.end_time = end_time
            execution_record.duration_seconds = duration
            execution_record.error_message = str(e)
            await sync_to_async(execution_record.save)()
            
            return {
                'execution_id': execution_id,
                'workflow_id': str(workflow_id),
                'workflow_name': workflow_name,
                'status': 'failed',
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration,
                'total_messages': 0,
                'total_agents_involved': 0,
                'average_response_time_ms': 0,
                'providers_used': [],
                'conversation_history': '',
                'messages': [],
                'error_message': str(e),
                'result_summary': f"Execution failed: {str(e)}"
            }
    
    async def continue_workflow_execution(self, workflow, execution_record, execution_sequence, start_position, executed_nodes, deployment_context: Optional[Dict[str, Any]] = None):
        """
        Continue workflow execution from a specific position (used after reflection completion)
        
        Args:
            workflow: The workflow being executed
            execution_record: The execution record to continue
            execution_sequence: The execution sequence
            start_position: Position to start from
            executed_nodes: Dictionary of executed nodes
            deployment_context: Optional deployment context for UserProxyAgent handling
        """
        logger.info(f"▶️ CONTINUE WORKFLOW: Resuming from position {start_position} with {len(execution_sequence) - start_position} remaining nodes")
        
        # Check if this is a deployment context by checking DeploymentSession
        if not deployment_context:
            deployment_context = await self._get_deployment_context_from_execution(execution_record)
        
        is_deployment = deployment_context is not None and deployment_context.get('is_deployment', False)
        
        # Get workflow data
        workflow_id = await sync_to_async(lambda: workflow.workflow_id)()
        graph_json = await sync_to_async(lambda: workflow.graph_json)()
        project = await sync_to_async(lambda: workflow.project)()
        
        # Load existing state from execution record
        conversation_history = execution_record.conversation_history or ""
        messages = execution_record.messages_data or []
        agents_involved = set()
        total_response_time = 0
        providers_used = []
        
        # Initialize message sequence manager
        message_manager = MessageSequenceManager(messages)
        
        try:
            # Execute remaining nodes in sequence
            for node_index in range(start_position, len(execution_sequence)):
                # Check if execution has been stopped
                await sync_to_async(execution_record.refresh_from_db)()
                if execution_record.status == WorkflowExecutionStatus.STOPPED:
                    logger.info(f"🛑 CONTINUE WORKFLOW: Execution {execution_record.execution_id} has been stopped, terminating")
                    return {
                        'status': 'stopped',
                        'message': 'Workflow execution was stopped by user',
                        'execution_id': execution_record.execution_id
                    }
                
                node = execution_sequence[node_index]
                node_type = node.get('type')
                node_data = node.get('data', {})
                node_name = node_data.get('name', f'Node_{node.get("id", "unknown")}')
                node_id = node.get('id')
                
                # CRITICAL FIX: Refresh executed_nodes from database to get latest state
                executed_nodes = execution_record.executed_nodes or {}
                
                # CRITICAL FIX: Check if node has already been executed
                # Skip StartNode and EndNode as they don't have outputs in executed_nodes
                if node_type not in ['StartNode', 'EndNode'] and node_id in executed_nodes:
                    logger.info(f"⏭️ CONTINUE WORKFLOW: Skipping {node_name} (node_id: {node_id}) - already executed")
                    continue
                
                logger.info(f"🎯 CONTINUE WORKFLOW: Executing node {node_name} (type: {node_type}) at position {node_index}")
                
                if node_type in ['AssistantAgent', 'UserProxyAgent', 'GroupChatManager', 'DelegateAgent']:
                    # CRITICAL FIX: Only skip the specific UserProxyAgent that was just processed
                    # Check if this is the UserProxyAgent that just provided human input
                    if node_type == 'UserProxyAgent' and node_data.get('require_human_input', True):
                        # Refresh execution record to get latest state
                        await sync_to_async(execution_record.refresh_from_db)()
                        
                        # Check if this UserProxyAgent was the one that just provided input
                        awaiting_agent = execution_record.awaiting_human_input_agent or ""
                        human_input_context = execution_record.human_input_context or {}
                        reflection_source = human_input_context.get('reflection_source')
                        
                        # CRITICAL FIX: Only skip if:
                        # 1. This is a regular UserProxyAgent (not reflection) AND it matches the awaiting agent AND awaiting_agent is not empty
                        # 2. We should NOT skip UserProxyAgent nodes that are in the main workflow sequence after reflection completes
                        #    because the reflection context has been cleared
                        # ROOT CAUSE FIX: Use node_id instead of node_name for accurate matching
                        user_proxy_agent_id_from_context = execution_record.human_input_agent_id
                        should_skip = False
                        if not reflection_source and awaiting_agent and user_proxy_agent_id_from_context:
                            # Regular UserProxyAgent - skip only if it's the one that just provided input
                            # AND we're still in a regular human input context (not after reflection)
                            # CRITICAL FIX: Use node_id for matching, not node_name
                            if node_id == user_proxy_agent_id_from_context:
                                should_skip = True
                                logger.info(f"⏭️ CONTINUE WORKFLOW: Skipping UserProxyAgent {node_name} (node_id: {node_id}) - just processed regular human input")
                        elif reflection_source and awaiting_agent and user_proxy_agent_id_from_context:
                            # Reflection workflow - but if context is cleared, don't skip
                            # Only skip if we're still in the reflection context
                            # CRITICAL FIX: Use node_id for matching, not node_name
                            if node_id == user_proxy_agent_id_from_context:
                                # Check if this is still an active reflection context
                                # If human_input_context is empty or cleared, don't skip
                                if human_input_context and human_input_context.get('reflection_source'):
                                    should_skip = True
                                    logger.info(f"⏭️ CONTINUE WORKFLOW: Skipping UserProxyAgent {node_name} (node_id: {node_id}) - just processed reflection input")
                                else:
                                    # CRITICAL FIX: Check if UserProxyAgent was already executed via reflection
                                    # If it's in executed_nodes, skip it even if context is cleared
                                    if node_id in executed_nodes:
                                        should_skip = True
                                        logger.info(f"⏭️ CONTINUE WORKFLOW: Skipping UserProxyAgent {node_name} (node_id: {node_id}) - already executed via reflection")
                                    else:
                                        logger.info(f"✅ CONTINUE WORKFLOW: UserProxyAgent {node_name} (node_id: {node_id}) was in reflection but context cleared - will execute in main workflow")
                        
                        if should_skip:
                            continue
                        else:
                            # CRITICAL FIX: Check if this UserProxyAgent requires human input
                            # If it does, pause for human input instead of executing as regular agent
                            if node_data.get('require_human_input', True):
                                # Get input mode (default to 'user' for backward compatibility)
                                input_mode = node_data.get('input_mode', 'user')
                                
                                # Admin Input Mode: Always use internal pause mechanism (admin UI)
                                if input_mode == 'admin':
                                    logger.info(f"👤 ADMIN INPUT: UserProxyAgent {node_name} requires admin input (continue, input_mode=admin)")
                                    
                                    # PAUSE WORKFLOW - Use internal pause mechanism
                                    human_input_data = await self.human_input_handler.pause_for_human_input(
                                        workflow, node, executed_nodes, conversation_history, execution_record
                                    )
                                    
                                    # If in deployment context, also store in deployment session for admin to provide input
                                    if is_deployment and deployment_context:
                                        session_id = deployment_context.get('session_id')
                                        if session_id:
                                            last_message = self._extract_last_conversation_message(messages, conversation_history)
                                            await self._store_deployment_pause_state(
                                                session_id, execution_record, node_id, node_name, last_message
                                            )
                                            logger.info(f"💾 DEPLOYMENT: Stored admin input pause state in session {session_id[:8]}")
                                    
                                    return human_input_data  # Return paused state
                                
                                # User Input Mode: Check context
                                elif input_mode == 'user':
                                    # In deployment context: Use deployment pause mechanism (client-side)
                                    if is_deployment and deployment_context:
                                        logger.info(f"👤 DEPLOYMENT: UserProxyAgent {node_name} requires user input in deployment context (continue)")
                                        
                                        # Extract the last conversation message
                                        last_message = self._extract_last_conversation_message(messages, conversation_history)
                                        
                                        # Get the description from UserProxyAgent node data (default to "USER INPUT REQUIRED")
                                        agent_description = node_data.get('description', 'USER INPUT REQUIRED')
                                        if not agent_description or not agent_description.strip():
                                            agent_description = 'USER INPUT REQUIRED'
                                        
                                        # Find input sources (connected agents that feed into this UserProxyAgent)
                                        # This is needed to properly update the execution record
                                        input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                                        aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
                                        
                                        # Update execution record to indicate human input required
                                        # This is critical for resume_workflow_with_human_input to find the execution
                                        # Store input_mode in context so we can filter deployment executions from admin UI
                                        aggregated_context['input_mode'] = input_mode
                                        aggregated_context['is_deployment'] = True
                                        await sync_to_async(self.human_input_handler.update_execution_for_human_input)(
                                            execution_record, node_id, node_name, aggregated_context
                                        )
                                        
                                        # Store execution state in deployment session (non-blocking)
                                        session_id = deployment_context.get('session_id')
                                        if session_id:
                                            await self._store_deployment_pause_state(
                                                session_id, execution_record, node_id, node_name, last_message
                                            )
                                        
                                        # Return special response indicating human input is required
                                        return {
                                            'status': 'awaiting_human_input',
                                            'execution_id': execution_record.execution_id,
                                            'agent_name': node_name,
                                            'agent_id': node_id,
                                            'human_input_required': True,
                                            'title': agent_description.strip(),
                                            'last_conversation_message': last_message,
                                            'message': f'UserProxyAgent {node_name} requires your input',
                                            'conversation_history': conversation_history
                                        }
                                    else:
                                        # In admin UI context: Use internal pause mechanism (for testing)
                                        logger.info(f"👤 USER INPUT: UserProxyAgent {node_name} requires user input in admin UI (continue)")
                                        
                                        # PAUSE WORKFLOW - Use internal pause mechanism
                                        human_input_data = await self.human_input_handler.pause_for_human_input(
                                            workflow, node, executed_nodes, conversation_history, execution_record
                                        )
                                        return human_input_data  # Return paused state
                                else:
                                    # Unknown input_mode, default to user input behavior
                                    logger.warning(f"⚠️ USERPROXY: Unknown input_mode '{input_mode}', defaulting to user input behavior")
                                    # Fall through to regular pause
                                    logger.info(f"👤 CONTINUE WORKFLOW: UserProxyAgent {node_name} requires human input - pausing workflow")
                                    
                                    # PAUSE WORKFLOW - Same as in execute_workflow
                                    human_input_data = await self.human_input_handler.pause_for_human_input(
                                        workflow, node, executed_nodes, conversation_history, execution_record
                                    )
                                    return human_input_data  # Return paused state
                            else:
                                logger.info(f"✅ CONTINUE WORKFLOW: Processing UserProxyAgent {node_name} - not the one that was just processed, and doesn't require human input")
                    
                    # Handle agent nodes with real LLM calls
                    agent_config = {
                        'llm_provider': node_data.get('llm_provider', 'openai'),
                        'llm_model': node_data.get('llm_model', 'gpt-3.5-turbo'),
                        'temperature': node_data.get('temperature', 0.7)  # CRITICAL FIX: Include temperature to avoid KeyError
                    }
                    
                    # Get LLM provider for this agent
                    llm_provider = await self.llm_provider_manager.get_llm_provider(agent_config, project)
                    if not llm_provider:
                        raise Exception(f"Failed to create LLM provider for agent {node_name}")
                    
                    # Execute regular agent
                    logger.info(f"🤖 CONTINUE WORKFLOW: Executing regular agent {node_name} (type: {node_type})")
                    
                    # Find input sources
                    input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                    
                    # CRITICAL FIX: Validate all required inputs are available before executing
                    # This includes checking if reflection responses are in executed_nodes
                    if len(input_sources) > 0:
                        missing_inputs = []
                        for input_source in input_sources:
                            source_id = input_source.get('source_id')
                            source_name = input_source.get('name', source_id)
                            if source_id not in executed_nodes:
                                missing_inputs.append(f"{source_name} (node_id: {source_id})")
                        
                        if missing_inputs:
                            error_msg = f"Cannot execute {node_name}: Missing required inputs from {', '.join(missing_inputs)}. Available inputs: {list(executed_nodes.keys())}"
                            logger.warning(f"⏳ CONTINUE WORKFLOW: {error_msg} - waiting for dependencies")
                            # CRITICAL FIX: Don't raise exception, skip this node and continue
                            # It will be checked again in the next iteration when dependencies are satisfied
                            continue
                    
                    if len(input_sources) > 1:
                        # Multi-input mode
                        logger.info(f"📥 CONTINUE WORKFLOW: Agent {node_name} has {len(input_sources)} input sources - using multi-input mode")
                        aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
                        # CRITICAL FIX: Use craft_conversation_prompt_with_docaware for multi-input (same as main execution)
                        prompt_result = await self.chat_manager.craft_conversation_prompt_with_docaware(
                            aggregated_context, node, str(project.project_id), conversation_history
                        )
                        # Handle dict return with potential file_references (Full Document Mode)
                        llm_messages = prompt_result.get('messages', prompt_result) if isinstance(prompt_result, dict) else prompt_result
                        
                        # Apply file reference formatting if file attachments are enabled
                        if isinstance(prompt_result, dict) and prompt_result.get('file_references'):
                            logger.info(f"📎 FILE ATTACHMENTS: Formatting {len(prompt_result['file_references'])} file references for {node_name}")
                            llm_messages = self.chat_manager.format_messages_with_file_refs(
                                llm_messages,
                                prompt_result['file_references'],
                                prompt_result.get('provider', 'openai')
                            )
                    else:
                        # Single-input mode - CRITICAL FIX: Use proper prompt crafting
                        logger.info(f"📥 CONTINUE WORKFLOW: Agent {node_name} has {len(input_sources)} input source - using single-input mode")
                        prompt_result_single = await self.chat_manager.craft_conversation_prompt(
                            conversation_history, node, str(project.project_id)
                        )
                        # Handle dict return with potential file_references (File Attachments)
                        llm_messages = prompt_result_single.get('messages', prompt_result_single) if isinstance(prompt_result_single, dict) else prompt_result_single
                        
                        # Apply file reference formatting if file attachments are enabled
                        if isinstance(prompt_result_single, dict) and prompt_result_single.get('file_references'):
                            logger.info(f"📎 FILE ATTACHMENTS: Formatting {len(prompt_result_single['file_references'])} file references for {node_name}")
                            llm_messages = self.chat_manager.format_messages_with_file_refs(
                                llm_messages,
                                prompt_result_single['file_references'],
                                prompt_result_single.get('provider', 'openai')
                            )
                    
                    # Chat file references (deployment chatbot uploads) — continue path
                    _is_deployment = deployment_context is not None and deployment_context.get('is_deployment', False)
                    if _is_deployment and deployment_context:
                        if deployment_context.get('chat_file_references'):
                            _chat_refs = deployment_context['chat_file_references']
                            _provider = node_data.get('llm_provider', 'openai').lower()
                            logger.info(f"📎 CHAT FILES (continue): Attaching {len(_chat_refs)} session files to {node_name} ({_provider})")
                            llm_messages = self.chat_manager.format_messages_with_file_refs(
                                llm_messages, _chat_refs, _provider
                            )
                        if deployment_context.get('chat_text_attachments'):
                            for _att in deployment_context['chat_text_attachments']:
                                _text_block = f"\n\n--- Attached Document: {_att['filename']} ---\n{_att['text']}\n--- End Document ---"
                                for _msg in reversed(llm_messages):
                                    if _msg.get('role') == 'user':
                                        if isinstance(_msg['content'], str):
                                            _msg['content'] += _text_block
                                        elif isinstance(_msg['content'], list):
                                            for _part in _msg['content']:
                                                if isinstance(_part, dict) and _part.get('type') == 'text':
                                                    _part['text'] += _text_block
                                                    break
                                        break
                            logger.info(f"📎 CHAT TEXT (continue): Injected {len(deployment_context['chat_text_attachments'])} text attachments into {node_name}")

                    # DEBUG: Log messages content for troubleshooting
                    messages_preview = f"{len(llm_messages)} messages" + (f", first message: {llm_messages[0].get('content', '')[:100]}..." if llm_messages and isinstance(llm_messages, list) else "")
                    logger.info(f"🔍 CONTINUE WORKFLOW: Agent {node_name} messages: {messages_preview}")

                    # Make LLM call with structured messages
                    start_time = timezone.now()
                    llm_response = await llm_provider.generate_response(messages=llm_messages)
                    end_time = timezone.now()
                    
                    if llm_response.error:
                        raise Exception(f"LLM error for agent {node_name}: {llm_response.error}")
                    
                    agent_response_text = llm_response.text.strip()
                    response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                    
                    logger.info(f"✅ CONTINUE WORKFLOW: Agent {node_name} completed successfully - response length: {len(agent_response_text)} chars")
                    
                    # Track metrics
                    agents_involved.add(node_name)
                    total_response_time += response_time_ms
                    if agent_config['llm_provider'] not in providers_used:
                        providers_used.append(agent_config['llm_provider'])
                    
                    # Add message with proper sequence
                    message, sequence = message_manager.add_message(
                        agent_name=node_name,
                        agent_type=node_type,
                        content=agent_response_text,
                        message_type='assistant_response',
                        response_time_ms=response_time_ms,
                        token_count=llm_response.token_count,
                        metadata={
                            'llm_provider': agent_config['llm_provider'],
                            'llm_model': agent_config['llm_model'],
                            'temperature': agent_config.get('temperature', 0.7)  # CRITICAL FIX: Use .get() with default for safety
                        }
                    )
                    
                    # Store original response before any reflection processing
                    original_agent_response = agent_response_text
                    
                    # CRITICAL FIX: Check for cross-agent reflection connections
                    # This was missing from continue_workflow_execution, causing AI Assistant 2's
                    # reflection to User Proxy 2 to be skipped
                    try:
                        cross_agent_reflection_edges = []
                        for edge in graph_json.get('edges', []):
                            if (edge.get('source') == node_id and 
                                edge.get('type') == 'reflection' and 
                                edge.get('target') != node_id):  # Cross-agent reflection
                                cross_agent_reflection_edges.append(edge)
                        
                        if cross_agent_reflection_edges:
                            logger.info(f"🔄 CONTINUE WORKFLOW REFLECTION: Found {len(cross_agent_reflection_edges)} cross-agent reflection edges from {node_name}")
                        
                        # Process cross-agent reflections using original response
                        for reflection_edge in cross_agent_reflection_edges:
                            logger.info(f"🔄 CONTINUE WORKFLOW REFLECTION: Processing cross-agent reflection from {node_name}")
                            
                            reflection_result, updated_conversation = await self.reflection_handler.handle_cross_agent_reflection(
                                node, original_agent_response, reflection_edge, graph_json, execution_record, conversation_history, deployment_context
                            )
                            
                            # Check if we're waiting for human input in reflection
                            if reflection_result == 'AWAITING_REFLECTION_INPUT':
                                logger.info(f"👤 CONTINUE WORKFLOW REFLECTION: Pausing workflow - awaiting human input for reflection (admin UI)")
                                # Save current state before returning
                                execution_record.executed_nodes = executed_nodes
                                execution_record.messages_data = message_manager.get_messages()
                                execution_record.conversation_history = conversation_history
                                await sync_to_async(execution_record.save)()
                                return {
                                    'status': 'paused_for_reflection_input',
                                    'conversation_history': updated_conversation,
                                    'message': f'Workflow paused - {execution_record.awaiting_human_input_agent} needs to provide reflection feedback',
                                    'execution_id': execution_record.execution_id
                                }
                            elif reflection_result == 'AWAITING_DEPLOYMENT_INPUT':
                                # User input mode in deployment context - return deployment pause status
                                logger.info(f"👤 CONTINUE WORKFLOW REFLECTION: Pausing workflow - awaiting user input for reflection in deployment")
                                
                                # Get target node info for response
                                target_node_id = execution_record.human_input_agent_id
                                target_node_name = execution_record.awaiting_human_input_agent
                                
                                # Find target node to get description
                                target_node = None
                                for n in graph_json.get('nodes', []):
                                    if n.get('id') == target_node_id:
                                        target_node = n
                                        break
                                
                                target_data = target_node.get('data', {}) if target_node else {}
                                agent_description = target_data.get('description', 'USER INPUT REQUIRED')
                                if not agent_description or not agent_description.strip():
                                    agent_description = 'USER INPUT REQUIRED'
                                
                                # Extract last message
                                last_message = self._extract_last_conversation_message(message_manager.get_messages(), updated_conversation)
                                
                                # Store execution state in deployment session
                                session_id = deployment_context.get('session_id') if deployment_context else None
                                if session_id:
                                    await self._store_deployment_pause_state(
                                        session_id, execution_record, target_node_id, target_node_name, last_message
                                    )
                                
                                return {
                                    'status': 'awaiting_human_input',
                                    'execution_id': execution_record.execution_id,
                                    'agent_name': target_node_name,
                                    'agent_id': target_node_id,
                                    'human_input_required': True,
                                    'title': agent_description.strip(),
                                    'last_conversation_message': last_message,
                                    'message': f'UserProxyAgent {target_node_name} requires your input (reflection)',
                                    'conversation_history': updated_conversation
                                }
                            else:
                                # Reflection completed successfully (no human input required)
                                agent_response_text = reflection_result
                                conversation_history = updated_conversation
                                logger.info(f"✅ CONTINUE WORKFLOW REFLECTION: Completed cross-agent reflection - final response length: {len(agent_response_text)} chars")
                    
                    except Exception as reflection_error:
                        logger.error(f"❌ CONTINUE WORKFLOW REFLECTION: Error processing reflection for {node_name}: {reflection_error}")
                        import traceback
                        logger.error(f"❌ CONTINUE WORKFLOW REFLECTION: Traceback: {traceback.format_exc()}")
                        # Continue with original response if reflection fails
                    
                    # Update conversation history and executed nodes (continue path: plain handoff; doc-tool citations not re-parsed here)
                    conversation_history += f"\n{node_name}: {agent_response_text}"
                    executed_nodes[node_id] = pack_executed_output(agent_response_text, None)
                    
                    # CRITICAL FIX: Save executed_nodes to database after each agent execution
                    # This ensures downstream agents can access the output immediately
                    execution_record.executed_nodes = executed_nodes
                    await sync_to_async(execution_record.save)(update_fields=['executed_nodes'])
                    logger.info(f"💾 CONTINUE WORKFLOW: Saved executed_nodes for {node_name} (node_id: {node_id}) to database")
                    
                    # CRITICAL FIX: Save messages_data to database after each agent execution
                    # This ensures messages are persisted even if the workflow pauses or encounters an error
                    execution_record.messages_data = message_manager.get_messages()
                    execution_record.conversation_history = conversation_history
                    await sync_to_async(execution_record.save)(update_fields=['messages_data', 'conversation_history'])
                    logger.info(f"💾 CONTINUE WORKFLOW: Saved messages_data for {node_name} to database")
                    
                elif node_type == 'EndNode':
                    # Handle end node
                    end_message = node_data.get('message', 'Workflow completed successfully.')
                    executed_nodes[node_id] = end_message
                    
                    message, sequence = message_manager.add_message(
                        agent_name='End',
                        agent_type='EndNode',
                        content=end_message,
                        message_type='workflow_end'
                    )
            
            # Calculate final metrics
            end_time = timezone.now()
            duration = (end_time - execution_record.start_time).total_seconds()
            
            # Update execution record with completion
            execution_record.status = 'completed'
            execution_record.end_time = end_time
            execution_record.duration_seconds = duration
            execution_record.conversation_history = conversation_history
            execution_record.messages_data = message_manager.get_messages()
            execution_record.total_messages = len(message_manager.get_messages())
            execution_record.total_agents_involved = len(agents_involved)
            execution_record.providers_used = providers_used
            execution_record.executed_nodes = executed_nodes
            execution_record.result_summary = f"Continued workflow execution completed with {len(agents_involved)} agents"
            await sync_to_async(execution_record.save)()
            
            logger.info(f"✅ CONTINUE WORKFLOW: Execution completed successfully - {len(message_manager.get_messages())} total messages")
            
            return {
                'status': 'success',
                'message': 'Workflow execution continued and completed successfully',
                'execution_id': execution_record.execution_id,
                'updated_conversation': conversation_history,
                'conversation_history': conversation_history,
                'workflow_completed': True,
                'total_agents': len(agents_involved),
                'final_response': agent_response_text if agents_involved else "Workflow completed",
                'messages': message_manager.get_messages(),  # Include messages for deployment executor
                'response': agent_response_text if agents_involved else "Workflow completed"
            }
            
        except Exception as e:
            logger.error(f"❌ CONTINUE WORKFLOW: Continuation failed: {e}")
            
            # Update execution record for failure
            execution_record.status = 'failed'
            execution_record.end_time = timezone.now()
            execution_record.duration_seconds = (execution_record.end_time - execution_record.start_time).total_seconds()
            execution_record.error_message = str(e)
            execution_record.result_summary = f"Workflow continuation failed: {str(e)}"
            await sync_to_async(execution_record.save)()
            
            return {
                'status': 'failed',
                'message': f'Workflow continuation failed: {str(e)}',
                'execution_id': execution_record.execution_id,
                'error': str(e)
            }
    
    # ------------------------------------------------------------------
    # Document Tool Calling — plan → tool loop → synthesise
    # ------------------------------------------------------------------
    MAX_TOOL_ITERATIONS = 20
    MAX_TOOL_CALLS_PER_TURN = 50

    async def _execute_doc_tool_calling(
        self,
        node: Dict[str, Any],
        node_name: str,
        node_type: str,
        llm_messages: List[Dict[str, Any]],
        llm_provider,
        agent_config: Dict[str, Any],
        project_id: str,
        messages: list,
        message_sequence: int,
        execution_record,
        event_callback=None,
    ) -> str:
        """
        Run the three-phase document-tool-calling loop for an agent:
        1. Planning — LLM produces a checklist
        2. Tool loop — LLM selects documents via tool calls; results go to notebook
        3. Synthesis — LLM reviews notebook and answers the original query
        """
        import json as _json
        from . import document_tool_service
        from .chat_manager import ChatManager

        provider_name = agent_config.get("llm_provider", "openai")
        model_name = agent_config.get("llm_model", "gpt-4")

        # ---- Build document tools ----
        node_data = node.get("data", {})
        tools, tool_map, title_map = [], {}, {}
        doc_tool_selected = None
        if node_data.get("doc_tool_calling"):
            doc_tool_selected = node_data.get("doc_tool_calling_documents")
            tools, tool_map, title_map = await document_tool_service.build_document_tools(
                project_id, selected_filenames=doc_tool_selected
            )
            tools.extend(document_tool_service.build_document_info_tools())

        # ---- Pre-warm: upload all tool documents to LLM provider in parallel ----
        # Skip for Ollama — local model reads extraction_text directly
        if tool_map and provider_name != 'ollama':
            try:
                from .llm_file_service import LLMFileUploadService
                from users.models import ProjectDocument as _PWDoc
                _prewarm_project = await sync_to_async(lambda: workflow.project)()
                _file_svc = LLMFileUploadService(_prewarm_project)
                _doc_ids = list(set(tool_map.values()))
                _prewarm_docs = await sync_to_async(list)(_PWDoc.objects.filter(document_id__in=_doc_ids))
                _upload_tasks = [_file_svc._upload_to_provider(doc, provider_name) for doc in _prewarm_docs]
                _results = await asyncio.gather(*_upload_tasks, return_exceptions=True)
                _ok = sum(1 for r in _results if not isinstance(r, Exception))
                logger.info(f"🔥 PRE-WARM: Uploaded {_ok}/{len(_prewarm_docs)} documents to {provider_name}")
            except Exception as pw_err:
                logger.warning(f"⚠️ PRE-WARM: Failed to pre-warm uploads: {pw_err}")
        elif tool_map and provider_name == 'ollama':
            logger.info(f"⏭️ PRE-WARM: Skipped for Ollama (local model reads text directly)")

        # ---- Build web search tool(s) ----
        # URL mode: content is already injected into the context window by
        # chat_manager — no tool registration needed here.
        _ws_handler = getattr(self.chat_manager, 'websearch_handler', None)
        url_tool_map: Dict[str, str] = {}
        ws_tool = None
        has_web_tools = False
        if _ws_handler:
            if _ws_handler.get_websearch_mode(node) == 'urls':
                logger.info("🌐 WEB TOOLS: URL mode — content injected into context window, no tool needed")
            else:
                ws_tool = _ws_handler.build_websearch_tool(node)
                if ws_tool:
                    tools.append(ws_tool)
                    title_map[ws_tool["function"]["name"]] = "Web Search"
                    has_web_tools = True

        # ---- Build DocAware search tool ----
        _da_handler = getattr(self.chat_manager, 'docaware_handler', None)
        da_tool = _da_handler.build_docaware_tool(node) if _da_handler else None
        if da_tool:
            tools.append(da_tool)
            title_map[da_tool["function"]["name"]] = "Document Search"

        if not tools:
            logger.warning(f"⚠️ TOOL CALLING: No tools available for project {project_id}; falling back to normal call")
            resp = await llm_provider.generate_response(messages=llm_messages)
            if resp.error:
                raise Exception(f"Agent {node_name} error: {resp.error}")
            return resp.text.strip(), []

        tool_descriptions = "\n".join(
            f"- {t['function']['name']}: {t['function']['description'][:200]}"
            for t in tools
        )

        has_doc_tools = bool(tool_map)

        memory_section = ""
        summary_rows = []
        if has_doc_tools:
            memory_context_lines = []
            try:
                from users.models import ProjectDocumentSummary
                summary_rows = await sync_to_async(list)(
                    ProjectDocumentSummary.objects.filter(
                        document__project__project_id=project_id,
                    ).values_list(
                        "document__document_id", "memory", "citation",
                        "short_summary", "document__original_filename",
                    )
                )
                for did, mem, cit, short_sum, orig_filename in summary_rows:
                    if not mem or not isinstance(mem, list) or len(mem) == 0:
                        continue
                    doc_label = str(did)[:8]
                    if cit and isinstance(cit, dict) and cit.get("title"):
                        doc_label = cit["title"][:60]
                    topics = [e.get("query", "")[:50] for e in mem if e.get("query")]
                    memory_context_lines.append(
                        f"  - {doc_label}: {len(mem)} prior insights on: {'; '.join(topics)}"
                    )
            except Exception as e:
                logger.warning(f"⚠️ DOC TOOL CALLING: Could not fetch memory context: {e}")

            if memory_context_lines:
                memory_section = (
                    "\n\nPRIOR KNOWLEDGE (from previous analyses):\n"
                    + "\n".join(memory_context_lines)
                    + "\n\nUse this prior knowledge to ask more targeted, "
                    "non-redundant questions."
                )

        # ---- Build document summary section for planning ----
        doc_summary_section = ""
        if has_doc_tools:
            docid_to_toolname = {did: tname for tname, did in tool_map.items()}
            summary_lines = []
            for did, mem, cit, short_sum, orig_filename in summary_rows:
                if not short_sum or not short_sum.strip():
                    continue
                tool_name = docid_to_toolname.get(str(did))
                if not tool_name:
                    continue  # not in active tool set
                doc_title = (
                    cit.get("title") if cit and isinstance(cit, dict) and cit.get("title")
                    else orig_filename or str(did)[:8]
                )
                summary_lines.append(
                    f"  [{tool_name}] {doc_title}:\n    {short_sum.strip()}"
                )
                if len(summary_lines) >= 20:
                    break
            if summary_lines:
                doc_summary_section = (
                    "\n\nDOCUMENT SUMMARIES (use these to decide which documents to consult):\n"
                    + "\n\n".join(summary_lines)
                )

        # ---- Phase 1: Planning (controlled by plan_mode toggle) ----
        plan_mode_enabled = node_data.get("plan_mode", True)  # default ON for backward compat
        plan_text = ""

        if plan_mode_enabled:
            planning_messages = list(llm_messages)  # shallow copy
            if has_doc_tools:
                planning_content = (
                    "Before answering, create a numbered plan of which documents "
                    "you will consult and what information you need from each.\n\n"
                    "Available documents (as tools you can call):\n"
                    f"{tool_descriptions}"
                    f"{doc_summary_section}"
                    f"{memory_section}\n\n"
                    "Output ONLY the plan as a numbered list."
                )
            else:
                planning_content = (
                    "Before answering, create a numbered plan of what information "
                    "you need to find using the available tools.\n\n"
                    "Available tools:\n"
                    f"{tool_descriptions}\n\n"
                    "Output ONLY the plan as a numbered list."
                )
            planning_messages.append({
                "role": "user",
                "content": planning_content,
            })
            plan_response = await llm_provider.generate_response(messages=planning_messages)
            if plan_response.error:
                raise Exception(f"Agent {node_name} planning error: {plan_response.error}")

            plan_text = plan_response.text.strip()
            logger.info(f"📋 DOC TOOL CALLING [{node_name}]: Plan created ({len(plan_text)} chars)")

            if event_callback:
                event_callback("planning", {"agent": node_name, "content": plan_text})

            messages.append({
                "sequence": message_sequence,
                "agent_name": node_name,
                "agent_type": node_type,
                "content": plan_text,
                "message_type": "tool_plan",
                "timestamp": timezone.now().isoformat(),
                "response_time_ms": getattr(plan_response, "response_time_ms", 0),
                "token_count": getattr(plan_response, "token_count", None),
                "metadata": {
                    "llm_provider": provider_name,
                    "llm_model": model_name,
                    "phase": "planning",
                },
            })
            message_sequence += 1
            execution_record.messages_data = messages
            await sync_to_async(execution_record.save)()
        else:
            logger.info(f"⚡ DOC TOOL CALLING [{node_name}]: Plan mode disabled — skipping planning phase")

        # ---- Phase 2: Tool calling loop ----
        notebook: List[Dict[str, Any]] = []

        # Build a document title reference for the synthesis prompt
        title_ref_lines = []
        for tname, ttitle in title_map.items():
            if ttitle != tname:
                title_ref_lines.append(f"  {tname} → {ttitle}")
        title_ref_section = ""
        if title_ref_lines:
            title_ref_section = (
                "\n\nDocument reference (use titles, not tool names):\n"
                + "\n".join(title_ref_lines)
            )

        # Start the tool-calling conversation from the original messages
        tool_conv = list(llm_messages)
        _plan_intro = f"Here is your plan:\n{plan_text}\n\n" if plan_mode_enabled and plan_text else ""
        tool_conv.append({
            "role": "user",
            "content": (
                f"{_plan_intro}"
                "Use the document tools "
                "to retrieve information. When you have gathered all the "
                "information you need, provide your final answer WITHOUT "
                "calling any more tools.\n\n"
                "IMPORTANT — grounded citations:\n"
                "- Use numbered markers [1], [2], [3], … in the text. Each DISTINCT "
                "claim or passage you rely on must use the NEXT number; do not label "
                "every sentence with [1] unless they all cite the exact same quoted passage.\n"
                "- For each marker [N], the citations JSON below must include ONE object "
                "with \"ref\": N whose \"quoted_text\" is the VERBATIM excerpt from the "
                "document that supports THAT specific sentence (not a generic quote reused "
                "for all markers).\n"
                "- You may reuse the same [N] only when the same passage supports multiple "
                "nearby clauses; otherwise increment N.\n"
                "- Reference documents by their title (not tool name or filename).\n"
                "- IMPORTANT: Include the \"tool_name\" field in each citation so we can link to the document.\n"
                + (
                    "- For citations from web search results, include the source "
                    "\"url\" field and set \"source\": \"web\". For citations from "
                    "project documents, set \"source\": \"document\" (page/section "
                    "are only relevant for document citations).\n"
                    if has_web_tools else ""
                ) +
                "\nAt the END of your response, include a structured citations block (valid JSON array):\n"
                "---CITATIONS---\n"
                + (
                    '[{"ref": 1, "document_title": "Page Title", "quoted_text": "excerpt from web page…", "url": "https://example.com/article", "source": "web"}, '
                    '{"ref": 2, "document_title": "Paper A", "tool_name": "read_doc_paper_a_pdf", "quoted_text": "exact excerpt from document…", "page": 2, "section": "Intro", "source": "document"}]\n'
                    if has_web_tools else
                    '[{"ref": 1, "document_title": "Paper A", "tool_name": "read_doc_paper_a_pdf", "quoted_text": "first exact excerpt…", "page": 2, "section": "Intro"}, '
                    '{"ref": 2, "document_title": "Paper A", "tool_name": "read_doc_paper_a_pdf", "quoted_text": "different excerpt for claim two…", "page": 4, "section": "Methods"}]\n'
                ) +
                "---END_CITATIONS---"
                f"{title_ref_section}"
            ),
        })

        for iteration in range(self.MAX_TOOL_ITERATIONS):
            response = await llm_provider.generate_response(
                messages=tool_conv,
                tools=tools,
            )
            if response.error:
                raise Exception(f"Agent {node_name} tool-loop error (iter {iteration}): {response.error}")

            if not response.tool_calls:
                # LLM finished — this is the synthesis
                if event_callback:
                    event_callback("synthesizing", {"agent": node_name})
                logger.info(f"✅ DOC TOOL CALLING [{node_name}]: Synthesis after {iteration} tool iterations")
                from agent_orchestration.document_tool_service import (
                    _append_citations_block,
                    _parse_citations_block,
                )
                clean_text, raw_citations = _parse_citations_block(response.text.strip())
                title_to_docid = {title_map.get(tn, ""): did for tn, did in tool_map.items() if title_map.get(tn)}

                # ── Citation normalization (same logic as explicit synthesis) ──
                import re as _re

                # Info tool names that should NOT be used as citation sources
                from .document_tool_service import (
                    LIST_FILES_TOOL_NAME, COUNT_FILES_TOOL_NAME,
                    GET_SUMMARIES_TOOL_NAME, FIND_RELEVANT_TOOL_NAME,
                    GET_METADATA_TOOL_NAME,
                )
                _info_tool_names = {
                    LIST_FILES_TOOL_NAME, COUNT_FILES_TOOL_NAME,
                    GET_SUMMARIES_TOOL_NAME, FIND_RELEVANT_TOOL_NAME,
                    GET_METADATA_TOOL_NAME,
                }

                _raw_cit_map: Dict[int, Dict[str, Any]] = {}
                for _c in raw_citations:
                    _r = _c.get("ref")
                    if _r is not None:
                        _raw_cit_map[int(_r)] = _c

                # ── Convert filename-based refs [name.pdf] to numbered [N] ──
                # Build reverse map: filename/title → tool_name for lookup
                _filename_to_tool: Dict[str, str] = {}
                for _tn, _tt in title_map.items():
                    if _tn not in _info_tool_names:
                        _filename_to_tool[_tt.lower()] = _tn
                        # Also map without extension
                        _base = _tt.rsplit('.', 1)[0] if '.' in _tt else _tt
                        _filename_to_tool[_base.lower()] = _tn

                _filename_cit_counter = max((_c.get("ref", 0) for _c in raw_citations), default=0) + 1
                _filename_ref_map: Dict[str, int] = {}  # filename → assigned ref number

                def _replace_filename_ref(_match_obj):
                    nonlocal _filename_cit_counter
                    _ref_text = _match_obj.group(1)
                    # Skip if it's already a number (handled below)
                    if _ref_text.isdigit():
                        return _match_obj.group(0)
                    _key = _ref_text.lower().strip()
                    _matched_tool = _filename_to_tool.get(_key)
                    if not _matched_tool:
                        # Try without extension
                        _base_key = _key.rsplit('.', 1)[0] if '.' in _key else _key
                        _matched_tool = _filename_to_tool.get(_base_key)
                    if not _matched_tool:
                        return _match_obj.group(0)  # Not a known filename
                    if _key not in _filename_ref_map:
                        _filename_ref_map[_key] = _filename_cit_counter
                        # Add to raw_citations
                        raw_citations.append({
                            "ref": _filename_cit_counter,
                            "document_title": title_map.get(_matched_tool, _ref_text),
                            "quoted_text": f"Reference from {title_map.get(_matched_tool, _ref_text)}",
                            "document_id": tool_map.get(_matched_tool),
                            "source": "document",
                        })
                        _filename_cit_counter += 1
                    return f"[{_filename_ref_map[_key]}]"

                # Replace [filename.pdf] and [filename] patterns with [N]
                clean_text = _re.sub(r'\[([^\[\]]{3,80})\]', _replace_filename_ref, clean_text)

                if _filename_ref_map:
                    logger.info(
                        f"📎 FILENAME→NUM: Converted {len(_filename_ref_map)} filename refs to numbered citations"
                    )
                    # Rebuild raw_cit_map with new entries
                    for _c in raw_citations:
                        _r = _c.get("ref")
                        if _r is not None:
                            _raw_cit_map[int(_r)] = _c

                _seen: set = set()
                _ordered_refs: List[int] = []
                for _m in _re.finditer(r'\[(\d+)\]', clean_text):
                    _n = int(_m.group(1))
                    if _n not in _seen:
                        _seen.add(_n)
                        _ordered_refs.append(_n)

                def _find_cit_nb(_ref_num: int) -> Dict[str, Any]:
                    # Only search document-read entries, skip info tools
                    _doc_entries = [e for e in notebook if e.get("tool_name") not in _info_tool_names]
                    for _entry in _doc_entries:
                        _rt = _entry.get("result", "")
                        _match = _re.search(rf'\[{_ref_num}\]\s*"([^"]+)"', _rt)
                        if _match:
                            return {
                                "document_title": title_map.get(_entry["tool_name"], _entry["tool_name"]),
                                "quoted_text": _match.group(1)[:250],
                                "document_id": tool_map.get(_entry["tool_name"]),
                                "source": "document",
                            }
                        _match2 = _re.search(rf'\[{_ref_num}\]\s*([^\[\n]+)', _rt)
                        if _match2:
                            return {
                                "document_title": title_map.get(_entry["tool_name"], _entry["tool_name"]),
                                "quoted_text": _match2.group(1).strip()[:250],
                                "document_id": tool_map.get(_entry["tool_name"]),
                                "source": "document",
                            }
                    # Fallback: use first document-read entry (not info tools)
                    if _doc_entries:
                        _e = _doc_entries[0]
                        return {
                            "document_title": title_map.get(_e["tool_name"], _e["tool_name"]),
                            "quoted_text": f"Reference from {title_map.get(_e['tool_name'], _e['tool_name'])}",
                            "source": "document",
                            "document_id": tool_map.get(_e["tool_name"]),
                        }
                    return {"quoted_text": "Reference", "source": "document"}

                _new_citations: List[Dict[str, Any]] = []
                _old_to_new: Dict[int, int] = {}
                for _new_num, _old_num in enumerate(_ordered_refs, start=1):
                    _old_to_new[_old_num] = _new_num
                    if _old_num in _raw_cit_map:
                        _entry = dict(_raw_cit_map[_old_num])
                        _entry["ref"] = _new_num
                    else:
                        _entry = _find_cit_nb(_old_num)
                        _entry["ref"] = _new_num
                    _new_citations.append(_entry)

                for _old_num in sorted(_old_to_new.keys(), reverse=True):
                    clean_text = clean_text.replace(f"[{_old_num}]", f"[__CITE_{_old_to_new[_old_num]}__]")
                for _new_num in range(1, len(_ordered_refs) + 1):
                    clean_text = clean_text.replace(f"[__CITE_{_new_num}__]", f"[{_new_num}]")

                # Build a reverse lookup: lowercase title/filename → document_id
                _fuzzy_docid: Dict[str, str] = {}
                for _title, _did in title_to_docid.items():
                    _fuzzy_docid[_title.lower()] = _did
                    _base = _title.rsplit('.', 1)[0] if '.' in _title else _title
                    _fuzzy_docid[_base.lower()] = _did
                # Also map tool_name → document_id directly
                for _tn, _did in tool_map.items():
                    if _tn not in _info_tool_names:
                        _fuzzy_docid[title_map.get(_tn, '').lower()] = _did

                for _cit in _new_citations:
                    if _cit.get("document_id") or _cit.get("url"):
                        continue
                    # Priority 1: LLM included tool_name → direct lookup
                    _tn_from_cit = (_cit.get("tool_name") or "").strip()
                    if _tn_from_cit and _tn_from_cit in tool_map:
                        _cit["document_id"] = tool_map[_tn_from_cit]
                        # Also fix document_title to use the proper title
                        _cit["document_title"] = title_map.get(_tn_from_cit, _cit.get("document_title", ""))
                        continue
                    # Priority 2: Exact match on document_title
                    _dt = (_cit.get("document_title") or "").strip()
                    if not _dt:
                        continue
                    _matched_id = title_to_docid.get(_dt) or _fuzzy_docid.get(_dt.lower())
                    # Priority 3: Substring match
                    if not _matched_id:
                        _dt_lower = _dt.lower()
                        for _known, _did in _fuzzy_docid.items():
                            if _known in _dt_lower or _dt_lower in _known:
                                _matched_id = _did
                                break
                    if _matched_id:
                        _cit["document_id"] = _matched_id

                if _ordered_refs:
                    logger.info(
                        f"📎 CITATION NORMALIZE: {len(_ordered_refs)} refs renumbered [1..{len(_ordered_refs)}], "
                        f"{len(_raw_cit_map)} from LLM block, {len(_ordered_refs) - len(set(_ordered_refs) & set(_raw_cit_map.keys()))} recovered"
                    )

                return _append_citations_block(clean_text, _new_citations), _new_citations

            # Record the assistant's tool-call turn in the conversation
            tool_conv.append(
                ChatManager.format_assistant_tool_call_message(
                    response.tool_calls, provider_name, response.text or ""
                )
            )

            # Execute all tool calls concurrently
            pending_calls = response.tool_calls[: self.MAX_TOOL_CALLS_PER_TURN]
            if len(response.tool_calls) > self.MAX_TOOL_CALLS_PER_TURN:
                dropped = len(response.tool_calls) - self.MAX_TOOL_CALLS_PER_TURN
                logger.warning(f"⚠️ TOOL CALLING [{node_name}]: {dropped} tool calls dropped (max {self.MAX_TOOL_CALLS_PER_TURN}/turn)")

            async def _run_single_tool(tc: Dict[str, Any]):
                """Execute one tool call; returns (tc, result_text, source_passages)."""
                _query = tc["arguments"].get("query", "")

                # --- Per-URL web search tool (URL mode with summaries) ---
                from .websearch_handler import WebSearchHandler
                if tc["name"].startswith(WebSearchHandler.URL_TOOL_PREFIX):
                    _ws = getattr(self.chat_manager, 'websearch_handler', None)
                    if not _ws:
                        return tc, "[Web search handler not available]", []
                    _target_url = url_tool_map.get(tc["name"], "")
                    if not _target_url:
                        return tc, f"[Unknown URL tool: {tc['name']}]", []
                    _ttl = node.get('data', {}).get('web_search_cache_ttl', 3600)
                    _result = await _ws._get_url_context([_target_url], _ttl, project_id)
                    return tc, _result, []

                # --- Web search tool ---
                if tc["name"] == WebSearchHandler.WEB_SEARCH_TOOL_NAME:
                    _ws = getattr(self.chat_manager, 'websearch_handler', None)
                    if not _ws:
                        return tc, "[Web search handler not available]", []
                    _result = await _ws.execute_websearch_tool(node, _query, project_id)
                    return tc, _result, []

                # --- DocAware search tool ---
                from .docaware_handler import DocAwareHandler
                if tc["name"] == DocAwareHandler.DOCAWARE_TOOL_NAME:
                    _da = getattr(self.chat_manager, 'docaware_handler', None)
                    if not _da:
                        return tc, "[Document search handler not available]", []
                    _limit = tc["arguments"].get("limit", 5)
                    _result = await _da.execute_docaware_tool(node, _query, project_id, limit=_limit)
                    return tc, _result, []

                # --- Document info tools ---
                if tc["name"] == document_tool_service.LIST_FILES_TOOL_NAME:
                    _result = await document_tool_service.execute_list_files_tool(project_id, doc_tool_selected)
                    return tc, _result, []

                if tc["name"] == document_tool_service.COUNT_FILES_TOOL_NAME:
                    _result = await document_tool_service.execute_count_files_tool(project_id, doc_tool_selected)
                    return tc, _result, []

                if tc["name"] == document_tool_service.GET_SUMMARIES_TOOL_NAME:
                    _result = await document_tool_service.execute_get_summaries_tool(project_id, doc_tool_selected)
                    return tc, _result, []

                if tc["name"] == document_tool_service.FIND_RELEVANT_TOOL_NAME:
                    _limit = tc["arguments"].get("limit", 5)
                    _result = await document_tool_service.execute_find_relevant_documents_tool(
                        project_id, _query, limit=_limit, selected_filenames=doc_tool_selected
                    )
                    return tc, _result, []

                if tc["name"] == document_tool_service.GET_METADATA_TOOL_NAME:
                    _fname = tc["arguments"].get("filename", "")
                    _result = await document_tool_service.execute_get_document_metadata_tool(
                        project_id, _fname, selected_filenames=doc_tool_selected
                    )
                    return tc, _result, []

                # --- Document tool ---
                _doc_id = tool_map.get(tc["name"])
                if not _doc_id:
                    return tc, f"[Unknown tool: {tc['name']}]", []

                _result = await document_tool_service.execute_document_tool(
                    project_id=project_id,
                    document_id=_doc_id,
                    query=_query,
                    provider=provider_name,
                    model=model_name,
                    agent_name=node_name,
                )

                _passages: List[Dict[str, Any]] = []
                try:
                    from users.models import ProjectDocumentSummary
                    _summary = await sync_to_async(
                        lambda did=_doc_id: ProjectDocumentSummary.objects.filter(
                            document__document_id=did
                        ).values_list("memory", flat=True).first()
                    )()
                    if _summary and isinstance(_summary, list) and _summary:
                        _passages = _summary[-1].get("source_passages", [])
                except Exception:
                    pass

                return tc, _result, _passages

            async def _timed_tool(tc):
                _t0 = time.time()
                res = await _run_single_tool(tc)
                _ms = int((time.time() - _t0) * 1000)
                return (*res, _ms)

            gather_results = await asyncio.gather(
                *[_timed_tool(tc) for tc in pending_calls],
                return_exceptions=True,
            )

            # Process results in original order
            calls_with_results: List[Dict[str, Any]] = []
            for _ri, raw_result in enumerate(gather_results):
                if isinstance(raw_result, BaseException):
                    logger.error(f"Tool call failed: {raw_result}")
                    failed_tc = pending_calls[_ri] if _ri < len(pending_calls) else None
                    if failed_tc:
                        fail_doc = failed_tc["name"]
                        for t in tools:
                            if t["function"]["name"] == failed_tc["name"]:
                                fail_doc = t["function"]["description"][:60]
                                break
                        notebook.append({
                            "step": len(notebook) + 1,
                            "tool_name": failed_tc["name"],
                            "document_name": fail_doc,
                            "query": failed_tc["arguments"].get("query", ""),
                            "result": f"[TOOL CALL FAILED: {str(raw_result)[:300]}]",
                            "source_passages": [],
                            "status": "failed",
                        })
                    continue

                tc, result_text, source_passages, tool_call_ms = raw_result
                query = tc["arguments"].get("query", "")

                calls_with_results.append({**tc, "result": result_text})

                doc_filename = tc["name"]
                for t in tools:
                    if t["function"]["name"] == tc["name"]:
                        doc_filename = t["function"]["description"][:60]
                        break

                if event_callback:
                    event_callback("tool_result", {
                        "agent": node_name,
                        "tool": title_map.get(tc["name"], tc["name"]),
                        "chars": len(str(result_text)),
                        "content": str(result_text)[:6000],
                    })

                notebook.append({
                    "step": len(notebook) + 1,
                    "tool_name": tc["name"],
                    "document_name": doc_filename,
                    "query": query,
                    "result": result_text[:6000],
                    "source_passages": source_passages[:15],
                    "status": "completed",
                })

                messages.append({
                    "sequence": message_sequence,
                    "agent_name": node_name,
                    "agent_type": node_type,
                    "content": _json.dumps(notebook[-1]),
                    "message_type": "tool_notebook",
                    "timestamp": timezone.now().isoformat(),
                    "response_time_ms": tool_call_ms,
                    "token_count": None,
                    "metadata": {
                        "llm_provider": provider_name,
                        "llm_model": model_name,
                        "phase": "tool_execution",
                        "iteration": iteration,
                        "tool_type": (
                            "web_search" if (
                                tc["name"].startswith("wsurl_")
                                or tc["name"] == "web_search"
                            )
                            else "docaware" if tc["name"] == "document_search"
                            else "document_read" if tc["name"] in tool_map
                            else "other"
                        ),
                        "tool_name": tc["name"],
                    },
                })
                message_sequence += 1

            execution_record.messages_data = messages
            await sync_to_async(execution_record.save)()

            # Append tool results to conversation so the LLM can continue
            tool_result_msgs = ChatManager.format_tool_results(calls_with_results, provider_name)
            tool_conv.extend(tool_result_msgs)

        # If we exhausted iterations, do a final synthesis call without tools
        logger.warning(f"⚠️ DOC TOOL CALLING [{node_name}]: Hit max iterations ({self.MAX_TOOL_ITERATIONS}), forcing synthesis")
        if event_callback:
            event_callback("synthesizing", {"agent": node_name})

        def _format_notebook_entry(entry: Dict[str, Any]) -> str:
            doc_title = title_map.get(entry["tool_name"], entry["tool_name"])
            parts = [
                f"### Document: {doc_title}",
                f"**Query:** {entry['query']}",
                f"**Finding:** {entry['result']}",
            ]
            passages = entry.get("source_passages", [])
            if passages:
                citation_lines = []
                for p in passages[:3]:
                    qt = p.get("quoted_text", "")[:150]
                    loc_parts = []
                    if p.get("page"):
                        loc_parts.append(f"p.{p['page']}")
                    if p.get("section"):
                        loc_parts.append(p["section"])
                    loc = f" ({', '.join(loc_parts)})" if loc_parts else ""
                    citation_lines.append(f'  - "{qt}"{loc}')
                parts.append("**Sources:**\n" + "\n".join(citation_lines))
            return "\n".join(parts)

        notebook_summary = "\n\n".join(
            _format_notebook_entry(entry) for entry in notebook
        )
        synthesis_messages = list(llm_messages)
        synthesis_messages.append({
            "role": "user",
            "content": (
                "Based on your research notebook below, provide a comprehensive "
                "answer to the original query.\n\n"
                "IMPORTANT — grounded citations:\n"
                "- Number citations SEQUENTIALLY starting from [1]. Do NOT reuse passage "
                "numbers from the research notes — renumber them starting from 1.\n"
                "- EVERY [N] marker in your text MUST have a corresponding entry in the "
                "JSON citations block below.\n"
                "- Each DISTINCT claim needs its own number unless the same verbatim passage supports it.\n"
                "- In the JSON block, each ref N must pair with a quoted_text that is the "
                "specific excerpt backing the sentence where [N] appears (not one generic "
                "quote reused for every marker).\n"
                "- Reference documents by their title (not filename).\n"
                + (
                    "- For citations from web search results, include the source "
                    "\"url\" field and set \"source\": \"web\". For citations from "
                    "project documents, set \"source\": \"document\".\n"
                    if has_web_tools else ""
                ) +
                "\nAt the END of your response, include a structured citations block (valid JSON array), e.g.:\n"
                "---CITATIONS---\n"
                + (
                    '[{"ref": 1, "document_title": "Page Title", "quoted_text": "excerpt from web…", "url": "https://example.com/article", "source": "web"}, '
                    '{"ref": 2, "document_title": "Title", "quoted_text": "excerpt from document…", "page": 1, "section": "1", "source": "document"}]\n'
                    if has_web_tools else
                    '[{"ref": 1, "document_title": "Title", "quoted_text": "excerpt for first claim…", "page": 1, "section": "1"}, '
                    '{"ref": 2, "document_title": "Title", "quoted_text": "different excerpt for second claim…", "page": 3, "section": "2"}]\n'
                ) +
                "---END_CITATIONS---\n\n"
                + (
                    f"=== ORIGINAL PLAN ===\n{plan_text}\n=== END PLAN ===\n\n"
                    "Verify that your answer addresses each item in the original plan. "
                    "If a planned step was not completed or a tool call failed, acknowledge the gap.\n\n"
                    if plan_text else ""
                )
                + f"=== RESEARCH NOTEBOOK ===\n{notebook_summary}\n=== END NOTEBOOK ==="
            ),
        })
        synthesis_resp = await llm_provider.generate_response(messages=synthesis_messages)
        if synthesis_resp.error:
            raise Exception(f"Agent {node_name} synthesis error: {synthesis_resp.error}")
        from agent_orchestration.document_tool_service import (
            _append_citations_block,
            _parse_citations_block,
        )
        clean_text, raw_citations = _parse_citations_block(synthesis_resp.text.strip())
        title_to_docid = {title_map.get(tn, ""): did for tn, did in tool_map.items() if title_map.get(tn)}

        # ── Complete citation normalization ──────────────────────────
        # The LLM often uses arbitrary [N] numbers copied from tool-result
        # passage IDs instead of sequential refs, and omits many from the
        # JSON block. We renumber everything sequentially and ensure every
        # inline [N] has a matching structured citation with tooltip data.

        import re as _re

        # Build lookup from whatever the LLM put in its citations block
        _raw_cit_map: Dict[int, Dict[str, Any]] = {}
        for _c in raw_citations:
            _r = _c.get("ref")
            if _r is not None:
                _raw_cit_map[int(_r)] = _c

        # Collect all [N] in text, in order of first appearance
        _seen: set = set()
        _ordered_refs: List[int] = []
        for _m in _re.finditer(r'\[(\d+)\]', clean_text):
            _n = int(_m.group(1))
            if _n not in _seen:
                _seen.add(_n)
                _ordered_refs.append(_n)

        def _find_citation_in_notebook(_ref_num: int) -> Dict[str, Any]:
            """Reconstruct a citation entry from notebook tool results."""
            # Try [N] "quote" pattern in notebook result text
            for _entry in notebook:
                _result_text = _entry.get("result", "")
                _pat = rf'\[{_ref_num}\]\s*"([^"]+)"'
                _match = _re.search(_pat, _result_text)
                if _match:
                    return {
                        "document_title": title_map.get(_entry["tool_name"], _entry["tool_name"]),
                        "quoted_text": _match.group(1)[:250],
                        "document_id": tool_map.get(_entry["tool_name"]),
                        "source": "document",
                    }
            # Try [N] followed by any descriptive text
            for _entry in notebook:
                _result_text = _entry.get("result", "")
                _pat2 = rf'\[{_ref_num}\]\s*([^\[\n]+)'
                _match2 = _re.search(_pat2, _result_text)
                if _match2:
                    return {
                        "document_title": title_map.get(_entry["tool_name"], _entry["tool_name"]),
                        "quoted_text": _match2.group(1).strip()[:250],
                        "document_id": tool_map.get(_entry["tool_name"]),
                        "source": "document",
                    }
            # Fallback: use first notebook entry's document title
            if notebook:
                _entry = notebook[0]
                return {
                    "document_title": title_map.get(_entry["tool_name"], _entry["tool_name"]),
                    "quoted_text": f"Reference from {title_map.get(_entry['tool_name'], _entry['tool_name'])}",
                    "source": "document",
                    "document_id": tool_map.get(_entry["tool_name"]),
                }
            return {"quoted_text": "Reference", "source": "document"}

        # Build renumbered citations: [old_num] → [new_num]
        _new_citations: List[Dict[str, Any]] = []
        _old_to_new: Dict[int, int] = {}
        for _new_num, _old_num in enumerate(_ordered_refs, start=1):
            _old_to_new[_old_num] = _new_num
            if _old_num in _raw_cit_map:
                _entry = dict(_raw_cit_map[_old_num])
                _entry["ref"] = _new_num
            else:
                _entry = _find_citation_in_notebook(_old_num)
                _entry["ref"] = _new_num
            _new_citations.append(_entry)

        # Renumber refs in the text using placeholder to avoid collisions
        for _old_num in sorted(_old_to_new.keys(), reverse=True):
            clean_text = clean_text.replace(f"[{_old_num}]", f"[__CITE_{_old_to_new[_old_num]}__]")
        for _new_num in range(1, len(_ordered_refs) + 1):
            clean_text = clean_text.replace(f"[__CITE_{_new_num}__]", f"[{_new_num}]")

        # Enrich with document_id
        for _cit in _new_citations:
            _dt = _cit.get("document_title", "")
            if _dt and _dt in title_to_docid and not _cit.get("url"):
                _cit["document_id"] = title_to_docid[_dt]

        if _ordered_refs:
            logger.info(
                f"📎 CITATION NORMALIZE: {len(_ordered_refs)} refs renumbered [1..{len(_ordered_refs)}], "
                f"{len(_raw_cit_map)} from LLM block, {len(_ordered_refs) - len(set(_ordered_refs) & set(_raw_cit_map.keys()))} recovered from notebook"
            )

        return _append_citations_block(clean_text, _new_citations), _new_citations

    async def _save_messages_to_database(self, messages, execution_record):
        """
        Save messages to database with proper error handling and duplicate prevention
        """
        # Get existing message sequences to prevent duplicates
        from users.models import WorkflowExecutionMessage
        
        try:
            existing_sequences = await sync_to_async(set)(
                WorkflowExecutionMessage.objects.filter(
                    execution=execution_record
                ).values_list('sequence', flat=True)
            )
        except Exception as e:
            logger.error(f"❌ SAVE MESSAGE: Error getting existing sequences: {e}")
            existing_sequences = set()
        
        logger.info(f"💾 SAVE MESSAGE: Found {len(existing_sequences)} existing message sequences in database")
        
        saved_count = 0
        skipped_count = 0
        
        for message in messages:
            # Skip messages without required fields
            if not isinstance(message, dict):
                logger.warning(f"⚠️ SAVE MESSAGE: Skipping non-dict message: {type(message)}")
                continue
            
            # Ensure message has a sequence key - use get() with default
            message_sequence = message.get('sequence')
            if message_sequence is None:
                # Try to assign a sequence based on existing sequences
                message_sequence = max(existing_sequences, default=-1) + 1
                message['sequence'] = message_sequence
                logger.warning(f"⚠️ SAVE MESSAGE: Message missing sequence, assigned {message_sequence}")
            
            # Skip messages that already exist in database
            if message_sequence in existing_sequences:
                skipped_count += 1
                logger.debug(f"⏭️ SAVE MESSAGE: Skipping duplicate sequence {message_sequence} ({message.get('agent_name', 'Unknown')})")
                continue
                
            # Parse timestamp from message
            try:
                message_timestamp = datetime.fromisoformat(message.get('timestamp', '').replace('Z', '+00:00'))
                if message_timestamp.tzinfo is None:
                    message_timestamp = timezone.make_aware(message_timestamp)
            except (KeyError, ValueError, AttributeError):
                message_timestamp = timezone.now()
            
            try:
                await sync_to_async(WorkflowExecutionMessage.objects.create)(
                    execution=execution_record,
                    sequence=message_sequence,
                    agent_name=message.get('agent_name') or 'System',
                    agent_type=message.get('agent_type') or 'System',
                    content=message.get('content', ''),
                    message_type=message.get('message_type', 'chat'),
                    timestamp=message_timestamp,
                    response_time_ms=message.get('response_time_ms', 0),
                    token_count=message.get('token_count'),
                    metadata=message.get('metadata', {})
                )
                saved_count += 1
                existing_sequences.add(message_sequence)  # Add to set to prevent duplicates in same batch
                logger.debug(f"💾 SAVE MESSAGE: Saved sequence {message_sequence} ({message.get('agent_name', 'Unknown')})")
            except Exception as save_error:
                logger.error(f"❌ SAVE MESSAGE: Failed to save message {message_sequence}: {save_error}")
        
        logger.info(f"💾 SAVE MESSAGE: Saved {saved_count} new messages, skipped {skipped_count} duplicates")
    
    def _find_ready_nodes(self, execution_sequence: List[Dict[str, Any]], executed_nodes: Dict[str, str],
                         graph_json: Dict[str, Any], current_index: int) -> List[Tuple[int, Dict[str, Any]]]:
        """
        Find all nodes that are ready to execute in parallel (all dependencies satisfied)
        
        Args:
            execution_sequence: Full execution sequence
            executed_nodes: Dictionary of executed node outputs
            graph_json: Full workflow graph
            current_index: Current position in execution sequence
            
        Returns:
            List of (index, node) tuples for nodes ready to execute in parallel
        """
        ready_nodes = []
        edges = graph_json.get('edges', [])
        
        # Build dependency map: node_id -> set of source node_ids it depends on
        dependency_map = {}
        nodes = graph_json.get('nodes', [])
        node_map = {node.get('id'): node for node in nodes}  # Create lookup for fast access
        
        for edge in edges:
            edge_type = edge.get('type', 'sequential')
            source_id = edge.get('source')
            target_id = edge.get('target')
            
            # Get target node to check if it's a UserProxyAgent
            target_node = node_map.get(target_id)
            is_user_proxy = (target_node and 
                            target_node.get('type') == 'UserProxyAgent' and
                            target_node.get('data', {}).get('require_human_input', True))
            
            # Include sequential edges for all nodes
            # Include reflection edges ONLY for UserProxyAgent nodes (they depend on reflection sources)
            if edge_type == 'sequential' or (edge_type == 'reflection' and is_user_proxy):
                if target_id not in dependency_map:
                    dependency_map[target_id] = set()
                dependency_map[target_id].add(source_id)
        
        # Check nodes from current_index onwards
        for i in range(current_index, len(execution_sequence)):
            node = execution_sequence[i]
            node_id = node.get('id')
            node_type = node.get('type')
            
            # Skip if already executed
            if node_id in executed_nodes:
                continue
            
            # Skip StartNode and EndNode (handled separately)
            if node_type in ['StartNode', 'EndNode']:
                continue
            
            # Check if all dependencies are satisfied
            dependencies = dependency_map.get(node_id, set())
            all_dependencies_satisfied = all(dep_id in executed_nodes for dep_id in dependencies)
            
            if all_dependencies_satisfied:
                # CRITICAL FIX: Check if this node depends on any node that's currently executing in parallel
                # If a dependency is in the current ready_nodes batch, this node should wait
                depends_on_parallel_node = False
                node_name = node.get('data', {}).get('name', node_id)
                for dep_id in dependencies:
                    # Check if this dependency is in the ready_nodes we're about to execute
                    # (This prevents nodes from being ready if their dependency is executing in parallel)
                    for ready_idx, ready_node in ready_nodes:
                        if ready_node.get('id') == dep_id:
                            depends_on_parallel_node = True
                            dep_name = ready_node.get('data', {}).get('name', dep_id)
                            logger.info(f"⏳ PARALLEL: Node {node_name} depends on {dep_name} which is executing in parallel - will wait")
                            break
                    if depends_on_parallel_node:
                        break
                
                if not depends_on_parallel_node:
                    ready_nodes.append((i, node))
                else:
                    # This node depends on a node that's executing in parallel, so it must wait
                    break
            else:
                # If this node's dependencies aren't satisfied, no nodes after it can be ready either
                # (due to topological sort ordering)
                break
        
        return ready_nodes
    
    async def _execute_nodes_in_parallel(self, ready_nodes: List[Tuple[int, Dict[str, Any]]],
                                        workflow, graph_json, executed_nodes, conversation_history,
                                        execution_record, messages, message_sequence, agents_involved,
                                        total_response_time, providers_used, project_id,
                                        deployment_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute multiple nodes in parallel using asyncio.gather
        
        Args:
            ready_nodes: List of (index, node) tuples to execute
            workflow: Workflow instance
            graph_json: Full workflow graph
            executed_nodes: Current executed nodes state
            conversation_history: Current conversation history
            execution_record: Execution record
            messages: Current messages list
            message_sequence: Current message sequence number
            agents_involved: Set of agents involved
            total_response_time: Total response time so far
            providers_used: List of providers used
            project_id: Project ID
            
        Returns:
            List of execution results for each node
        """
        async def execute_single_node(node_tuple):
            """Execute a single node and return result"""
            idx, node = node_tuple
            node_id = node.get('id')
            node_type = node.get('type')
            node_data = node.get('data', {})
            node_name = node_data.get('name', f'Node_{node_id}')
            
            try:
                logger.info(f"🔀 PARALLEL: Executing {node_name} (type: {node_type})")
                
                # Handle UserProxyAgent separately (can't parallelize if requires human input)
                if node_type == 'UserProxyAgent' and node_data.get('require_human_input', True):
                    return {
                        'node_id': node_id,
                        'node_name': node_name,
                        'executed': False,
                        'paused': True,
                        'index': idx
                    }
                
                # Get LLM provider
                agent_config = {
                    'llm_provider': node_data.get('llm_provider', 'openai'),
                    'llm_model': node_data.get('llm_model', 'gpt-3.5-turbo')
                }
                
                project = await sync_to_async(lambda: workflow.project)()
                llm_provider = await self.llm_provider_manager.get_llm_provider(agent_config, project)
                if not llm_provider:
                    raise Exception(f"Failed to create LLM provider for agent {node_name}")
                
                # Get input sources - use a snapshot of executed_nodes to avoid race conditions
                # Each parallel execution gets its own snapshot
                input_sources = self.workflow_parser.find_multiple_inputs_to_node(node_id, graph_json)
                
                # Validate inputs
                if len(input_sources) > 0:
                    missing_inputs = []
                    for input_source in input_sources:
                        source_id = input_source.get('source_id')
                        if source_id not in executed_nodes:
                            missing_inputs.append(source_id)
                    if missing_inputs:
                        raise Exception(f"Missing required inputs: {missing_inputs}")
                
                # CRITICAL FIX: Special handling for GroupChatManager in parallel execution
                # GroupChatManager must execute delegates, not act as a regular AssistantAgent
                if node_type == 'GroupChatManager':
                    logger.info(f"👥 PARALLEL: Executing GroupChatManager {node_name} with tool-based delegation")

                    execution_sequence = self.workflow_parser.parse_workflow_graph(graph_json)

                    logger.info(f"📥 PARALLEL: GroupChatManager {node_name} has {len(input_sources)} input source(s)")
                    chat_result = await self.chat_manager.execute_group_chat_manager_with_multiple_inputs(
                        node, llm_provider, input_sources, executed_nodes, execution_sequence, graph_json, str(project_id), project, execution_id, event_callback=event_callback
                    )
                    
                    agent_response_text = chat_result['final_response']
                    response_time_ms = 0  # GroupChatManager response time is complex (includes delegate execution)
                    
                    logger.info(f"✅ PARALLEL: {node_name} completed - {len(agent_response_text)} chars (with {chat_result.get('total_iterations', 0)} delegate iterations)")
                    
                    # Return special result for GroupChatManager
                    return {
                        'node_id': node_id,
                        'node_name': node_name,
                        'executed': True,
                        'output': agent_response_text,
                        'response_time_ms': response_time_ms,
                        'token_count': None,
                        'agents_involved': {node_name},
                        'providers_used': [agent_config['llm_provider']],
                        'metadata': {
                            'llm_provider': agent_config['llm_provider'],
                            'llm_model': agent_config['llm_model'],
                            'is_group_chat_manager': True,
                            'delegate_conversations': chat_result.get('delegate_conversations', []),
                            'delegate_status': chat_result.get('delegate_status', {}),
                            'total_iterations': chat_result.get('total_iterations', 0)
                        },
                        'index': idx,
                        'is_group_chat_manager': True,
                        'chat_result': chat_result  # Store full result for message logging
                    }
                
                # Regular agent execution (AssistantAgent, etc.)
                # Craft prompt - use conversation_history snapshot
                # Note: In parallel execution, conversation_history may not include other parallel nodes yet
                # This is correct - each node sees the state before parallel execution started
                if len(input_sources) > 1:
                    aggregated_context = self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
                    prompt_result = await self.chat_manager.craft_conversation_prompt_with_docaware(
                        aggregated_context, node, str(project_id), conversation_history
                    )
                    # Handle dict return with potential file_references (Full Document Mode)
                    llm_messages = prompt_result.get('messages', prompt_result) if isinstance(prompt_result, dict) else prompt_result
                    
                    # Apply file reference formatting if file attachments are enabled
                    if isinstance(prompt_result, dict) and prompt_result.get('file_references'):
                        logger.info(f"📎 FILE ATTACHMENTS: Formatting {len(prompt_result['file_references'])} file references for {node_name}")
                        llm_messages = self.chat_manager.format_messages_with_file_refs(
                            llm_messages,
                            prompt_result['file_references'],
                            prompt_result.get('provider', 'openai')
                        )
                else:
                    prompt_result_single = await self.chat_manager.craft_conversation_prompt(
                        conversation_history, node, str(project_id)
                    )
                    # Handle dict return with potential file_references (File Attachments)
                    llm_messages = prompt_result_single.get('messages', prompt_result_single) if isinstance(prompt_result_single, dict) else prompt_result_single
                    
                    # Apply file reference formatting if file attachments are enabled
                    if isinstance(prompt_result_single, dict) and prompt_result_single.get('file_references'):
                        logger.info(f"📎 FILE ATTACHMENTS: Formatting {len(prompt_result_single['file_references'])} file references for {node_name}")
                        llm_messages = self.chat_manager.format_messages_with_file_refs(
                            llm_messages,
                            prompt_result_single['file_references'],
                            prompt_result_single.get('provider', 'openai')
                        )
                
                # Chat file references (deployment chatbot uploads) — parallel path
                is_deployment = deployment_context is not None and deployment_context.get('is_deployment', False)
                if is_deployment and deployment_context:
                    if deployment_context.get('chat_file_references'):
                        _chat_refs = deployment_context['chat_file_references']
                        _provider = node_data.get('llm_provider', 'openai').lower()
                        logger.info(f"📎 CHAT FILES (parallel): Attaching {len(_chat_refs)} session files to {node_name} ({_provider})")
                        llm_messages = self.chat_manager.format_messages_with_file_refs(
                            llm_messages, _chat_refs, _provider
                        )
                    if deployment_context.get('chat_text_attachments'):
                        for _att in deployment_context['chat_text_attachments']:
                            _text_block = f"\n\n--- Attached Document: {_att['filename']} ---\n{_att['text']}\n--- End Document ---"
                            for _msg in reversed(llm_messages):
                                if _msg.get('role') == 'user':
                                    if isinstance(_msg['content'], str):
                                        _msg['content'] += _text_block
                                    elif isinstance(_msg['content'], list):
                                        for _part in _msg['content']:
                                            if isinstance(_part, dict) and _part.get('type') == 'text':
                                                _part['text'] += _text_block
                                                break
                                    break
                        logger.info(f"📎 CHAT TEXT (parallel): Injected {len(deployment_context['chat_text_attachments'])} text attachments into {node_name}")

                # Execute LLM call with structured messages
                agent_response = await llm_provider.generate_response(messages=llm_messages)
                
                if agent_response.error:
                    raise Exception(f"Agent {node_name} error: {agent_response.error}")
                
                agent_response_text = agent_response.text.strip()
                response_time_ms = getattr(agent_response, 'response_time_ms', 0) if hasattr(agent_response, 'response_time_ms') else 0
                
                logger.info(f"✅ PARALLEL: {node_name} completed - {len(agent_response_text)} chars, {response_time_ms}ms")
                
                return {
                    'node_id': node_id,
                    'node_name': node_name,
                    'executed': True,
                    'output': agent_response_text,
                    'response_time_ms': response_time_ms,
                    'token_count': getattr(agent_response, 'token_count', None),
                    'agents_involved': {node_name},
                    'providers_used': [agent_config['llm_provider']],
                    'metadata': {
                        'llm_provider': agent_config['llm_provider'],
                        'llm_model': agent_config['llm_model'],
                        'cost_estimate': getattr(agent_response, 'cost_estimate', None)
                    },
                    'index': idx
                }
            except Exception as e:
                logger.error(f"❌ PARALLEL: {node_name} failed: {e}")
                return {
                    'node_id': node_id,
                    'node_name': node_name,
                    'executed': False,
                    'error': str(e),
                    'index': idx
                }
        
        # Execute all nodes in parallel
        results = await asyncio.gather(*[execute_single_node(node_tuple) for node_tuple in ready_nodes])
        
        # Process results and create messages (in order of execution sequence)
        results.sort(key=lambda r: r['index'])
        next_sequence = message_sequence
        new_messages = []
        
        for result in results:
            if result.get('executed'):
                # Get node type from original node
                node_idx = result['index']
                node_type = next((n[1].get('type', 'AssistantAgent') for n in ready_nodes if n[0] == node_idx), 'AssistantAgent')
                
                # Special handling for GroupChatManager from parallel execution
                if result.get('is_group_chat_manager') and result.get('chat_result'):
                    chat_result = result['chat_result']
                    delegate_conversations = chat_result.get('delegate_conversations', [])
                    delegate_status = chat_result.get('delegate_status', {})
                    total_iterations = chat_result.get('total_iterations', 0)
                    
                    # Create GroupChatManager message with delegate details
                    par_gcm_metadata = {
                        **result.get('metadata', {}),
                        'is_group_chat_manager': True,
                        'total_iterations': total_iterations,
                        'delegate_count': len(delegate_status),
                        'expandable': True,
                        'delegate_conversations': delegate_conversations,
                        'delegate_status': delegate_status,
                    }
                    if chat_result.get('citations'):
                        par_gcm_metadata['citations'] = chat_result['citations']

                    new_messages.append({
                        'sequence': next_sequence,
                        'agent_name': result['node_name'],
                        'agent_type': node_type,
                        'content': result['output'],
                        'message_type': 'group_chat_summary',
                        'timestamp': timezone.now().isoformat(),
                        'response_time_ms': result.get('response_time_ms', 0),
                        'token_count': result.get('token_count'),
                        'metadata': par_gcm_metadata,
                    })
                    next_sequence += 1
                    
                    # Log individual delegate messages if available
                    # Note: For parallel execution, we store delegate conversations in metadata
                    # Individual delegate messages are logged in the sequential path
                    logger.info(f"💾 PARALLEL: GroupChatManager {result['node_name']} completed with {total_iterations} delegate iterations")
                else:
                    # Regular agent message
                    new_messages.append({
                        'sequence': next_sequence,
                        'agent_name': result['node_name'],
                        'agent_type': node_type,
                        'content': result['output'],
                        'message_type': 'chat',
                        'timestamp': timezone.now().isoformat(),
                        'response_time_ms': result.get('response_time_ms', 0),
                        'token_count': result.get('token_count'),
                        'metadata': result.get('metadata', {})
                    })
                    next_sequence += 1
        
        # Append new messages to existing messages list
        messages.extend(new_messages)
        
        # Update execution record with all messages
        execution_record.messages_data = messages
        await sync_to_async(execution_record.save)(update_fields=['messages_data'])
        
        logger.info(f"💾 PARALLEL: Saved {len(new_messages)} messages from parallel execution")
        
        return results
    
    def get_workflow_execution_summary(self, workflow: AgentWorkflow) -> Dict[str, Any]:
        """
        Get execution summary with recent execution history and messages
        """
        # Get recent executions from database
        recent_executions = WorkflowExecution.objects.filter(
            workflow=workflow
        ).order_by('-start_time')[:10]
        
        execution_history = []
        for execution in recent_executions:
            # Get messages for this execution
            messages = WorkflowExecutionMessage.objects.filter(
                execution=execution
            ).order_by('sequence')
            
            execution_data = {
                'execution_id': execution.execution_id,
                'status': execution.status,
                'start_time': execution.start_time.isoformat(),
                'end_time': execution.end_time.isoformat() if execution.end_time else None,
                'duration_seconds': execution.duration_seconds,
                'total_messages': execution.total_messages,
                'total_agents_involved': execution.total_agents_involved,
                'providers_used': execution.providers_used,
                'result_summary': execution.result_summary,
                'conversation_history': execution.conversation_history,
                'messages': [
                    {
                        'sequence': msg.sequence,
                        'agent_name': msg.agent_name,
                        'agent_type': msg.agent_type,
                        'content': msg.content,
                        'message_type': msg.message_type,
                        'timestamp': msg.timestamp.isoformat(),
                        'response_time_ms': msg.response_time_ms,
                        'token_count': msg.token_count,
                        'metadata': msg.metadata
                    }
                    for msg in messages
                ]
            }
            execution_history.append(execution_data)
        
        return {
            'workflow_id': str(workflow.workflow_id),
            'workflow_name': workflow.name,
            'total_executions': workflow.total_executions,
            'successful_executions': workflow.successful_executions,
            'average_execution_time': workflow.average_execution_time,
            'last_executed_at': workflow.last_executed_at.isoformat() if workflow.last_executed_at else None,
            'recent_executions': execution_history
        }
    
    def _extract_last_conversation_message(self, messages: List[Dict[str, Any]], conversation_history: str) -> str:
        """
        Extract the last conversation message to display when requesting human input.
        Shows the most recent meaningful message (prefers user queries, then assistant responses).
        Prioritizes messages_data over conversation_history string.
        
        Args:
            messages: List of message dictionaries from messages_data
            conversation_history: Conversation history as string
            
        Returns:
            Last conversation message content
        """
        # First, try to get from messages_data (more reliable)
        if messages:
            # Look for the last meaningful message (user input or assistant response)
            # Prefer user input if available, otherwise assistant response
            user_message = None
            assistant_message = None
            
            for msg in reversed(messages):
                if isinstance(msg, dict):
                    agent_type = msg.get('agent_type', '')
                    message_type = msg.get('message_type', '')
                    content = msg.get('content', '') or msg.get('message', '')
                    
                    if not content or not content.strip():
                        continue
                    
                    # Skip StartNode and EndNode
                    if agent_type in ['StartNode', 'EndNode']:
                        continue
                    
                    # Collect user input messages
                    if message_type in ['user_input', 'human_input'] or agent_type == 'UserProxyAgent':
                        if not user_message:
                            user_message = content.strip()
                    
                    # Collect assistant/agent messages (not user input)
                    elif message_type not in ['user_input', 'human_input']:
                        if not assistant_message:
                            assistant_message = content.strip()
            
            # Prefer user message if available (most recent context)
            if user_message:
                logger.info(f"📝 DEPLOYMENT: Extracted last user message: {user_message[:100]}...")
                return user_message
            
            # Fallback to assistant message
            if assistant_message:
                logger.info(f"📝 DEPLOYMENT: Extracted last assistant message: {assistant_message[:100]}...")
                return assistant_message
        
        # Fallback: extract from conversation_history string
        if conversation_history:
            lines = conversation_history.strip().split('\n')
            user_line = None
            assistant_line = None
            
            # Look for the last user and assistant messages
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        role = parts[0].strip().lower()
                        content = parts[1].strip()
                        
                        if content:
                            # Prefer user messages
                            if role == 'user' and not user_line:
                                user_line = content
                            # Then assistant messages
                            elif ('assistant' in role or 'ai' in role) and not assistant_line:
                                assistant_line = content
            
            # Return user message if available, otherwise assistant
            if user_line:
                logger.info(f"📝 DEPLOYMENT: Extracted last user message from conversation_history: {user_line[:100]}...")
                return user_line
            
            if assistant_line:
                logger.info(f"📝 DEPLOYMENT: Extracted last assistant message from conversation_history: {assistant_line[:100]}...")
                return assistant_line
        
        # Default fallback
        logger.warning(f"⚠️ DEPLOYMENT: Could not extract last conversation message")
        return "Please provide your input to continue."
    
    async def _store_deployment_pause_state(
        self, 
        session_id: str, 
        execution_record: Any, 
        node_id: str, 
        node_name: str, 
        last_message: str
    ):
        """
        Store paused execution state in DeploymentSession (non-blocking).
        Also stores session_id in execution record metadata for later retrieval.
        
        Args:
            session_id: Deployment session ID
            execution_record: WorkflowExecution record
            node_id: UserProxyAgent node ID
            node_name: UserProxyAgent name
            last_message: Last conversation message to display
        """
        try:
            from .models import DeploymentSession
            
            # Get deployment session
            deployment_session = await sync_to_async(
                DeploymentSession.objects.filter(session_id=session_id).first
            )()
            
            if deployment_session:
                # Ensure execution record is saved and has an execution_id
                if not execution_record.execution_id:
                    logger.error(f"❌ DEPLOYMENT: Execution record has no execution_id!")
                    return
                
                # Refresh execution record to ensure it's saved
                await sync_to_async(execution_record.refresh_from_db)()
                
                # Verify execution exists in database
                from users.models import WorkflowExecution
                execution_exists = await sync_to_async(
                    WorkflowExecution.objects.filter(execution_id=execution_record.execution_id).exists
                )()
                
                if not execution_exists:
                    logger.error(f"❌ DEPLOYMENT: WorkflowExecution {execution_record.execution_id} does not exist in database!")
                    return
                
                # Update session with pause state
                deployment_session.awaiting_human_input = True
                deployment_session.paused_execution_id = execution_record.execution_id
                deployment_session.human_input_prompt = last_message
                deployment_session.human_input_agent_name = node_name
                deployment_session.human_input_agent_id = node_id
                
                # Add the last conversation message to conversation history so it appears in the chat UI
                # This is the message the user sees when the human input modal appears
                if last_message and last_message.strip():
                    conversation_history = deployment_session.conversation_history or []
                    conversation_history.append({
                        'role': 'assistant',
                        'content': last_message,
                        'timestamp': timezone.now().isoformat()
                    })
                    deployment_session.conversation_history = conversation_history
                    deployment_session.message_count = len(conversation_history)
                    logger.info(f"📝 DEPLOYMENT: Added last conversation message to session history: {last_message[:100]}...")
                
                await sync_to_async(deployment_session.save)()
                
                # Store session_id in execution record metadata for later retrieval
                execution_metadata = execution_record.messages_data or []
                # Check if metadata already exists in last message or create new entry
                if execution_metadata and isinstance(execution_metadata[-1], dict):
                    execution_metadata[-1]['deployment_session_id'] = session_id
                else:
                    # Add metadata entry
                    execution_metadata.append({
                        'deployment_session_id': session_id,
                        'timestamp': timezone.now().isoformat()
                    })
                execution_record.messages_data = execution_metadata
                await sync_to_async(execution_record.save)(update_fields=['messages_data'])
                
                logger.info(f"💾 DEPLOYMENT: Stored pause state in session {session_id[:8]} for UserProxyAgent {node_name} (execution_id: {execution_record.execution_id[:8]})")
            else:
                logger.warning(f"⚠️ DEPLOYMENT: Could not find DeploymentSession for session_id {session_id}")
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Failed to store pause state: {e}", exc_info=True)
    
    async def _get_deployment_context_from_execution(self, execution_record: Any) -> Optional[Dict[str, Any]]:
        """
        Check if an execution is part of a deployment by checking DeploymentSession.
        First checks execution record metadata for session_id, then checks DeploymentSession.
        
        Args:
            execution_record: WorkflowExecution record
            
        Returns:
            Deployment context dict if found, None otherwise
        """
        try:
            from .models import DeploymentSession
            
            # First, try to get session_id from execution record metadata
            session_id = None
            messages_data = execution_record.messages_data or []
            if messages_data:
                # Check last message for deployment_session_id
                if isinstance(messages_data[-1], dict) and 'deployment_session_id' in messages_data[-1]:
                    session_id = messages_data[-1]['deployment_session_id']
                    logger.info(f"📝 DEPLOYMENT: Found session_id {session_id[:8]} in execution metadata")
            
            # Check if there's a DeploymentSession with this execution_id (paused state)
            deployment_session = await sync_to_async(
                DeploymentSession.objects.filter(
                    paused_execution_id=execution_record.execution_id
                ).first
            )()
            
            if deployment_session:
                return {
                    'is_deployment': True,
                    'session_id': deployment_session.session_id,
                    'current_user_query': ''  # Will be provided when resuming
                }
            
            # If we have session_id from metadata, try to get that session
            if session_id:
                deployment_session = await sync_to_async(
                    DeploymentSession.objects.filter(session_id=session_id).first
                )()
                if deployment_session:
                    return {
                        'is_deployment': True,
                        'session_id': deployment_session.session_id,
                        'current_user_query': ''
                    }
            
            # Fallback: Check if there's an active deployment for this project
            workflow = await sync_to_async(lambda: execution_record.workflow)()
            project = await sync_to_async(lambda: workflow.project)()
            
            from .models import WorkflowDeployment
            deployment = await sync_to_async(
                WorkflowDeployment.objects.filter(
                    project=project,
                    is_active=True
                ).first
            )()
            
            if deployment:
                # Try to find a session that might be related (by checking recent sessions)
                recent_session = await sync_to_async(
                    DeploymentSession.objects.filter(
                        deployment=deployment,
                        is_active=True
                    ).order_by('-last_activity').first
                )()
                
                if recent_session:
                    return {
                        'is_deployment': True,
                        'session_id': recent_session.session_id,
                        'current_user_query': ''
                    }
            
            return None
        except Exception as e:
            logger.error(f"❌ DEPLOYMENT: Failed to get deployment context: {e}", exc_info=True)
            return None