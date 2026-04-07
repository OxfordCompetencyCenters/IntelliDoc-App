"""
Delegate Tool Executor
======================

Provides the machinery for tool-based GroupChatManager → Delegate delegation:

1. ``build_delegate_tools``  — one OpenAI-style function tool per connected
   DelegateAgent (``tasks: string[]``).
2. ``run_delegate_doc_tool_loop`` — runs the existing doc-tool-calling loop
   for a single delegate (plan → tool calls → synthesis), reusing
   ``document_tool_service``.
3. ``execute_tool_based_delegation`` — two-phase orchestration:
   Phase 1 (planning) → Phase 2 (tool loop with parallel delegate handlers).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from asgiref.sync import sync_to_async
from django.utils import timezone

logger = logging.getLogger("conversation_orchestrator")

MAX_TOOL_NAME_LEN = 64
MAX_DELEGATION_ITERATIONS = 10
MAX_DELEGATE_TOOL_CALLS_PER_TURN = 10


# ── helpers ──────────────────────────────────────────────────────────

def _sanitize_delegate_name(raw: str) -> str:
    """Turn a delegate name / id into a valid tool name (^[a-zA-Z0-9_-]{1,64}$)."""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", raw.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    prefix = "delegate__"
    max_body = MAX_TOOL_NAME_LEN - len(prefix)
    return f"{prefix}{name[:max_body]}"


# ── 1. Build per-delegate tools ──────────────────────────────────────

def build_delegate_tools(
    delegate_nodes: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Build one OpenAI-format function tool per connected delegate.

    Returns
    -------
    tools : list[dict]
        Tool definitions (``tasks: string[]``).
    tool_map : dict[str, dict]
        Mapping  tool_name  →  delegate_node dict.
    """
    tools: List[Dict[str, Any]] = []
    tool_map: Dict[str, Dict[str, Any]] = {}
    seen_names: set = set()

    for node in delegate_nodes:
        data = node.get("data", {})
        delegate_name = data.get("name", node.get("id", "delegate"))
        raw_tool_name = _sanitize_delegate_name(delegate_name)

        unique_name = raw_tool_name
        counter = 2
        while unique_name in seen_names:
            suffix = f"_{counter}"
            unique_name = raw_tool_name[: MAX_TOOL_NAME_LEN - len(suffix)] + suffix
            counter += 1
        seen_names.add(unique_name)

        description = data.get("description", "")
        if not description:
            description = data.get("system_message", f"Delegate agent: {delegate_name}")
        description = f"{delegate_name}: {description}"
        if data.get("doc_tool_calling"):
            doc_files = data.get("doc_tool_calling_documents")
            if isinstance(doc_files, list) and doc_files:
                description += f" [Has document access: {', '.join(doc_files[:5])}]"
            else:
                description += " [Has access to all project documents]"

        tools.append({
            "type": "function",
            "function": {
                "name": unique_name,
                "description": description[:1024],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "List of task instructions to send to this delegate. "
                                "Each string is a self-contained subtask."
                            ),
                        }
                    },
                    "required": ["tasks"],
                },
            },
        })
        tool_map[unique_name] = node

    logger.info(f"🔧 DELEGATE TOOLS: Built {len(tools)} delegate tools")
    return tools, tool_map


# ── 2. Run doc-tool loop for a single delegate ──────────────────────

