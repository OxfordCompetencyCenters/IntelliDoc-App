"""
Chat Manager
============

Handles group chat management and delegate conversation execution for conversation orchestration.
"""

import logging
import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from asgiref.sync import sync_to_async

from .query_analysis_service import get_query_analysis_service
from .message_protocol import DelegationMessageProtocol, MessageType

logger = logging.getLogger('conversation_orchestrator')


class ChatManager:
    """
    Manages group chat orchestration and delegate conversations
    """
    
    def __init__(self, llm_provider_manager, workflow_parser, docaware_handler, websearch_handler=None):
        self.llm_provider_manager = llm_provider_manager
        self.workflow_parser = workflow_parser
        self.docaware_handler = docaware_handler
        self.websearch_handler = websearch_handler

    def _append_intellidoc_platform_prompt(
        self, parts: List[str], agent_node: Dict[str, Any],
        has_sources: bool = False,
    ) -> None:
        """Append global + per-type IntelliDoc guidance after user system text (not shown in UI)."""
        from .intellidoc_system_prompt import intellidoc_addendum_for_node

        block = intellidoc_addendum_for_node(agent_node, has_sources=has_sources)
        if block:
            parts.append(block)

    def _intellidoc_addendum_string(self, agent_node: Dict[str, Any], has_sources: bool = False) -> str:
        """Return platform addendum for embedding in f-strings (e.g. group chat final prompt)."""
        from .intellidoc_system_prompt import intellidoc_addendum_for_node

        return intellidoc_addendum_for_node(agent_node, has_sources=has_sources)
    
    @staticmethod
    def format_messages_with_file_refs(
        messages: List[Dict[str, Any]], 
        file_references: List[Dict[str, Any]], 
        provider: str
    ) -> List[Dict[str, Any]]:
        """
        Format messages to include file references for different LLM providers.
        File refs are attached only to the most recent user message to avoid
        redundant payloads and match provider semantics (files for the current turn).
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            file_references: List of file reference dicts from full document mode
            provider: LLM provider name ('openai', 'anthropic', 'google')
            
        Returns:
            Modified messages list with file references on the last user message only
        """
        if not file_references:
            return messages
        
        # Index of the last user message: only that turn gets file refs
        last_user_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get('role') == 'user':
                last_user_idx = i
                break
        
        formatted_messages = []
        for idx, msg in enumerate(messages):
            if msg.get('role') != 'user':
                formatted_messages.append(msg)
                continue
            
            # Only attach file refs to the most recent user message
            is_last_user = (idx == last_user_idx)
            if not is_last_user:
                formatted_messages.append(msg)
                continue
            
            raw_content = msg.get('content', '')
            # Guard: if content is already a list (e.g. multi-modal from another path), preserve and append file parts
            if isinstance(raw_content, list):
                logger.warning(
                    "FILE REFS: Last user message already has array content; appending file refs to existing parts"
                )
                content_parts = list(raw_content)
            else:
                content_parts = [{"type": "text", "text": raw_content if isinstance(raw_content, str) else str(raw_content)}]
            
            if provider == 'openai':
                for ref in file_references:
                    content_parts.append({
                        "type": "file",
                        "file": {"file_id": ref['file_id']}
                    })
                formatted_messages.append({"role": "user", "content": content_parts})
            elif provider == 'anthropic':
                # Anthropic Messages API: document block with file_id (see Anthropic Messages API docs)
                for ref in file_references:
                    content_parts.append({
                        "type": "document",
                        "source": {"type": "file", "file_id": ref['file_id']}
                    })
                formatted_messages.append({"role": "user", "content": content_parts})
            elif provider in ('google', 'gemini'):
                for ref in file_references:
                    content_parts.append({
                        "type": "file_data",
                        "file_uri": ref['file_id'],
                        "mime_type": ref.get('file_type', 'application/pdf')
                    })
                formatted_messages.append({"role": "user", "content": content_parts})
            elif provider == 'ollama':
                # Ollama: no file refs needed — content is already inline text
                formatted_messages.append(msg)
            else:
                logger.warning(f"FILE REFS: Unknown provider {provider}, keeping original message format")
                formatted_messages.append(msg)
        
        logger.info(f"FILE REFS: Attached {len(file_references)} file references to last user message for {provider}")
        return formatted_messages

    @staticmethod
    def format_tool_results(
        tool_calls_with_results: List[Dict[str, Any]],
        provider: str,
    ) -> List[Dict[str, Any]]:
        """
        Build the provider-specific messages that feed tool results back into
        the conversation so the LLM can continue.

        Each item in *tool_calls_with_results* must have:
            id, name, arguments (dict), result (str)

        Returns a list of message dicts to append to the conversation.
        """
        messages: List[Dict[str, Any]] = []
        if provider == "openai":
            for tc in tool_calls_with_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tc["result"],
                })
        elif provider == "anthropic":
            tool_result_blocks = []
            for tc in tool_calls_with_results:
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": tc["result"],
                })
            messages.append({"role": "user", "content": tool_result_blocks})
        elif provider in ("google", "gemini"):
            parts = []
            for tc in tool_calls_with_results:
                parts.append({
                    "functionResponse": {
                        "name": tc["name"],
                        "response": {"result": tc["result"]},
                    }
                })
            messages.append({"role": "function", "parts": parts})
        else:
            for tc in tool_calls_with_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tc["result"],
                })
        return messages

    @staticmethod
    def format_assistant_tool_call_message(
        tool_calls: List[Dict[str, Any]],
        provider: str,
        text: str = "",
    ) -> Dict[str, Any]:
        """
        Build the assistant message that records which tools the LLM chose.
        Required by OpenAI/Anthropic between the assistant turn and the tool
        results turn.
        """
        import json as _json
        if provider == "openai":
            return {
                "role": "assistant",
                "content": text or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": _json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in tool_calls
                ],
            }
        elif provider == "anthropic":
            content_blocks = []
            if text:
                content_blocks.append({"type": "text", "text": text})
            for tc in tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["arguments"],
                })
            return {"role": "assistant", "content": content_blocks}
        elif provider in ("google", "gemini"):
            parts = []
            if text:
                parts.append({"text": text})
            for tc in tool_calls:
                parts.append({
                    "functionCall": {
                        "name": tc["name"],
                        "args": tc["arguments"],
                    }
                })
            return {"role": "model", "parts": parts}
        elif provider == "ollama":
            # Ollama uses same format as OpenAI for tool calls
            return {
                "role": "assistant",
                "content": text or "",
                "tool_calls": [
                    {
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"] if isinstance(tc["arguments"], dict) else _json.loads(tc["arguments"]),
                        },
                    }
                    for tc in tool_calls
                ],
            }
        else:
            return {"role": "assistant", "content": text or ""}

    async def execute_group_chat_manager_with_multiple_inputs(self, chat_manager_node: Dict[str, Any], llm_provider, input_sources: List[Dict[str, Any]], executed_nodes: Dict[str, str], execution_sequence: List[Dict[str, Any]], graph_json: Dict[str, Any], project_id: Optional[str] = None, project: Optional[Any] = None, execution_id: Optional[str] = None, event_callback=None) -> Dict[str, Any]:
        """
        Execute GroupChatManager using tool-based delegation.

        Two-phase approach:
        Phase 1 — The manager LLM produces a plan (no tools).
        Phase 2 — The manager LLM uses per-delegate tools (``tasks: string[]``)
                  to dispatch work; handlers run in parallel when multiple
                  tool calls appear in a single turn.

        Delegates reuse the existing doc-tool-calling loop when
        ``doc_tool_calling`` is enabled on the delegate node.
        """
        from .delegate_tool_executor import execute_tool_based_delegation

        manager_name = chat_manager_node.get('data', {}).get('name', 'Chat Manager')
        chat_manager_id = chat_manager_node.get('id')

        logger.info(f"👥 GROUP CHAT MANAGER: Starting tool-based delegation for {manager_name}")
        logger.info(f"📥 GROUP CHAT MANAGER: Processing {len(input_sources)} input sources")
        
        # Resolve project for API keys if not provided
        if project is None and project_id:
            from users.models import IntelliDocProject
            try:
                project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
            except IntelliDocProject.DoesNotExist:
                logger.warning(f"⚠️ GROUP CHAT MANAGER: Project {project_id} not found")

        # Discover connected delegate nodes
        delegate_nodes = self._discover_delegate_nodes(chat_manager_id, graph_json)
        if not delegate_nodes:
            error_message = (
                f"GroupChatManager {manager_name} has no connected delegate agents. "
                "Please connect DelegateAgent nodes via delegate edges."
            )
            logger.error(f"❌ GROUP CHAT MANAGER: {error_message}")
            raise Exception(error_message)

        # Build input context from upstream sources
        aggregated_context = self.workflow_parser.aggregate_multiple_inputs(
            input_sources, executed_nodes
        )
        input_context = self.workflow_parser.format_multiple_inputs_prompt(
            aggregated_context
        )

        # #region agent log
        logger.info(f"🔬 DEBUG-6451c8 [H5] Input context: len={len(input_context)}, preview={input_context[:200]}, delegates={[d.get('data',{}).get('name','?') for d in delegate_nodes]}, project_id={project_id}")
        # #endregion
        result = await execute_tool_based_delegation(
            chat_manager_node=chat_manager_node,
            llm_provider=llm_provider,
            delegate_nodes=delegate_nodes,
            input_context=input_context,
            project_id=project_id,
            project=project,
            llm_provider_manager=self.llm_provider_manager,
            execution_id=execution_id,
            event_callback=event_callback,
            websearch_handler=self.websearch_handler,
            docaware_handler=self.docaware_handler,
        )
        result["input_count"] = aggregated_context.get("input_count", 1)
        return result

    # ── Delegate-node discovery (shared helper) ──────────────────
    def _discover_delegate_nodes(
        self, chat_manager_id: str, graph_json: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find DelegateAgent nodes connected via 'delegate' edges."""
        edges = graph_json.get("edges", [])
        all_nodes = graph_json.get("nodes", [])
        delegate_nodes: List[Dict[str, Any]] = []
        connected_ids: set = set()

        for edge in edges:
            if edge.get("type") != "delegate":
                continue
            if edge.get("source") == chat_manager_id:
                target_id = edge.get("target")
            elif edge.get("target") == chat_manager_id:
                target_id = edge.get("source")
            else:
                continue
            if target_id in connected_ids:
                continue
            for node in all_nodes:
                if node.get("id") == target_id and node.get("type") == "DelegateAgent":
                    connected_ids.add(target_id)
                    delegate_nodes.append(node)
                    logger.info(
                        f"🔗 GROUP CHAT MANAGER: Found delegate "
                        f"{node.get('data', {}).get('name', target_id)}"
                    )

        logger.info(
            f"🤝 GROUP CHAT MANAGER: Found {len(delegate_nodes)} connected delegates"
        )
        return delegate_nodes

    # ── Single-input convenience wrapper ─────────────────────────
    async def execute_group_chat_manager(
        self,
        chat_manager_node: Dict[str, Any],
        llm_provider,
        conversation_history: str,
        execution_sequence: List[Dict[str, Any]],
        graph_json: Dict[str, Any],
        project_id: Optional[str] = None,
        project=None,
    ) -> Dict[str, Any]:
        """
        Single-input GroupChatManager entry point.

        Wraps the conversation history into the multi-input shape and
        delegates to ``execute_group_chat_manager_with_multiple_inputs``.
        """
        input_sources = [{
            "node_id": "conversation_input",
            "node_name": "Conversation",
            "node_type": "conversation",
        }]
        executed_nodes = {"conversation_input": conversation_history}

        return await self.execute_group_chat_manager_with_multiple_inputs(
            chat_manager_node=chat_manager_node,
            llm_provider=llm_provider,
            input_sources=input_sources,
            executed_nodes=executed_nodes,
            execution_sequence=execution_sequence,
            graph_json=graph_json,
            project_id=project_id,
            project=project,
        )

    async def craft_conversation_prompt(self, conversation_history: str, agent_node: Dict[str, Any], project_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Craft conversation messages array for an agent including full conversation history
        Enhanced with DocAware RAG capabilities
        
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        from .message_converter import parse_conversation_history_to_messages
        
        agent_name = agent_node.get('data', {}).get('name', 'Agent')
        agent_system_message = agent_node.get('data', {}).get('system_message', '')
        agent_instructions = agent_node.get('data', {}).get('instructions', '')
        
        # Build system message
        system_parts = []
        if agent_system_message:
            system_parts.append(agent_system_message)
        if agent_instructions:
            system_parts.append(f"Instructions for {agent_name}: {agent_instructions}")
        # IntelliDoc platform prompt is appended AFTER sources are resolved (see below)

        # 📚 DOCAWARE INTEGRATION: Add chunk-based document context if enabled
        # Skip when the agent enters the tool-calling path (doc_tool_calling,
        # web_search_enabled, or doc_aware as tool) -- the LLM will obtain
        # information through tools.
        agent_data_da = agent_node.get('data', {})
        _da_will_use_tool_path = (
            agent_data_da.get('doc_tool_calling')
            or agent_data_da.get('web_search_enabled')
            or agent_data_da.get('doc_aware')
        )
        document_context = ""
        if self.docaware_handler.is_docaware_enabled(agent_node) and project_id and not _da_will_use_tool_path:
            try:
                search_query = self.docaware_handler.extract_query_from_conversation(conversation_history)
                
                if search_query:
                    logger.info(f"📚 DOCAWARE: Single agent {agent_name} using conversation-based search query")
                    logger.info(f"📚 DOCAWARE: Query: {search_query[:100]}...")
                    
                    document_context = await self.docaware_handler.get_docaware_context_from_conversation_query(
                        agent_node, search_query, project_id, conversation_history
                    )
                    
                    if document_context:
                        logger.info(f"📚 DOCAWARE: Added document context to single agent {agent_name} ({len(document_context)} chars)")
                else:
                    logger.warning(f"📚 DOCAWARE: No search query could be extracted from conversation history for {agent_name}")
                    
            except Exception as e:
                logger.error(f"❌ DOCAWARE: Failed to get document context for single agent {agent_name}: {e}")
                import traceback
                logger.error(f"❌ DOCAWARE: Traceback: {traceback.format_exc()}")
        elif _da_will_use_tool_path:
            logger.info(f"📚 DOCAWARE: Skipping context injection for {agent_name} — agent uses tool-calling path")
        
        # Add chunk-based document context to system message if available
        if document_context:
            system_parts.append("\n=== RELEVANT DOCUMENTS ===")
            system_parts.append("IMPORTANT: The following documents contain the ACTUAL CONTENT of the research paper you are reviewing.")
            system_parts.append("These documents ARE the paper content - use them directly in your analysis and response.")
            system_parts.append("You have full access to the paper content through these documents.")
            system_parts.append("")
            system_parts.append(document_context)
            system_parts.append("=== END DOCUMENTS ===")
            system_parts.append("\nCRITICAL: Use the document content provided above to conduct your review. The documents above ARE the paper content.")
        
        # 📎 FILE ATTACHMENTS: Independent of DocAware - send entire files via LLM File API
        file_attachment_refs: Optional[List[Dict[str, Any]]] = None
        if self.docaware_handler.is_file_attachments_enabled(agent_node) and project_id:
            # NOTE: Any failure to prepare file attachments is treated as a hard error
            # and will bubble up to the workflow executor, causing the node to fail.
            logger.info(f"📎 FILE ATTACHMENTS: Getting file references for single agent {agent_name}")
            attachment_result = await self.docaware_handler.get_file_attachment_references(
                agent_node, project_id
            )
            
            if attachment_result.get('file_references'):
                file_attachment_refs = attachment_result['file_references']
                logger.info(f"📎 FILE ATTACHMENTS: Retrieved {len(file_attachment_refs)} project-level file references for {agent_name}")
            else:
                logger.warning(f"⚠️ FILE ATTACHMENTS: No project-level file references available for {agent_name}")
                if attachment_result.get('warning'):
                    logger.warning(f"⚠️ FILE ATTACHMENTS: {attachment_result['warning']}")
        
        # Merge any node-scoped inline attachments (immediately uploaded to provider)
        agent_data = agent_node.get('data', {})
        inline_attachments = agent_data.get('inline_file_attachments') or []
        if inline_attachments:
            provider = agent_data.get('llm_provider', 'openai').lower()
            # Validate inline file_ids against the current API key (they may be stale after key rotation)
            if project_id:
                inline_attachments = await self.docaware_handler.validate_and_reupload_inline_attachments(
                    inline_attachments, provider, project_id
                )
            if not file_attachment_refs:
                file_attachment_refs = []
            for att in inline_attachments:
                att_provider = (att.get('provider') or provider).lower()
                # Treat gemini as google for file service / message formatting
                normalized_provider = 'google' if att_provider == 'gemini' else att_provider
                if normalized_provider != ('google' if provider in ('google', 'gemini') else provider):
                    # Skip attachments for a different provider
                    continue
                file_id = att.get('file_id')
                if not file_id:
                    continue
                file_attachment_refs.append({
                    'file_id': file_id,
                    'filename': att.get('filename', 'attachment'),
                    'document_id': att.get('id'),
                    'provider': provider,
                    'file_type': att.get('mime_type', 'application/octet-stream'),
                    'file_size': att.get('size')
                })
            if inline_attachments:
                logger.info(
                    f"📎 FILE ATTACHMENTS: Added {len(inline_attachments)} node-level attachments for {agent_name}"
                )

        # If we have any attachments (project-level or node-scoped), add indicator to system message
        if file_attachment_refs:
            system_parts.append("\n=== FILE ATTACHMENTS ===")
            system_parts.append("The following documents have been attached for your reference.")
            for ref in file_attachment_refs:
                system_parts.append(f"- {ref.get('filename', 'unknown')} ({ref.get('file_type', 'document')})")
            system_parts.append("=== END FILE ATTACHMENTS ===")
            system_parts.append("\nAnalyze the full document content provided in the attachments to complete your task.")
        
        # 🌐 WEBSEARCH INTEGRATION: Add web search context if enabled
        # URL mode: always inject fetched content directly into the context window
        # (no tool-call loop). General/domain modes still use the tool-calling path.
        agent_data_ws = agent_node.get('data', {})
        _ws_mode = agent_data_ws.get('web_search_mode', 'general')
        _will_use_tool_path = agent_data_ws.get('doc_tool_calling') or (
            agent_data_ws.get('web_search_enabled') and _ws_mode != 'urls'
        )
        websearch_context = ""
        if self.websearch_handler and self.websearch_handler.is_websearch_enabled(agent_node) and project_id and (not _will_use_tool_path or _ws_mode == 'urls'):
            try:
                logger.info(f"🌐 WEBSEARCH: Single agent {agent_name} - WebSearch enabled (context augmentation)")
                websearch_context = await self.websearch_handler.get_websearch_context(
                    agent_node, conversation_history, project_id
                )
                
                if websearch_context:
                    logger.info(f"🌐 WEBSEARCH: Added web context to single agent {agent_name} ({len(websearch_context)} chars)")
                    
            except Exception as e:
                logger.error(f"❌ WEBSEARCH: Failed to get web context for single agent {agent_name}: {e}")
                import traceback
                logger.error(f"❌ WEBSEARCH: Traceback: {traceback.format_exc()}")
        
        # Add web search context to system message if available
        if websearch_context:
            system_parts.append("\n=== WEB SEARCH RESULTS ===")
            system_parts.append("The following information was retrieved from web search and may contain recent or relevant information:")
            system_parts.append("")
            system_parts.append(websearch_context)
            system_parts.append("=== END WEB SEARCH ===")

        # Append IntelliDoc platform prompt — now that we know which sources
        # are available, citation instructions are included only when needed.
        _has_sources = bool(document_context or websearch_context or file_attachment_refs
                           or _da_will_use_tool_path or _will_use_tool_path)
        self._append_intellidoc_platform_prompt(system_parts, agent_node, has_sources=_has_sources)

        # Build full system message
        system_message = "\n".join(system_parts) if system_parts else None

        # Add final instruction to conversation history
        enhanced_history = conversation_history
        if enhanced_history.strip():
            enhanced_history += f"\n{agent_name}: Please provide your response based on the conversation history above."
        else:
            enhanced_history = f"{agent_name}: Please provide your response."
        
        # Parse conversation history to messages array
        messages = parse_conversation_history_to_messages(
            conversation_history=enhanced_history,
            system_message=system_message,
            include_system=True
        )
        
        # Return dict with file references if file attachments are enabled, otherwise return messages list
        if file_attachment_refs:
            return {
                'messages': messages,
                'file_references': file_attachment_refs,
                'mode': 'file_attachments',
                'provider': agent_node.get('data', {}).get('llm_provider', 'openai')
            }
        
        return messages
    
    async def craft_conversation_prompt_with_docaware(
        self, 
        aggregated_context: Dict[str, Any], 
        agent_node: Dict[str, Any], 
        project_id: Optional[str] = None, 
        conversation_history: str = ""
    ) -> Dict[str, Any]:
        """
        Enhanced conversation messages crafting with DocAware using aggregated input as search query.
        
        DocAware handles chunk-based RAG. File attachments are handled independently.
        
        Args:
            aggregated_context: Output from aggregate_multiple_inputs containing all agent inputs
            agent_node: Agent node configuration
            project_id: Project ID for DocAware search
            conversation_history: Traditional conversation history (fallback)
        
        Returns:
            Dict with:
            - messages: List of message dicts with 'role' and 'content' keys
            - file_references: (Optional) List of file references for File Attachments
            - mode: 'chunks' or 'file_attachments'
            - provider: LLM provider name
        """
        from .message_converter import parse_conversation_history_to_messages
        
        agent_name = agent_node.get('data', {}).get('name', 'Agent')
        agent_system_message = agent_node.get('data', {}).get('system_message', '')
        agent_instructions = agent_node.get('data', {}).get('instructions', '')
        
        # Build system message
        system_parts = []
        if agent_system_message:
            system_parts.append(agent_system_message)
        if agent_instructions:
            system_parts.append(f"Instructions for {agent_name}: {agent_instructions}")
        # IntelliDoc platform prompt is appended AFTER sources are resolved (see below)

        # 📚 DOCAWARE INTEGRATION: Chunk-based document context
        # Skip when the agent enters the tool-calling path (doc_tool_calling,
        # web_search_enabled, or doc_aware as tool) -- the LLM will obtain
        # information through tools.
        agent_data_da = agent_node.get('data', {})
        _da_will_use_tool_path = (
            agent_data_da.get('doc_tool_calling')
            or agent_data_da.get('web_search_enabled')
            or agent_data_da.get('doc_aware')
        )
        document_context = ""
        if self.docaware_handler.is_docaware_enabled(agent_node) and project_id and not _da_will_use_tool_path:
            try:
                search_query = self.docaware_handler.extract_search_query_from_aggregated_input(aggregated_context)
                
                if search_query:
                    logger.info(f"📚 DOCAWARE: Using aggregated input as search query for {agent_name}")
                    logger.info(f"📚 DOCAWARE: Search query: {search_query[:100]}...")
                    
                    document_context = await self.docaware_handler.get_docaware_context_from_query(
                        agent_node, search_query, project_id, aggregated_context
                    )
                    
                    if document_context:
                        logger.info(f"📚 DOCAWARE: Added document context to {agent_name} ({len(document_context)} chars)")
                else:
                    logger.warning(f"📚 DOCAWARE: No search query could be extracted from aggregated input for {agent_name}")
                    
            except Exception as e:
                logger.error(f"❌ DOCAWARE: Failed to get document context for {agent_name}: {e}")
                import traceback
                logger.error(f"❌ DOCAWARE: Traceback: {traceback.format_exc()}")
        elif _da_will_use_tool_path:
            logger.info(f"📚 DOCAWARE: Skipping context injection for {agent_name} — agent uses tool-calling path")
        
        # Add chunk-based document context to system message if available
        if document_context:
            system_parts.append("\n=== RELEVANT DOCUMENTS ===")
            system_parts.append("IMPORTANT: The following documents contain the ACTUAL CONTENT of the research paper you are reviewing.")
            system_parts.append("These documents ARE the paper content - use them directly in your analysis and response.")
            system_parts.append("You have full access to the paper content through these documents.")
            system_parts.append("")
            system_parts.append(document_context)
            system_parts.append("=== END DOCUMENTS ===")
            system_parts.append("\nCRITICAL: Use the document content provided above to conduct your review. The documents above ARE the paper content.")
        
        # 📎 FILE ATTACHMENTS: Independent of DocAware - send entire files via LLM File API
        file_attachment_refs: Optional[List[Dict[str, Any]]] = None
        if self.docaware_handler.is_file_attachments_enabled(agent_node) and project_id:
            logger.info(f"📎 FILE ATTACHMENTS: Getting file references for {agent_name}")
            attachment_result = await self.docaware_handler.get_file_attachment_references(
                agent_node, project_id
            )
            
            if attachment_result.get('file_references'):
                file_attachment_refs = attachment_result['file_references']
                logger.info(f"📎 FILE ATTACHMENTS: Retrieved {len(file_attachment_refs)} project-level file references for {agent_name}")
            else:
                logger.warning(f"⚠️ FILE ATTACHMENTS: No project-level file references available for {agent_name}")
                if attachment_result.get('warning'):
                    logger.warning(f"⚠️ FILE ATTACHMENTS: {attachment_result['warning']}")

        # Merge any node-scoped inline attachments
        agent_data = agent_node.get('data', {})
        inline_attachments = agent_data.get('inline_file_attachments') or []
        if inline_attachments:
            provider = agent_data.get('llm_provider', 'openai').lower()
            # Validate inline file_ids against the current API key (they may be stale after key rotation)
            if project_id:
                inline_attachments = await self.docaware_handler.validate_and_reupload_inline_attachments(
                    inline_attachments, provider, project_id
                )
            if not file_attachment_refs:
                file_attachment_refs = []
            for att in inline_attachments:
                att_provider = (att.get('provider') or provider).lower()
                normalized_provider = 'google' if att_provider == 'gemini' else att_provider
                if normalized_provider != ('google' if provider in ('google', 'gemini') else provider):
                    continue
                file_id = att.get('file_id')
                if not file_id:
                    continue
                file_attachment_refs.append({
                    'file_id': file_id,
                    'filename': att.get('filename', 'attachment'),
                    'document_id': att.get('id'),
                    'provider': provider,
                    'file_type': att.get('mime_type', 'application/octet-stream'),
                    'file_size': att.get('size')
                })
            if inline_attachments:
                logger.info(
                    f"📎 FILE ATTACHMENTS: Added {len(inline_attachments)} node-level attachments for {agent_name}"
                )

        if file_attachment_refs:
            system_parts.append("\n=== FILE ATTACHMENTS ===")
            system_parts.append("The following documents have been attached for your reference.")
            for ref in file_attachment_refs:
                system_parts.append(f"- {ref.get('filename', 'unknown')} ({ref.get('file_type', 'document')})")
            system_parts.append("=== END FILE ATTACHMENTS ===")
            system_parts.append("\nAnalyze the full document content provided in the attachments to complete your task.")
        
        # 🌐 WEBSEARCH INTEGRATION: Add web search context if enabled
        # URL mode: always inject fetched content directly into the context window.
        # General/domain modes still use the tool-calling path.
        agent_data_ws = agent_node.get('data', {})
        _ws_mode = agent_data_ws.get('web_search_mode', 'general')
        _will_use_tool_path = agent_data_ws.get('doc_tool_calling') or (
            agent_data_ws.get('web_search_enabled') and _ws_mode != 'urls'
        )
        websearch_context = ""
        if self.websearch_handler and self.websearch_handler.is_websearch_enabled(agent_node) and project_id and (not _will_use_tool_path or _ws_mode == 'urls'):
            try:
                logger.info(f"🌐 WEBSEARCH: Agent {agent_name} with aggregated input - WebSearch enabled (context augmentation, mode={_ws_mode})")
                if _ws_mode == 'urls':
                    # URL mode: use aggregated input as RAG query so Milvus
                    # returns chunks relevant to A1+A2's outputs, not generic content.
                    agg_query = self.websearch_handler.extract_search_query_from_aggregated_input(aggregated_context)
                    websearch_context = await self.websearch_handler.get_websearch_context(
                        agent_node, agg_query or "", project_id
                    )
                else:
                    search_query = self.websearch_handler.extract_search_query_from_aggregated_input(aggregated_context)
                    if search_query:
                        websearch_context = await self.websearch_handler.get_websearch_context_from_query(
                            agent_node, search_query, project_id
                        )

                if websearch_context:
                    logger.info(f"🌐 WEBSEARCH: Added web context to agent {agent_name} ({len(websearch_context)} chars)")
                    
            except Exception as e:
                logger.error(f"❌ WEBSEARCH: Failed to get web context for agent {agent_name}: {e}")
                import traceback
                logger.error(f"❌ WEBSEARCH: Traceback: {traceback.format_exc()}")
        
        # Add web search context to system message if available
        if websearch_context:
            system_parts.append("\n=== WEB SEARCH RESULTS ===")
            system_parts.append("The following information was retrieved from web search and may contain recent or relevant information:")
            system_parts.append("")
            system_parts.append(websearch_context)
            system_parts.append("=== END WEB SEARCH ===")

        # Append IntelliDoc platform prompt — citation instructions only when sources exist.
        # For multi-input nodes, upstream agent citations also count as sources.
        _has_sources_multi = bool(
            document_context or websearch_context or file_attachment_refs
            or _da_will_use_tool_path or _will_use_tool_path
            or aggregated_context.get('input_count', 0) > 0
        )
        self._append_intellidoc_platform_prompt(system_parts, agent_node, has_sources=_has_sources_multi)

        # Build full system message
        system_message = "\n".join(system_parts) if system_parts else None

        # Build user message with aggregated input and conversation history
        user_parts = []
        
        # Add aggregated input context
        if aggregated_context['input_count'] > 0:
            formatted_context = self.workflow_parser.format_multiple_inputs_prompt(aggregated_context)
            user_parts.append("=== INPUT FROM CONNECTED AGENTS ===")
            user_parts.append(formatted_context)
            user_parts.append("=== END INPUT ===")
        
        # Add conversation history if available.
        # For multi-input nodes, direct-input agents are already in
        # INPUT FROM CONNECTED AGENTS with proper citations.  Including
        # them again here would duplicate content and leave orphaned [N]
        # citation markers (no reference definitions).  Keep only the
        # Start Node prompt and any intermediate agents.
        if conversation_history.strip():
            filtered_history = conversation_history
            if aggregated_context['input_count'] > 1:
                direct_input_names = {
                    inp['name'] for inp in aggregated_context.get('all_inputs', [])
                }
                if direct_input_names:
                    cut_positions = []
                    for name in direct_input_names:
                        pos = conversation_history.find(f"\n{name}: ")
                        if pos != -1:
                            cut_positions.append(pos)
                    if cut_positions:
                        filtered_history = conversation_history[:min(cut_positions)]
                        logger.info(
                            f"🔀 MULTI-INPUT DEDUP: Filtered {len(direct_input_names)} "
                            f"direct-input agents from conversation_history for {agent_name}, "
                            f"preserved {len(filtered_history)}/{len(conversation_history)} chars"
                        )

            if filtered_history.strip():
                user_parts.append("\n=== ORIGINAL USER REQUEST ===")
                user_parts.append(filtered_history)
                user_parts.append("=== END USER REQUEST ===")
        
        # Add final instruction
        user_parts.append(f"\n{agent_name}, please analyze the inputs and provide your response:")
        
        user_content = "\n".join(user_parts) if user_parts else f"{agent_name}, please provide your response."
        
        # Build messages array
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_content})
        
        # Return dict with messages and optional file references for file attachments
        result: Dict[str, Any] = {
            'messages': messages,
            'mode': 'file_attachments' if file_attachment_refs else 'chunks'
        }
        
        if file_attachment_refs:
            result['file_references'] = file_attachment_refs
            result['provider'] = agent_node.get('data', {}).get('llm_provider', 'openai')
            logger.info(f"📎 FILE ATTACHMENTS: Including {len(result['file_references'])} file references in result")
        
        return result
    
