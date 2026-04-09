"""
Real Agent Orchestration Engine
==============================

Custom agent orchestration framework that chains conversations between agents
using different LLM providers for REAL execution (not simulation).

This is the main orchestrator that coordinates between all the specialized modules.
The heavy lifting is now done by dedicated modules for better maintainability.
"""

import logging
from typing import Dict, List, Any, Optional
from asgiref.sync import sync_to_async

# Import specialized modules
from .llm_provider_manager import LLMProviderManager
from .reflection_handler import ReflectionHandler
from .workflow_parser import WorkflowParser
from .chat_manager import ChatManager
from .docaware_handler import DocAwareHandler
from .websearch_handler import WebSearchHandler
from .human_input_handler import HumanInputHandler
from .workflow_executor import WorkflowExecutor

# Import models
from users.models import AgentWorkflow, WorkflowExecution

logger = logging.getLogger('conversation_orchestrator')

class ConversationOrchestrator:
    """
    Main conversation orchestration engine that coordinates all workflow execution
    
    This class acts as a facade that delegates work to specialized modules:
    - LLMProviderManager: Handles LLM provider creation and reflection logic
    - WorkflowParser: Parses workflow graphs and handles multiple inputs
    - ChatManager: Manages group chats and delegate conversations
    - DocAwareHandler: Handles document-aware functionality
    - HumanInputHandler: Manages workflow pause/resume for human input
    - WorkflowExecutor: Main workflow execution engine
    """
    
    def __init__(self):
        # Initialize all specialized handlers
        self.llm_provider_manager = LLMProviderManager()
        self.workflow_parser = WorkflowParser()
        self.docaware_handler = DocAwareHandler(self.llm_provider_manager)
        self.websearch_handler = WebSearchHandler(self.llm_provider_manager)
        
        # Initialize reflection handler with LLM provider manager
        self.reflection_handler = ReflectionHandler(self.llm_provider_manager)
        
        # Initialize chat manager with dependencies
        self.chat_manager = ChatManager(
            self.llm_provider_manager,
            self.workflow_parser,
            self.docaware_handler,
            self.websearch_handler
        )
        
        # Initialize human input handler with dependencies
        self.human_input_handler = HumanInputHandler(
            self.workflow_parser,
            self.docaware_handler,
            self.llm_provider_manager,
            self.reflection_handler,
            self.websearch_handler
        )
        
        # Set the human input handler reference in reflection handler
        self.reflection_handler.set_human_input_handler(self.human_input_handler)
        
        # Initialize workflow executor with all dependencies
        self.workflow_executor = WorkflowExecutor(
            self.workflow_parser,
            self.llm_provider_manager,
            self.chat_manager,
            self.docaware_handler,
            self.human_input_handler,
            self.reflection_handler
        )
        
        logger.info("🤖 ORCHESTRATOR: Initialized modular conversation orchestrator with all components")
    
    # ============================================================================
    # MAIN API METHODS - Primary interfaces used by the application
    # ============================================================================
    
    async def execute_workflow(self, workflow: AgentWorkflow, executed_by, deployment_context: Optional[Dict[str, Any]] = None, event_callback=None, stream_callback=None) -> Dict[str, Any]:
        """
        Execute the complete workflow with REAL LLM calls and conversation chaining

        Args:
            workflow: The AgentWorkflow instance to execute
            executed_by: User who initiated the execution
            deployment_context: Optional deployment context with user query for UserProxyAgent handling
            event_callback: Optional callback for streaming intermediate events
            stream_callback: Optional async callable(chunk: str) for streaming final agent output

        Returns:
            Dict containing execution results, conversation history, and metadata
        """
        return await self.workflow_executor.execute_workflow(workflow, executed_by, deployment_context=deployment_context, event_callback=event_callback, stream_callback=stream_callback)
    
    async def resume_workflow_with_human_input(self, execution_id: str, human_input: str, user):
        """
        Resume paused workflow with human input
        
        Args:
            execution_id: ID of the paused workflow execution
            human_input: Human input provided to resume the workflow
            user: User providing the input
            
        Returns:
            Dict containing resumed execution results
        """
        return await self.human_input_handler.resume_workflow_with_human_input(execution_id, human_input, user)
    
    def get_workflow_execution_summary(self, workflow: AgentWorkflow) -> Dict[str, Any]:
        """
        Get execution summary with recent execution history and messages
        
        Args:
            workflow: The AgentWorkflow instance to get summary for
            
        Returns:
            Dict containing execution statistics and recent history
        """
        return self.workflow_executor.get_workflow_execution_summary(workflow)
    
    # ============================================================================
    # UTILITY METHODS - Backward compatibility and convenience methods
    # ============================================================================
    
    def get_llm_provider(self, agent_config: Dict[str, Any]) -> Optional[object]:
        """
        Create LLM provider instance based on agent configuration
        Delegates to LLMProviderManager for actual implementation
        """
        return self.llm_provider_manager.get_llm_provider(agent_config)
    
    def parse_workflow_graph(self, graph_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse workflow graph into linear execution sequence
        Delegates to WorkflowParser for actual implementation
        """
        return self.workflow_parser.parse_workflow_graph(graph_json)
    
    def find_multiple_inputs_to_node(self, target_node_id: str, graph_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find all nodes that feed into the target node
        Delegates to WorkflowParser for actual implementation
        """
        return self.workflow_parser.find_multiple_inputs_to_node(target_node_id, graph_json)
    
    def aggregate_multiple_inputs(self, input_sources: List[Dict[str, Any]], executed_nodes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate multiple input sources into structured context
        Delegates to WorkflowParser for actual implementation
        """
        return self.workflow_parser.aggregate_multiple_inputs(input_sources, executed_nodes)
    
    def is_docaware_enabled(self, agent_node: Dict[str, Any]) -> bool:
        """
        Check if DocAware is enabled for this agent
        Delegates to DocAwareHandler for actual implementation
        """
        return self.docaware_handler.is_docaware_enabled(agent_node)
    
    def is_websearch_enabled(self, agent_node: Dict[str, Any]) -> bool:
        """
        Check if WebSearch is enabled for this agent
        Delegates to WebSearchHandler for actual implementation
        """
        return self.websearch_handler.is_websearch_enabled(agent_node)
    
    async def craft_conversation_prompt(self, conversation_history: str, agent_node: Dict[str, Any], project_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Craft conversation messages array for an agent including full conversation history
        Delegates to ChatManager for actual implementation
        
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        return await self.chat_manager.craft_conversation_prompt(conversation_history, agent_node, project_id)
    
    async def execute_group_chat_manager(self, chat_manager_node: Dict[str, Any], llm_provider, conversation_history: str, execution_sequence: List[Dict[str, Any]], graph_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute GroupChatManager with tool-based delegation.
        Delegates to ChatManager for actual implementation.
        """
        return await self.chat_manager.execute_group_chat_manager(
            chat_manager_node, llm_provider, conversation_history, execution_sequence, graph_json
        )
    
    async def handle_reflection_connections(self, agent_node, agent_response, graph_json, llm_provider):
        """
        Handle reflection connections for an agent
        Delegates to ReflectionHandler for actual implementation
        """
        return await self.reflection_handler.handle_reflection_connections(
            agent_node, agent_response, graph_json, llm_provider
        )
    
    async def pause_for_human_input(self, workflow, node, executed_nodes, conversation_history, execution_record):
        """
        Pause workflow execution and prepare human input interface data
        Delegates to HumanInputHandler for actual implementation
        """
        return await self.human_input_handler.pause_for_human_input(
            workflow, node, executed_nodes, conversation_history, execution_record
        )
    
    # ============================================================================
    # MODULE ACCESS - Direct access to specialized modules if needed
    # ============================================================================
    
    def get_llm_provider_manager(self) -> LLMProviderManager:
        """Get direct access to LLM provider manager"""
        return self.llm_provider_manager
    
    def get_workflow_parser(self) -> WorkflowParser:
        """Get direct access to workflow parser"""
        return self.workflow_parser
    
    def get_chat_manager(self) -> ChatManager:
        """Get direct access to chat manager"""
        return self.chat_manager
    
    def get_docaware_handler(self) -> DocAwareHandler:
        """Get direct access to DocAware handler"""
        return self.docaware_handler
    
    def get_websearch_handler(self) -> WebSearchHandler:
        """Get direct access to WebSearch handler"""
        return self.websearch_handler
    
    def get_human_input_handler(self) -> HumanInputHandler:
        """Get direct access to human input handler"""
        return self.human_input_handler
    
    def get_workflow_executor(self) -> WorkflowExecutor:
        """Get direct access to workflow executor"""
        return self.workflow_executor
    
    def get_reflection_handler(self) -> ReflectionHandler:
        """Get direct access to reflection handler"""
        return self.reflection_handler