async def run_delegate_doc_tool_loop(
    delegate_node: Dict[str, Any],
    tasks: List[str],
    project_id: str,
    llm_provider_manager,
    manager_plan: str = "",
    fallback_llm=None,
    project=None,
    event_callback=None,
    websearch_handler=None,
    docaware_handler=None,
) -> str:
    """
    Execute a delegate's work using the existing doc-tool-calling loop.

    The delegate receives a system prompt built from its node config, a user
    message containing the tasks (and the manager plan for context), and then
    enters the same plan → tool-call → synthesis loop used by standalone
    agents when ``doc_tool_calling`` is enabled.

    If ``doc_tool_calling`` is *not* enabled on the delegate node, a single
    LLM call is made instead (no document tools).
    """
    from . import document_tool_service
    from .chat_manager import ChatManager

    data = delegate_node.get("data", {})
    delegate_name = data.get("name", "Delegate")
    delegate_config = {
        "llm_provider": data.get("llm_provider", "openai"),
        "llm_model": data.get("llm_model", "gpt-4"),
    }
    provider_name = delegate_config["llm_provider"]

    delegate_llm = None
    try:
        delegate_llm = await llm_provider_manager.get_llm_provider(
            delegate_config, project
        )
    except Exception as e:
        logger.warning(
            f"⚠️ DELEGATE TOOL EXEC: Could not create provider for {delegate_name}: {e}"
        )
    if not delegate_llm:
        delegate_llm = fallback_llm
    if not delegate_llm:
        return f"[Error: no LLM provider available for delegate {delegate_name}]"

    system_message = data.get("system_message", "You are a helpful specialized agent.")
    from .intellidoc_system_prompt import intellidoc_addendum_for_node
    platform_addendum = intellidoc_addendum_for_node(delegate_node)

    system_parts = [
        f"You are {delegate_name}, a specialized delegate agent.",
        f"System Message: {system_message}",
    ]
    if platform_addendum:
        system_parts.append(platform_addendum)

    task_block = "\n".join(f"- {t}" for t in tasks)
    user_content = f"Tasks assigned to you:\n{task_block}"
    if manager_plan:
        user_content = (
            f"Overall plan (for context):\n{manager_plan}\n\n{user_content}"
        )

    base_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": "\n".join(system_parts)},
        {"role": "user", "content": user_content},
    ]

    doc_tool_calling_enabled = data.get("doc_tool_calling", False)
    # #region agent log
    logger.info(f"🔬 DEBUG-6451c8 [H2] Delegate start: name={delegate_name}, doc_tool_calling={doc_tool_calling_enabled}, project_id={project_id}, tasks={len(tasks)}, has_llm={delegate_llm is not None}, provider={provider_name}")
    # #endregion

    # --- Build tools (document tools + web search + DocAware) ---
    _ws_enabled = websearch_handler and websearch_handler.is_websearch_enabled(delegate_node)
    _da_enabled = docaware_handler and docaware_handler.is_docaware_enabled(delegate_node)

    if (not doc_tool_calling_enabled and not _ws_enabled and not _da_enabled) or not project_id:
        logger.info(
            f"🤝 DELEGATE TOOL EXEC [{delegate_name}]: no tool calling; single LLM call"
        )
        resp = await delegate_llm.generate_response(messages=base_messages)
        if resp.error:
            return f"[Error from {delegate_name}: {resp.error}]"
        return resp.text.strip()

    tools, tool_map, title_map = [], {}, {}
    doc_tool_selected = None
    if doc_tool_calling_enabled:
        doc_tool_selected = data.get("doc_tool_calling_documents")
        tools, tool_map, title_map = await document_tool_service.build_document_tools(
            project_id, selected_filenames=doc_tool_selected
        )
        tools.extend(document_tool_service.build_document_info_tools())

    # Pre-warm: upload all tool documents to LLM provider in parallel
    if tool_map:
        try:
            from .llm_file_service import LLMFileUploadService
            from users.models import ProjectDocument as _PWDoc, IntelliDocProject as _PWProj
            _pw_proj = await sync_to_async(_PWProj.objects.get)(project_id=project_id)
            _file_svc = LLMFileUploadService(_pw_proj)
            _doc_ids = list(set(tool_map.values()))
            _pw_docs = await sync_to_async(list)(_PWDoc.objects.filter(document_id__in=_doc_ids))
            _upload_tasks = [_file_svc._upload_to_provider(doc, provider_name) for doc in _pw_docs]
            _results = await asyncio.gather(*_upload_tasks, return_exceptions=True)
            _ok = sum(1 for r in _results if not isinstance(r, Exception))
            logger.info(f"🔥 PRE-WARM (delegate): Uploaded {_ok}/{len(_pw_docs)} documents to {provider_name}")
        except Exception as pw_err:
            logger.warning(f"⚠️ PRE-WARM (delegate): Failed: {pw_err}")

    # URL mode: content is already injected into the context window by
    # chat_manager — no tool registration needed here.
    url_tool_map: Dict[str, str] = {}
    ws_tool = None
    has_web_tools = False
    if websearch_handler:
        if websearch_handler.get_websearch_mode(delegate_node) == 'urls':
            logger.info("🌐 WEB TOOLS (delegate): URL mode — content injected into context window, no tool needed")
        else:
            ws_tool = websearch_handler.build_websearch_tool(delegate_node)
            if ws_tool:
                tools.append(ws_tool)
                title_map[ws_tool["function"]["name"]] = "Web Search"
                has_web_tools = True

    da_tool = docaware_handler.build_docaware_tool(delegate_node) if docaware_handler else None
    if da_tool:
        tools.append(da_tool)
        title_map[da_tool["function"]["name"]] = "Document Search"

    if not tools:
        logger.warning(
            f"⚠️ DELEGATE TOOL EXEC [{delegate_name}]: No tools available; single call"
        )
        resp = await delegate_llm.generate_response(messages=base_messages)
        if resp.error:
            return f"[Error from {delegate_name}: {resp.error}]"
        return resp.text.strip()

    tool_descriptions = "\n".join(
        f"- {t['function']['name']}: {t['function']['description'][:200]}"
        for t in tools
    )

    # Fetch prior memory context for the delegate's planning prompt
    memory_section = ""
    summary_rows = []
    try:
        from asgiref.sync import sync_to_async
        from users.models import ProjectDocumentSummary
        summary_rows = await sync_to_async(list)(
            ProjectDocumentSummary.objects.filter(
                document__project__project_id=project_id,
            ).values_list(
                "document__document_id", "memory", "citation",
                "short_summary", "document__original_filename",
            )
        )
        memory_lines = []
        for did, mem, cit, short_sum, orig_filename in summary_rows:
            if not mem or not isinstance(mem, list) or len(mem) == 0:
                continue
            doc_label = str(did)[:8]
            if cit and isinstance(cit, dict) and cit.get("title"):
                doc_label = cit["title"][:60]
            topics = [e.get("query", "")[:50] for e in mem if e.get("query")]
            memory_lines.append(
                f"  - {doc_label}: {len(mem)} prior insights on: {'; '.join(topics)}"
            )
        if memory_lines:
            memory_section = (
                "\n\nPRIOR KNOWLEDGE (from previous analyses):\n"
                + "\n".join(memory_lines)
                + "\n\nUse this prior knowledge to ask more targeted, "
                "non-redundant questions."
            )
    except Exception as mem_err:
        logger.warning(f"⚠️ DELEGATE TOOL EXEC [{delegate_name}]: Could not fetch memory context: {mem_err}")

    # Build document summary section for delegate planning
    doc_summary_section = ""
    if tool_map:
        docid_to_toolname = {did: tname for tname, did in tool_map.items()}
        summary_lines = []
        for did, mem, cit, short_sum, orig_filename in summary_rows:
            if not short_sum or not short_sum.strip():
                continue
            tool_name = docid_to_toolname.get(str(did))
            if not tool_name:
                continue
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

    # Phase 1 — delegate-level planning (controlled by plan_mode toggle)
    plan_mode_enabled = data.get("plan_mode", True)  # default ON for backward compat
    plan_text = ""

    if plan_mode_enabled:
        planning_messages = list(base_messages)
        planning_messages.append({
            "role": "user",
            "content": (
                "Before answering, create a numbered plan of which documents "
                "you will consult and what information you need from each.\n\n"
                f"Available documents (as tools you can call):\n{tool_descriptions}"
                f"{doc_summary_section}"
                f"{memory_section}\n\n"
                "Output ONLY the plan as a numbered list."
            ),
        })
        plan_resp = await delegate_llm.generate_response(messages=planning_messages)
        if plan_resp.error:
            return f"[Error from {delegate_name} planning: {plan_resp.error}]"
        plan_text = plan_resp.text.strip()
        logger.info(
            f"📋 DELEGATE TOOL EXEC [{delegate_name}]: Plan created ({len(plan_text)} chars)"
        )
        if event_callback:
            event_callback("delegate_plan", {"agent": delegate_name, "content": plan_text})
    else:
        logger.info(f"⚡ DELEGATE TOOL EXEC [{delegate_name}]: Plan mode disabled — skipping planning phase")

    # Phase 2 — tool loop
    title_ref_lines = [
        f"  {tn} → {tt}" for tn, tt in title_map.items() if tt != tn
    ]
    title_ref_section = ""
    if title_ref_lines:
        title_ref_section = (
            "\n\nDocument reference (use titles, not tool names):\n"
            + "\n".join(title_ref_lines)
        )

    tool_conv = list(base_messages)
    _plan_intro = f"Here is your plan:\n{plan_text}\n\n" if plan_text else ""
    tool_conv.append({
        "role": "user",
        "content": (
            f"{_plan_intro}"
            "Use the document tools "
            "to retrieve information. When you have gathered all the "
            "information you need, provide your final answer WITHOUT "
            "calling any more tools.\n\n"
            "IMPORTANT — Citation requirements:\n"
            "- For every key claim, include an inline citation like [1], [2], etc.\n"
            "- Each numbered citation must reference a SPECIFIC PASSAGE, not an entire document.\n"
            "- At the end of your answer, include a \"Sources\" section listing every citation in this format:\n"
            "  [N] \"quoted passage text\" (p.X, Section Name) — Document Title\n"
            + (
                "  For web search sources use: [N] \"quoted passage\" — Page Title — URL: https://example.com/...\n"
                if has_web_tools else ""
            ) +
            "- Copy the quoted text verbatim from the source passages provided in the tool results.\n"
            "- Reference documents by their title (not tool name or filename)."
            f"{title_ref_section}"
        ),
    })

    max_iters = 20
    model_name = delegate_config["llm_model"]

    for iteration in range(max_iters):
        response = await delegate_llm.generate_response(
            messages=tool_conv, tools=tools
        )
        if response.error:
            return f"[Error from {delegate_name} tool-loop iter {iteration}: {response.error}]"

        if not response.tool_calls:
            logger.info(
                f"✅ DELEGATE TOOL EXEC [{delegate_name}]: Synthesis after {iteration} tool iterations"
            )
            result_text = response.text.strip()
            if event_callback:
                event_callback("delegate_done", {"agent": delegate_name, "chars": len(result_text)})
            return result_text

        tool_conv.append(
            ChatManager.format_assistant_tool_call_message(
                response.tool_calls, provider_name, response.text or ""
            )
        )

        pending = response.tool_calls[:10]

        async def _run(tc):
            query = tc["arguments"].get("query", "")

            from .websearch_handler import WebSearchHandler
            if tc["name"].startswith(WebSearchHandler.URL_TOOL_PREFIX):
                if not websearch_handler:
                    return tc, "[Web search handler not available]"
                _target_url = url_tool_map.get(tc["name"], "")
                if not _target_url:
                    return tc, f"[Unknown URL tool: {tc['name']}]"
                _ttl = delegate_node.get('data', {}).get('web_search_cache_ttl', 3600)
                try:
                    result = await websearch_handler._get_url_context([_target_url], _ttl, project_id)
                except Exception as exc:
                    logger.error(f"URL fetch failed in delegate {delegate_name}: {exc}")
                    result = f"[URL fetch error: {exc}]"
                return tc, result

            if tc["name"] == WebSearchHandler.WEB_SEARCH_TOOL_NAME:
                if not websearch_handler:
                    return tc, "[Web search handler not available]"
                try:
                    result = await websearch_handler.execute_websearch_tool(
                        delegate_node, query, project_id
                    )
                except Exception as exc:
                    logger.error(f"Web search failed in delegate {delegate_name}: {exc}")
                    result = f"[Web search error: {exc}]"
                return tc, result

            from .docaware_handler import DocAwareHandler
            if tc["name"] == DocAwareHandler.DOCAWARE_TOOL_NAME:
                if not docaware_handler:
                    return tc, "[Document search not available]"
                try:
                    limit = tc["arguments"].get("limit", 5)
                    result = await docaware_handler.execute_docaware_tool(
                        delegate_node, query, project_id, limit=limit
                    )
                except Exception as exc:
                    logger.error(f"DocAware search failed in delegate {delegate_name}: {exc}")
                    result = f"[Document search error: {exc}]"
                return tc, result

            if tc["name"] == document_tool_service.LIST_FILES_TOOL_NAME:
                try:
                    result = await document_tool_service.execute_list_files_tool(project_id, doc_tool_selected)
                except Exception as exc:
                    logger.error(f"list_project_files failed in delegate {delegate_name}: {exc}")
                    result = f"[Error listing files: {exc}]"
                return tc, result

            if tc["name"] == document_tool_service.COUNT_FILES_TOOL_NAME:
                try:
                    result = await document_tool_service.execute_count_files_tool(project_id, doc_tool_selected)
                except Exception as exc:
                    logger.error(f"count_project_files failed in delegate {delegate_name}: {exc}")
                    result = f"[Error counting files: {exc}]"
                return tc, result

            if tc["name"] == document_tool_service.GET_SUMMARIES_TOOL_NAME:
                try:
                    result = await document_tool_service.execute_get_summaries_tool(project_id, doc_tool_selected)
                except Exception as exc:
                    logger.error(f"get_document_summaries failed in delegate {delegate_name}: {exc}")
                    result = f"[Error retrieving summaries: {exc}]"
                return tc, result

            if tc["name"] == document_tool_service.FIND_RELEVANT_TOOL_NAME:
                try:
                    _limit = tc["arguments"].get("limit", 5)
                    result = await document_tool_service.execute_find_relevant_documents_tool(
                        project_id, query, limit=_limit, selected_filenames=doc_tool_selected
                    )
                except Exception as exc:
                    logger.error(f"find_relevant_documents failed in delegate {delegate_name}: {exc}")
                    result = f"[Error finding relevant documents: {exc}]"
                return tc, result

            if tc["name"] == document_tool_service.GET_METADATA_TOOL_NAME:
                try:
                    _fname = tc["arguments"].get("filename", "")
                    result = await document_tool_service.execute_get_document_metadata_tool(
                        project_id, _fname, selected_filenames=doc_tool_selected
                    )
                except Exception as exc:
                    logger.error(f"get_document_metadata failed in delegate {delegate_name}: {exc}")
                    result = f"[Error retrieving metadata: {exc}]"
                return tc, result

            doc_id = tool_map.get(tc["name"])
            if not doc_id:
                return tc, f"[Unknown tool: {tc['name']}]"
            try:
                result = await document_tool_service.execute_document_tool(
                    project_id=project_id,
                    document_id=doc_id,
                    query=query,
                    provider=provider_name,
                    model=model_name,
                    agent_name=delegate_name,
                )
            except Exception as exc:
                logger.error(f"Tool call {tc['name']} failed in delegate {delegate_name}: {exc}")
                result = f"[Error executing tool {tc['name']}: {exc}]"
            return tc, result

        gather_results = await asyncio.gather(
            *[_run(tc) for tc in pending], return_exceptions=False
        )

        calls_with_results = []
        for tc, result_text in gather_results:
            calls_with_results.append({**tc, "result": result_text})
            if event_callback:
                event_callback("tool_result", {
                    "agent": delegate_name,
                    "tool": tc.get("name", "?"),
                    "chars": len(str(result_text)),
                    "content": str(result_text)[:2000],
                })

        tool_result_msgs = ChatManager.format_tool_results(
            calls_with_results, provider_name
        )
        tool_conv.extend(tool_result_msgs)

    logger.warning(
        f"⚠️ DELEGATE TOOL EXEC [{delegate_name}]: Hit max iterations, forcing synthesis"
    )
    tool_conv.append({
        "role": "user",
        "content": (
            "You have used all available tool iterations. Based on the information "
            "gathered so far, provide your final answer. Include inline citations "
            "[1], [2], etc. where each number references a SPECIFIC PASSAGE, not an entire document. "
            "End with a Sources section in the format: [N] \"quoted passage\" (p.X, Section) — Document Title. "
            "For web search sources use: [N] \"quoted passage\" — Page Title — URL: https://..."
        ),
    })
    final_resp = await delegate_llm.generate_response(messages=tool_conv)
    if final_resp.error:
        return f"[Error from {delegate_name} forced synthesis: {final_resp.error}]"
    result_text = final_resp.text.strip()
    if event_callback:
        event_callback("delegate_done", {"agent": delegate_name, "chars": len(result_text)})
    return result_text


# ── 3. Two-phase tool-based delegation ───────────────────────────────

async def execute_tool_based_delegation(
    chat_manager_node: Dict[str, Any],
    llm_provider,
    delegate_nodes: List[Dict[str, Any]],
    input_context: str,
    project_id: Optional[str],
    project=None,
    llm_provider_manager=None,
    execution_id: Optional[str] = None,
    event_callback=None,
    websearch_handler=None,
    docaware_handler=None,
) -> Dict[str, Any]:
    """
    Two-phase GroupChatManager execution using tool calling.

    Phase 1: The manager LLM receives the user input and produces a plan (no
    tools).

    Phase 2: The manager LLM receives the plan + delegate tools and enters a
    tool loop. Each tool call dispatches to ``run_delegate_doc_tool_loop``
    for the target delegate. Multiple calls in one turn run in parallel.

    Returns the same ``Dict`` shape that ``workflow_executor`` expects:
    ``final_response``, ``delegate_conversations``, ``delegate_status``,
    ``total_iterations``, ``input_count``.
    """
    from .chat_manager import ChatManager
    from .intellidoc_system_prompt import intellidoc_addendum_for_node

    manager_data = chat_manager_node.get("data", {})
    manager_name = manager_data.get("name", "Chat Manager")
    provider_name = manager_data.get("llm_provider", "openai")

    logger.info(
        f"👥 GCM TOOL DELEGATION: Starting for {manager_name} "
        f"with {len(delegate_nodes)} delegates"
    )
    # #region agent log
    logger.info(f"🔬 DEBUG-6451c8 [H5] GCM entry: manager={manager_name}, delegates={len(delegate_nodes)}, provider={provider_name}, has_project={project is not None}, project_id={project_id}")
    # #endregion

    # Build system message for the manager
    system_parts = [
        f"You are {manager_name}, a Group Chat Manager.",
    ]
    sys_msg = manager_data.get("system_message", "")
    if sys_msg:
        system_parts.append(sys_msg)
    instructions = manager_data.get("instructions", "")
    if instructions:
        system_parts.append(f"Instructions: {instructions}")

    addendum = intellidoc_addendum_for_node(chat_manager_node)
    if addendum:
        system_parts.append(addendum)

    system_content = "\n".join(system_parts)

    # ── Phase 1 — Planning (no tools) ────────────────────────────
    delegate_summaries = []
    for dn in delegate_nodes:
        d = dn.get("data", {})
        dname = d.get("name", "Delegate")
        ddesc = d.get("description", d.get("system_message", ""))
        capability_parts = [f"- {dname}: {ddesc[:200]}"]
        if d.get("doc_tool_calling"):
            doc_files = d.get("doc_tool_calling_documents")
            if isinstance(doc_files, list) and doc_files:
                capability_parts.append(
                    f"  [Can query project documents: {', '.join(doc_files[:5])}"
                    + (f" and {len(doc_files)-5} more" if len(doc_files) > 5 else "")
                    + "]"
                )
            else:
                capability_parts.append(
                    "  [Can query all project documents via tool calling]"
                )
        delegate_summaries.append("\n".join(capability_parts))
    delegate_listing = "\n".join(delegate_summaries)

    # Validate delegate tools BEFORE Phase 1 planning — don't tell the LLM
    # about agents that can't actually be called.
    tools, tool_map = build_delegate_tools(delegate_nodes)
    if not tools:
        raise Exception(
            f"GroupChatManager {manager_name} has no delegate tools (no delegates connected)"
        )

    phase1_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": (
                f"{input_context}\n\n"
                "You have the following specialist delegate agents available:\n"
                f"{delegate_listing}\n\n"
                "Create a detailed plan for how to answer the query above. "
                "For each step, indicate which delegate agent should handle it "
                "and what specific task(s) you will assign to that delegate.\n\n"
                "Output ONLY the plan as a numbered list."
            ),
        },
    ]

    # #region agent log
    logger.info(f"🔬 DEBUG-6451c8 [H5] Phase1 messages: count={len(phase1_messages)}, user_preview={phase1_messages[-1]['content'][:200] if phase1_messages else 'EMPTY'}")
    # #endregion
    plan_response = await llm_provider.generate_response(messages=phase1_messages)
    if plan_response.error:
        raise Exception(
            f"GroupChatManager {manager_name} planning error: {plan_response.error}"
        )
    manager_plan = plan_response.text.strip()
    logger.info(
        f"📋 GCM TOOL DELEGATION [{manager_name}]: Plan created ({len(manager_plan)} chars)"
    )
    if event_callback:
        event_callback("planning", {"agent": manager_name, "content": manager_plan})
    # #region agent log
    logger.info(f"🔬 DEBUG-6451c8 [H4] Phase1 done: plan_len={len(manager_plan)}, preview={manager_plan[:200]}")
    # #endregion

    # ── Phase 2 — Tool loop (tools already validated before Phase 1) ──
    tool_names_listing = "\n".join(
        f"- {t['function']['name']}: {t['function']['description'][:150]}"
        for t in tools
    )

    phase2_messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": (
                f"{input_context}\n\n"
                f"Your plan:\n{manager_plan}\n\n"
                "Now execute the plan by calling the delegate tools below to assign "
                "tasks. You may call multiple delegates in a single turn. Each tool "
                "accepts a `tasks` array of task instructions.\n\n"
                f"Available delegate tools:\n{tool_names_listing}\n\n"
                "After receiving all delegate results, provide a comprehensive "
                "final answer that synthesizes their outputs.\n\n"
                "IMPORTANT — Citation requirements:\n"
                "- Preserve ALL inline citations [1], [2], etc. from delegate responses.\n"
                "- Each citation number must reference a SPECIFIC PASSAGE, not an entire document.\n"
                "- Merge all passage-level sources into a unified \"Sources\" section at the end, "
                "renumbering if needed to avoid conflicts between delegates.\n"
                "- Each source must follow this format: [N] \"quoted passage\" (p.X, Section) — Document Title\n"
                "- For web search sources preserve the URL: [N] \"quoted passage\" — Page Title — URL: https://...\n"
                "- Do NOT simplify citations to just document titles — always include the quoted text."
            ),
        },
    ]

    conversation_log: List[str] = []
    delegate_results: Dict[str, List[str]] = {}
    total_tool_calls = 0

    for iteration in range(MAX_DELEGATION_ITERATIONS):
        # #region agent log
        logger.info(f"🔬 DEBUG-6451c8 [H1,H4] Phase2 iter={iteration}, msgs={len(phase2_messages)}, total_calls={total_tool_calls}")
        # #endregion
        response = await llm_provider.generate_response(
            messages=phase2_messages, tools=tools
        )
        if response.error:
            raise Exception(
                f"GroupChatManager {manager_name} tool-loop error "
                f"(iter {iteration}): {response.error}"
            )

        if not response.tool_calls:
            if event_callback:
                event_callback("synthesizing", {"agent": manager_name})
            logger.info(
                f"✅ GCM TOOL DELEGATION [{manager_name}]: Final answer after "
                f"{iteration} tool iterations, {total_tool_calls} total tool calls"
            )
            final_text = response.text.strip()
            break
        else:
            # Record the assistant turn with tool calls
            phase2_messages.append(
                ChatManager.format_assistant_tool_call_message(
                    response.tool_calls, provider_name, response.text or ""
                )
            )

            pending = response.tool_calls[:MAX_DELEGATE_TOOL_CALLS_PER_TURN]
            total_tool_calls += len(pending)

            async def _handle_delegate_call(tc: Dict[str, Any]):
                tool_name = tc["name"]
                delegate_node = tool_map.get(tool_name)
                if not delegate_node:
                    return tc, f"[Unknown delegate tool: {tool_name}]"

                tasks_arg = tc["arguments"].get("tasks", [])
                if isinstance(tasks_arg, str):
                    tasks_arg = [tasks_arg]

                delegate_name = delegate_node.get("data", {}).get("name", tool_name)
                logger.info(
                    f"🤝 GCM TOOL DELEGATION: Dispatching {len(tasks_arg)} task(s) "
                    f"to {delegate_name}"
                )
                if event_callback:
                    event_callback("delegate_start", {"agent": delegate_name, "tasks": tasks_arg})

                try:
                    result = await run_delegate_doc_tool_loop(
                        delegate_node=delegate_node,
                        tasks=tasks_arg,
                        project_id=project_id or "",
                        llm_provider_manager=llm_provider_manager,
                        manager_plan=manager_plan,
                        fallback_llm=llm_provider,
                        project=project,
                        event_callback=event_callback,
                        websearch_handler=websearch_handler,
                        docaware_handler=docaware_handler,
                    )
                except Exception as exc:
                    logger.error(f"Delegate {delegate_name} execution failed: {exc}")
                    result = f"[Delegate {delegate_name} execution error: {exc}]"
                return tc, result

            # #region agent log
            _tc_names = [tc.get("name","?") for tc in pending]; _tc_ids = [tc.get("id","?") for tc in pending]
            logger.info(f"🔬 DEBUG-6451c8 [H1,H3] Before gather: iter={iteration}, pending={len(pending)}, names={_tc_names}, ids={_tc_ids}")
            # #endregion
            gather = await asyncio.gather(
                *[_handle_delegate_call(tc) for tc in pending],
            )

            calls_with_results = []
            for tc, result_text in gather:
                delegate_node = tool_map.get(tc["name"])
                delegate_name = (
                    delegate_node.get("data", {}).get("name", tc["name"])
                    if delegate_node
                    else tc["name"]
                )

                calls_with_results.append({**tc, "result": result_text})

                conversation_log.append(
                    f"{delegate_name}: {result_text[:500]}"
                )
                delegate_results.setdefault(delegate_name, []).append(result_text)

            # #region agent log
            _cwr = [{"name":c.get("name","?"),"id":c.get("id","?"),"result_len":len(str(c.get("result","")))} for c in calls_with_results]
            logger.info(f"🔬 DEBUG-6451c8 [H3] After gather: iter={iteration}, results={_cwr}")
            # #endregion
            tool_result_msgs = ChatManager.format_tool_results(
                calls_with_results, provider_name
            )
            phase2_messages.extend(tool_result_msgs)
    else:
        logger.warning(
            f"⚠️ GCM TOOL DELEGATION [{manager_name}]: Hit max iterations, "
            "forcing final synthesis"
        )
        if event_callback:
            event_callback("synthesizing", {"agent": manager_name})
        phase2_messages.append({
            "role": "user",
            "content": (
                "You have used all available delegation iterations. Based on the "
                "delegate results so far, provide your comprehensive final answer. "
                "Preserve ALL inline citations [1], [2], etc. referencing SPECIFIC PASSAGES. "
                "Include a unified Sources section at the end in the format: "
                "[N] \"quoted passage\" (p.X, Section) — Document Title. "
                "For web sources: [N] \"quoted passage\" — Page Title — URL: https://... "
                "Do NOT simplify to just document titles."
            ),
        })
        synth_resp = await llm_provider.generate_response(messages=phase2_messages)
        if synth_resp.error:
            raise Exception(
                f"GroupChatManager {manager_name} forced synthesis error: "
                f"{synth_resp.error}"
            )
        final_text = synth_resp.text.strip()

    # Extract structured citations from the text-based Sources section
    from agent_orchestration.document_tool_service import _parse_text_citations
    clean_text, gcm_citations = _parse_text_citations(final_text)
    if gcm_citations:
        final_text = clean_text
        logger.info(
            f"📎 GCM TOOL DELEGATION [{manager_name}]: Extracted "
            f"{len(gcm_citations)} structured citations"
        )

    # Build delegate_status in the shape workflow_executor expects
    delegate_status: Dict[str, Dict[str, Any]] = {}
    for dn in delegate_nodes:
        dname = dn.get("data", {}).get("name", "Delegate")
        results_for_delegate = delegate_results.get(dname, [])
        delegate_status[dname] = {
            "iterations": len(results_for_delegate),
            "max_iterations": MAX_DELEGATION_ITERATIONS,
            "completed": True,
            "node": dn,
            "termination_condition": "",
        }

    logger.info(
        f"✅ GCM TOOL DELEGATION [{manager_name}]: Completed with "
        f"{total_tool_calls} tool calls across {len(delegate_results)} delegates"
    )

    _result = {
        "final_response": final_text,
        "citations": gcm_citations,
        "delegate_conversations": conversation_log,
        "delegate_status": delegate_status,
        "total_iterations": total_tool_calls,
        "input_count": 1,
        "manager_plan": manager_plan,
    }
    # #region agent log
    logger.info(f"🔬 DEBUG-6451c8 [H4] GCM complete: final_len={len(final_text)}, conversations={len(conversation_log)}, delegates={list(delegate_status.keys())}, total_calls={total_tool_calls}")
    # #endregion
    return _result
