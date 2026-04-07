"""
Document Tool Service — exposes project documents as LLM-callable tools.

Each uploaded document becomes a tool whose description is the document's
short summary.  When an agent invokes a tool the service sends the full
document (via provider File API) together with the agent's query to the
LLM and returns the extracted answer.  The execution prompt also includes
``long_summary`` (or ``short_summary`` if long is empty) plus prior
``memory`` entries when present.

Memory: every tool-call result is persisted as a memory entry on the
document's ``ProjectDocumentSummary.memory`` JSONField so that future
tool calls can build on prior knowledge.

Citations: the LLM is instructed to provide exact quoted passages with
page/section metadata.  On first use, bibliographic metadata (title,
authors, year, DOI …) is extracted and saved to
``ProjectDocumentSummary.citation``.
"""
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from asgiref.sync import sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)

PROVIDER_FILE_FIELD = {
    "openai": "llm_file_id_openai",
    "anthropic": "llm_file_id_anthropic",
    "google": "llm_file_id_google",
    "gemini": "llm_file_id_google",
    "ollama": None,  # No file API — uses extraction_text directly
}

MAX_TOOL_NAME_LEN = 64
CONDENSATION_THRESHOLD = 15
KEEP_RECENT_ENTRIES = 5
# Cap overview text in execute_document_tool system prompt (long_summary / short fallback).
MAX_DOCUMENT_OVERVIEW_CHARS = 14000

# Tool names for document-info tools (added alongside read_doc_* when doc_tool_calling is enabled)
LIST_FILES_TOOL_NAME        = "list_project_files"
COUNT_FILES_TOOL_NAME       = "count_project_files"
GET_SUMMARIES_TOOL_NAME     = "get_document_summaries"
FIND_RELEVANT_TOOL_NAME     = "find_relevant_documents"
GET_METADATA_TOOL_NAME      = "get_document_metadata"


def _maybe_truncate_document_overview(text: str, max_chars: int = MAX_DOCUMENT_OVERVIEW_CHARS) -> str:
    """Truncate very long summaries so small-model context is not dominated."""
    if len(text) <= max_chars:
        return text
    logger.info(
        "📄 DOC TOOL EXEC: Document overview truncated from %s to %s chars",
        len(text),
        max_chars,
    )
    return (
        text[:max_chars]
        + "\n\n[... Document overview truncated due to length; the full document is attached.]"
    )


# ── helpers ──────────────────────────────────────────────────────────

def _sanitize_tool_name(filename: str) -> str:
    """
    Turn a filename into a valid OpenAI function-tool name:
    ^[a-zA-Z0-9_-]{1,64}$
    """
    name = re.sub(r"[^a-zA-Z0-9_]", "_", filename.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    prefix = "read_doc_"
    max_body = MAX_TOOL_NAME_LEN - len(prefix)
    return f"{prefix}{name[:max_body]}"


def _parse_citations_block(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Extract the ``---CITATIONS---`` JSON block from the LLM response.

    Returns (clean_text, citations_list).  If no block is found the full
    text is returned with an empty list.
    """
    pattern = r"---CITATIONS---\s*(.*?)\s*---END_CITATIONS---"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        # #region agent log
        logger.info(f"🔬 DEBUG-6451c8 [H7] No ---CITATIONS--- block found in response (len={len(text)}), tail={text[-200:] if len(text) > 200 else text}")
        # #endregion
        return text.strip(), []

    raw = match.group(1).strip()
    clean_text = text[: match.start()].strip()
    # Strip trailing "CITATIONS" headings the LLM sometimes emits before the block
    clean_text = re.sub(
        r'[\n\r]+(?:#{1,6}\s*)?(?:\*{1,2})?CITATIONS(?:\*{1,2})?\s*$',
        '',
        clean_text,
        flags=re.IGNORECASE,
    ).strip()
    # #region agent log
    logger.info(f"🔬 DEBUG-6451c8 [H6] Found CITATIONS block, raw_len={len(raw)}, raw_preview={raw[:300]}")
    # #endregion

    try:
        citations = json.loads(raw)
        if isinstance(citations, list):
            # #region agent log
            logger.info(f"🔬 DEBUG-6451c8 [H6] Parsed {len(citations)} citation items, keys={[list(c.keys()) if isinstance(c, dict) else type(c).__name__ for c in citations[:3]]}")
            # #endregion
            normalized: List[Dict[str, Any]] = []
            for item in citations:
                if not isinstance(item, dict):
                    continue
                ref = item.get("ref")
                if ref is not None:
                    try:
                        item = {**item, "ref": int(ref)}
                    except (TypeError, ValueError):
                        pass
                normalized.append(item)
            return clean_text, normalized
    except (json.JSONDecodeError, TypeError) as e:
        # #region agent log
        logger.warning(f"🔬 DEBUG-6451c8 [H6] JSON parse failed: {e}, raw={raw[:200]}")
        # #endregion
        pass

    return clean_text, []


def _append_citations_block(clean_text: str, citations: List[Dict[str, Any]]) -> str:
    """
    Re-attach the ``---CITATIONS---`` JSON block after parsing / enrichment.

    ``_parse_citations_block`` strips this block from the LLM output; deployment
    chat UIs (``parseCitations``) expect it to remain in the stored/streamed
    message content so inline ``[n]`` markers can link to structured entries.
    """
    if not citations:
        return clean_text
    blob = json.dumps(citations, ensure_ascii=False)
    return f"{clean_text.rstrip()}\n\n---CITATIONS---\n{blob}\n---END_CITATIONS---"


def _parse_text_citations(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parse a text-based Sources/References section into structured citation objects.

    Handles the format produced by GCM delegate synthesis prompts:
        [N] "quoted passage" (p.X, Section Name) -- Document Title

    Returns (clean_text_without_sources, citations_list).
    If no Sources section is found, returns the original text with an empty list.
    """
    # Locate the Sources / References heading (plain, bold, or markdown heading)
    section_pattern = re.compile(
        r"(?:^|\n)\s*(?:#{1,4}\s+)?(?:\*\*)?(?:Sources|References)(?:\*\*)?\s*\n",
        re.IGNORECASE,
    )
    section_match = section_pattern.search(text)
    if not section_match:
        return text, []

    body_text = text[: section_match.start()].rstrip()
    sources_block = text[section_match.end():]

    # Find every [N] anchor position — each starts a new citation entry
    anchor_pattern = re.compile(r"\[(\d+)\]\s*")
    anchors = list(anchor_pattern.finditer(sources_block))
    if not anchors:
        logger.info("📎 TEXT CITATIONS: Sources section found but no [N] anchors")
        return body_text, []

    # Quote pattern applied to the text between consecutive anchors
    # Handles straight quotes and common unicode curly quotes
    entry_pattern = re.compile(
        r'["\u201c](.*?)["\u201d]\s*'      # "quoted text" (straight or curly)
        r'(?:\(([^)]+)\)\s*)?'              # optional (p.X, Section)
        r'(?:[—–\-]+\s*(.+))?',            # optional -- Document Title
        re.DOTALL,
    )

    citations: List[Dict[str, Any]] = []
    for idx, anchor in enumerate(anchors):
        ref = int(anchor.group(1))
        start = anchor.end()
        end = anchors[idx + 1].start() if idx + 1 < len(anchors) else len(sources_block)
        entry_text = sources_block[start:end].strip()

        m = entry_pattern.match(entry_text)
        if not m:
            continue

        quoted_text = re.sub(r"\s+", " ", m.group(1)).strip()
        location_str = (m.group(2) or "").strip()
        document_title = re.sub(r"\s+", " ", (m.group(3) or "")).strip()

        page = None
        section = None
        if location_str:
            loc_parts = [p.strip() for p in location_str.split(",", 1)]
            for part in loc_parts:
                if part.lower().startswith("p."):
                    try:
                        page = int(part[2:].strip())
                    except ValueError:
                        page = part[2:].strip()
                else:
                    section = part

        url = None
        if document_title:
            url_match = re.search(r'URL:\s*(https?://\S+)', document_title)
            if url_match:
                url = url_match.group(1).rstrip('.,;')
                document_title = document_title[:url_match.start()].rstrip(' —–-').strip()

        cit: Dict[str, Any] = {"ref": ref, "quoted_text": quoted_text}
        if document_title:
            cit["document_title"] = document_title
        if page is not None:
            cit["page"] = page
        if section:
            cit["section"] = section
        if url:
            cit["url"] = url
            cit["source"] = "web"
        citations.append(cit)

    if citations:
        logger.info(
            f"📎 TEXT CITATIONS: Parsed {len(citations)} passage-level citations "
            f"from Sources section"
        )
    else:
        logger.info(
            "📎 TEXT CITATIONS: Sources section found but no citations matched "
            "the expected format"
        )

    return body_text, citations


def _format_memory_for_prompt(memory: List[Dict[str, Any]], max_entries: int = 10) -> str:
    """Format existing memory entries into a prompt section."""
    if not memory:
        return ""

    recent = memory[-max_entries:]
    lines = []
    for entry in recent:
        entry_type = entry.get("type", "insight")
        if entry_type == "condensed":
            lines.append(f"- [Condensed prior knowledge] {entry.get('insight', '')[:500]}")
        else:
            lines.append(f"- Q: {entry.get('query', '?')} → {entry.get('insight', '')[:300]}")
    return "\n".join(lines)


# ── build_document_tools ─────────────────────────────────────────────

async def build_document_tools(
    project_id: str,
    selected_filenames: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, str]]:
    """
    Build OpenAI-format tool schemas for project documents.

    Parameters
    ----------
    project_id : str
        UUID of the project.
    selected_filenames : list[str] | None
        When a non-empty list, only documents whose ``original_filename``
        is in this list are included.  When an empty list (``[]``), no
        tools are built and a warning is logged.  When ``None`` (default /
        legacy nodes), all processed documents are included.

    Returns
    -------
    tools : list[dict]
        Tool definitions ready for the ``tools`` parameter of an LLM call.
    tool_map : dict[str, str]
        Mapping  tool_name  →  document_id (UUID string).
    title_map : dict[str, str]
        Mapping  tool_name  →  document title (from citation metadata,
        falls back to original filename).
    """
    from users.models import IntelliDocProject, ProjectDocument, ProjectDocumentSummary

    if isinstance(selected_filenames, list) and len(selected_filenames) == 0:
        logger.warning(
            f"⚠️ DOC TOOLS: No documents selected for project {project_id}; "
            "returning zero tools"
        )
        return [], {}, {}

    project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)

    qs = ProjectDocument.objects.filter(
        project=project,
        upload_status__in=("completed", "ready"),
    )
    if isinstance(selected_filenames, list) and selected_filenames:
        qs = qs.filter(original_filename__in=selected_filenames)

    docs = await sync_to_async(list)(qs.order_by("original_filename"))

    doc_ids = [d.document_id for d in docs]

    # Fetch summaries + memory counts in bulk
    summary_rows = await sync_to_async(list)(
        ProjectDocumentSummary.objects.filter(
            document__document_id__in=doc_ids,
        ).values_list("document__document_id", "short_summary", "memory", "citation")
    )
    summary_map: Dict[str, str] = {}
    memory_map: Dict[str, List] = {}
    citation_map: Dict[str, Dict] = {}
    for did, short, mem, cit in summary_rows:
        key = str(did)
        summary_map[key] = short or ""
        memory_map[key] = mem if isinstance(mem, list) else []
        citation_map[key] = cit if isinstance(cit, dict) else {}

    tools: List[Dict[str, Any]] = []
    tool_map: Dict[str, str] = {}
    title_map: Dict[str, str] = {}
    seen_names: set = set()

    for doc in docs:
        raw_name = _sanitize_tool_name(doc.original_filename)
        unique_name = raw_name
        counter = 2
        while unique_name in seen_names:
            suffix = f"_{counter}"
            unique_name = raw_name[: MAX_TOOL_NAME_LEN - len(suffix)] + suffix
            counter += 1
        seen_names.add(unique_name)

        doc_key = str(doc.document_id)
        description = summary_map.get(doc_key, "")
        if not description:
            description = f"Read and analyze the document: {doc.original_filename}"

        # Append document title from citation if available
        cit = citation_map.get(doc_key, {})
        if cit.get("title"):
            description = f"[{cit['title']}] {description}"

        # Append memory hint if the document has prior knowledge
        mem = memory_map.get(doc_key, [])
        if mem:
            topics = set()
            for entry in mem[-5:]:
                q = entry.get("query", "")
                if q:
                    topics.add(q[:40])
            if topics:
                hint = f" | Prior knowledge ({len(mem)} insights): {'; '.join(list(topics)[:3])}"
                description += hint

        tools.append({
            "type": "function",
            "function": {
                "name": unique_name,
                "description": description[:1024],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "The specific question or information to "
                                "extract from this document"
                            ),
                        }
                    },
                    "required": ["query"],
                },
            },
        })
        tool_map[unique_name] = doc_key
        title_map[unique_name] = cit.get("title") or doc.original_filename

    logger.info(
        f"🔧 DOC TOOLS: Built {len(tools)} document tools for project {project_id}"
    )
    return tools, tool_map, title_map


# ── build_document_info_tools ─────────────────────────────────────────

def build_document_info_tools() -> List[Dict[str, Any]]:
    """
    Returns the three document-info tool schemas added alongside ``read_doc_*``
    tools whenever ``doc_tool_calling`` is enabled on a node.

    These tools give agents the ability to introspect the document set before
    deciding which documents to query in detail.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": LIST_FILES_TOOL_NAME,
                "description": (
                    "List all files available to you in this project. "
                    "Returns the filename and document title (if known) for each file."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": COUNT_FILES_TOOL_NAME,
                "description": (
                    "Return the total number of files available to you in this project."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": GET_SUMMARIES_TOOL_NAME,
                "description": (
                    "Return a high-level summary of every file available to you in this "
                    "project. Each summary is a broad overview of that document's content "
                    "and purpose — not a verbatim excerpt. Use this to understand what each "
                    "document is about before deciding which to query in detail."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": FIND_RELEVANT_TOOL_NAME,
                "description": (
                    "Search across all project documents and return the ones most relevant "
                    "to a query, ranked by relevance. Use this to identify which documents "
                    "to read in detail before calling their individual read_doc_* tools."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The topic or question to find relevant documents for",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of documents to return (default: 5, max: 10)",
                            "minimum": 1,
                            "maximum": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": GET_METADATA_TOOL_NAME,
                "description": (
                    "Return structured metadata for a specific file: size, type, upload date, "
                    "processing status, and whether a summary is available."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The exact filename as returned by list_project_files",
                        },
                    },
                    "required": ["filename"],
                },
            },
        },
    ]


# ── execute_list_files_tool ───────────────────────────────────────────

async def execute_list_files_tool(
    project_id: str,
    selected_filenames: Optional[List[str]] = None,
) -> str:
    """
    Return a numbered list of filenames (and citation titles where available)
    that the agent can access.
    """
    from users.models import IntelliDocProject, ProjectDocument

    try:
        project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
        qs = ProjectDocument.objects.filter(
            project=project,
            upload_status__in=("completed", "ready"),
        )
        if isinstance(selected_filenames, list) and selected_filenames:
            qs = qs.filter(original_filename__in=selected_filenames)
        docs = await sync_to_async(list)(
            qs.select_related("document_summary").order_by("original_filename")
        )
    except Exception as e:
        logger.error(f"list_project_files error: {e}")
        return "[Error retrieving file list]"

    if not docs:
        return "No files are currently available in this project."

    lines = []
    for i, doc in enumerate(docs, start=1):
        title = ""
        try:
            summary = doc.document_summary
            citation = summary.citation if summary else {}
            title = (citation or {}).get("title", "")
        except Exception:
            pass
        if title:
            lines.append(f"{i}. {doc.original_filename} ({title})")
        else:
            lines.append(f"{i}. {doc.original_filename}")

    return "\n".join(lines)


# ── execute_count_files_tool ──────────────────────────────────────────

async def execute_count_files_tool(
    project_id: str,
    selected_filenames: Optional[List[str]] = None,
) -> str:
    """Return the count of accessible project files as a plain string."""
    from users.models import IntelliDocProject, ProjectDocument

    try:
        project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
        qs = ProjectDocument.objects.filter(
            project=project,
            upload_status__in=("completed", "ready"),
        )
        if isinstance(selected_filenames, list) and selected_filenames:
            qs = qs.filter(original_filename__in=selected_filenames)
        count = await sync_to_async(qs.count)()
    except Exception as e:
        logger.error(f"count_project_files error: {e}")
        return "[Error counting files]"

    return str(count)


# ── execute_get_summaries_tool ────────────────────────────────────────

async def execute_get_summaries_tool(
    project_id: str,
    selected_filenames: Optional[List[str]] = None,
) -> str:
    """
    Return the high-level (long) summary for every accessible project file.
    Falls back to ``short_summary`` when ``long_summary`` is absent.
    """
    from users.models import IntelliDocProject, ProjectDocument

    try:
        project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
        qs = ProjectDocument.objects.filter(
            project=project,
            upload_status__in=("completed", "ready"),
        )
        if isinstance(selected_filenames, list) and selected_filenames:
            qs = qs.filter(original_filename__in=selected_filenames)
        docs = await sync_to_async(list)(
            qs.select_related("document_summary").order_by("original_filename")
        )
    except Exception as e:
        logger.error(f"get_document_summaries error: {e}")
        return "[Error retrieving document summaries]"

    if not docs:
        return "No files are currently available in this project."

    blocks = []
    for doc in docs:
        title_line = ""
        summary_text = "No summary available."
        try:
            summary = doc.document_summary
            if summary:
                summary_text = (
                    (summary.long_summary or summary.short_summary or "").strip()
                    or "No summary available."
                )
                citation = summary.citation or {}
                ct = citation.get("title", "")
                if ct:
                    title_line = f"Title: {ct}\n"
        except Exception:
            pass
        blocks.append(f"--- {doc.original_filename} ---\n{title_line}{summary_text}")

    return "\n\n".join(blocks)


# ── execute_find_relevant_documents_tool ─────────────────────────────

async def execute_find_relevant_documents_tool(
    project_id: str,
    query: str,
    limit: int = 5,
    selected_filenames: Optional[List[str]] = None,
) -> str:
    """
    Run a semantic search and return the top-N documents ranked by relevance.

    Performs a hybrid search against the project's Milvus collection, groups
    chunk-level hits by document, and returns a ranked list with a qualitative
    relevance label (high / medium / low) and matching-passage count.
    """
    from .docaware import EnhancedDocAwareAgentService, SearchMethod

    limit = max(1, min(limit, 10))
    chunk_limit = max(limit * 6, 30)  # fetch more chunks to get good document coverage

    try:
        service = EnhancedDocAwareAgentService(project_id)
        results = await sync_to_async(service.search_documents)(
            query,
            search_method=SearchMethod.HYBRID_SEARCH,
            method_parameters={"search_limit": chunk_limit},
        )
    except Exception as e:
        logger.error(f"find_relevant_documents error: {e}")
        return "[Error searching documents — ensure the project has been processed]"

    if not results:
        return "No relevant documents found for this query."

    # Group chunk-level hits by document source name
    from collections import defaultdict
    doc_scores: Dict[str, List[float]] = defaultdict(list)
    doc_passages: Dict[str, int] = defaultdict(int)

    for hit in results:
        meta = hit.get("metadata", {})
        source = (
            meta.get("source")
            or meta.get("filename")
            or meta.get("file_name")
            or hit.get("source")
            or "Unknown"
        )
        score = float(meta.get("score", 0.0))
        doc_scores[source].append(score)
        doc_passages[source] += 1

    # Apply selected_filenames scope if set
    if isinstance(selected_filenames, list) and selected_filenames:
        doc_scores = {k: v for k, v in doc_scores.items() if k in selected_filenames}
        doc_passages = {k: v for k, v in doc_passages.items() if k in selected_filenames}

    if not doc_scores:
        return "No relevant documents found for this query."

    # Rank by best (max) chunk score per document
    ranked = sorted(doc_scores.items(), key=lambda x: max(x[1]), reverse=True)[:limit]

    lines = []
    for i, (source, scores) in enumerate(ranked, start=1):
        best = max(scores)
        if best >= 0.7:
            label = "high"
        elif best >= 0.4:
            label = "medium"
        else:
            label = "low"
        n = doc_passages[source]
        lines.append(
            f"{i}. {source} (relevance: {label}) — {n} matching passage{'s' if n != 1 else ''}"
        )

    return "\n".join(lines)


# ── execute_get_document_metadata_tool ───────────────────────────────

async def execute_get_document_metadata_tool(
    project_id: str,
    filename: str,
    selected_filenames: Optional[List[str]] = None,
) -> str:
    """
    Return structured metadata for a specific project document.
    """
    from users.models import IntelliDocProject, ProjectDocument

    # Enforce scope if agent has a restricted document set
    if isinstance(selected_filenames, list) and selected_filenames:
        if filename not in selected_filenames:
            return f"[Access denied: '{filename}' is not in your accessible document set]"

    try:
        project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
        doc = await sync_to_async(
            ProjectDocument.objects.select_related("document_summary").get
        )(project=project, original_filename=filename, upload_status__in=("completed", "ready"))
    except Exception as lookup_err:
        if "DoesNotExist" in type(lookup_err).__name__ or "matching query" in str(lookup_err):
            return f"File not found: '{filename}'"
        logger.error(f"get_document_metadata error: {lookup_err}")
        return "[Error retrieving document metadata]"

    uploaded = doc.uploaded_at.strftime("%Y-%m-%d %H:%M") if doc.uploaded_at else "unknown"
    processed = doc.processed_at.strftime("%Y-%m-%d %H:%M") if doc.processed_at else "not processed"

    lines = [
        f"filename:  {doc.original_filename}",
        f"type:      {doc.file_type or doc.file_extension or 'unknown'}",
        f"size:      {doc.file_size_formatted}",
        f"uploaded:  {uploaded}",
        f"processed: {processed}",
        f"status:    {doc.upload_status}",
    ]

    # Summary availability
    summary_info = "none"
    try:
        summary = doc.document_summary
        if summary:
            if summary.long_summary:
                summary_info = "full summary available"
            elif summary.short_summary:
                summary_info = "short summary available"
            else:
                summary_info = "summary record exists (empty)"
    except Exception:
        pass
    lines.append(f"summary:   {summary_info}")

    return "\n".join(lines)


# ── execute_document_tool ────────────────────────────────────────────

async def execute_document_tool(
    project_id: str,
    document_id: str,
    query: str,
    provider: str,
    model: str,
    agent_name: str = "agent",
    project_api_key: Optional[str] = None,
) -> str:
    """
    Execute a document tool call: send the full document + query to the
    LLM via the provider's File API and return the answer text.

    The system prompt includes (when available): ``long_summary`` with
    ``short_summary`` as fallback, then prior ``memory`` entries, then
    citation instructions.

    Side effects:
    - Appends a memory entry to ``ProjectDocumentSummary.memory``.
    - On first call, extracts bibliographic citation metadata.
    - Triggers memory condensation when entries exceed threshold.
    """
    from users.models import IntelliDocProject, ProjectDocument, ProjectDocumentSummary
    from .chat_manager import ChatManager
    from .llm_file_service import LLMFileUploadService

    start = time.time()

    project = await sync_to_async(IntelliDocProject.objects.get)(project_id=project_id)
    doc = await sync_to_async(
        ProjectDocument.objects.get
    )(document_id=document_id, project=project)

    # ── Ollama path: inject extraction_text directly (no File API) ──
    if provider == 'ollama':
        doc_text = await sync_to_async(lambda: doc.extraction_text)()
        if not doc_text:
            return f"Error: No extracted text available for {doc.original_filename}. Please process documents first."

        # Truncate for context window
        max_chars = 24000
        if len(doc_text) > max_chars:
            doc_text = doc_text[:max_chars] + "\n\n[Document truncated for context window]"

        # Fetch existing memory
        doc_summary = await sync_to_async(
            lambda: ProjectDocumentSummary.objects.filter(document=doc).first()
        )()
        existing_memory: List[Dict[str, Any]] = []
        if doc_summary and isinstance(doc_summary.memory, list):
            existing_memory = doc_summary.memory

        memory_context = _format_memory_for_prompt(existing_memory)

        overview_text = ""
        if doc_summary:
            overview_text = (doc_summary.long_summary or "").strip() or (
                doc_summary.short_summary or ""
            ).strip()
        if overview_text:
            overview_text = _maybe_truncate_document_overview(overview_text)

        # Build system prompt
        system_parts = [
            "You are a document analysis assistant. Extract the requested "
            "information from the provided document text. Be precise and thorough."
        ]

        if overview_text:
            system_parts.append(
                "\nDOCUMENT OVERVIEW (from prior analysis):\n"
                f"{overview_text}\n"
                "Use this overview to focus your answer; always ground claims in the "
                "document text."
            )

        if memory_context:
            system_parts.append(
                "\nPRIOR KNOWLEDGE ABOUT THIS DOCUMENT:\n"
                f"{memory_context}\n"
                "Build on this existing knowledge. Focus on NEW information "
                "and do not repeat what is already known unless directly asked."
            )

        system_parts.append(
            "\nCITATION REQUIREMENTS:\n"
            "For every key fact you extract, cite the exact text from the document.\n"
            "At the END of your response, include a citations block in this exact format:\n"
            "---CITATIONS---\n"
            '[{"quoted_text": "exact text from document", "page": null, "section": "section heading or null"}]\n'
            "---END_CITATIONS---\n"
            "The quoted_text MUST be copied verbatim from the document. "
            "Include page numbers and section headings when identifiable."
        )

        system_prompt = "\n".join(system_parts)

        # Build messages with inline text (no file refs)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"DOCUMENT CONTENT ({doc.original_filename}):\n\n{doc_text}\n\n---\n\nQUERY: {query}"},
        ]

        llm_provider_instance = await _get_llm_provider(provider, model, project, project_api_key)
        response = await llm_provider_instance.generate_response(messages=messages)

        elapsed = int((time.time() - start) * 1000)
        if getattr(response, 'error', None):
            return f"[Error reading document: {response.error}]"

        clean_text, citations = _parse_citations_block(response.text or '')

        # Save memory entry
        memory_entry = {
            "query": query[:500],
            "insight": clean_text[:2000],
            "source_passages": citations[:10],
            "timestamp": timezone.now().isoformat(),
            "agent_name": agent_name,
        }

        if doc_summary:
            current_memory = doc_summary.memory if isinstance(doc_summary.memory, list) else []
            current_memory.append(memory_entry)
            doc_summary.memory = current_memory

            _doc_filename = doc.original_filename
            _mem_count = len(current_memory)
            _needs_condensation = _mem_count > CONDENSATION_THRESHOLD
            _needs_citation = not doc_summary.citation

            async def _background_persist_ollama():
                try:
                    await sync_to_async(doc_summary.save)(update_fields=["memory", "updated_at"])
                    logger.info(
                        f"🧠 DOC MEMORY: Saved entry #{_mem_count} for "
                        f"{_doc_filename} ({len(citations)} citations)"
                    )
                    if _needs_condensation:
                        await condense_document_memory(doc_summary, provider, model, project, project_api_key)
                except Exception as bg_err:
                    logger.warning(f"⚠️ DOC MEMORY: Background persist failed for {_doc_filename}: {bg_err}")

            import asyncio
            asyncio.create_task(_background_persist_ollama())

        logger.info(
            f"✅ DOC TOOL EXEC [Ollama]: {doc.original_filename} answered in {elapsed}ms "
            f"({len(clean_text)} chars, {len(citations)} citations)"
        )

        # Append citation footer
        result_text = clean_text or response.text or ''
        if citations:
            footer_lines = []
            for i, c in enumerate(citations[:10], start=1):
                qt = c.get("quoted_text", "")[:250]
                parts = []
                if c.get("page"):
                    parts.append(f"p.{c['page']}")
                if c.get("section"):
                    parts.append(c["section"])
                loc = f" ({', '.join(parts)})" if parts else ""
                footer_lines.append(f'[{i}] "{qt}"{loc}')
            result_text += (
                f"\n\nSource passages from {doc.original_filename}:\n"
                + "\n".join(footer_lines)
            )

        return result_text

    # ── Cloud provider path: use File API ────────────────────────
    # Resolve file_id for the provider; lazy-upload if missing.
    field = PROVIDER_FILE_FIELD.get(provider, "llm_file_id_openai")
    file_id = getattr(doc, field, None)

    if not file_id:
        logger.info(
            f"🔧 DOC TOOL EXEC: Lazy-uploading {doc.original_filename} to {provider}"
        )
        service = LLMFileUploadService(project)
        result = await service._upload_to_provider(doc, provider)
        file_id = result.get("file_id")
        if not file_id:
            return f"[Error: could not upload document to {provider}: {result.get('error', 'unknown')}]"
        await sync_to_async(doc.refresh_from_db)()
        file_id = getattr(doc, field, None) or file_id

    # ── Fetch existing memory ────────────────────────────────────
    doc_summary = await sync_to_async(
        lambda: ProjectDocumentSummary.objects.filter(document=doc).first()
    )()
    existing_memory: List[Dict[str, Any]] = []
    if doc_summary and isinstance(doc_summary.memory, list):
        existing_memory = doc_summary.memory

    memory_context = _format_memory_for_prompt(existing_memory)

    overview_text = ""
    if doc_summary:
        overview_text = (doc_summary.long_summary or "").strip() or (
            doc_summary.short_summary or ""
        ).strip()
    if overview_text:
        overview_text = _maybe_truncate_document_overview(overview_text)

    # ── Build system prompt: overview → memory → citation instructions ──
    system_parts = [
        "You are a document analysis assistant. Extract the requested "
        "information from the attached document. Be precise and thorough."
    ]

    if overview_text:
        system_parts.append(
            "\nDOCUMENT OVERVIEW (from prior analysis):\n"
            f"{overview_text}\n"
            "Use this overview to focus your answer; always ground claims in the "
            "attached document."
        )

    if memory_context:
        system_parts.append(
            "\nPRIOR KNOWLEDGE ABOUT THIS DOCUMENT:\n"
            f"{memory_context}\n"
            "Build on this existing knowledge. Focus on NEW information "
            "and do not repeat what is already known unless directly asked."
        )

    system_parts.append(
        "\nCITATION REQUIREMENTS:\n"
        "For every key fact you extract, cite the exact text from the document.\n"
        "At the END of your response, include a citations block in this exact format:\n"
        "---CITATIONS---\n"
        '[{"quoted_text": "exact text from document", "page": null, "section": "section heading or null"}]\n'
        "---END_CITATIONS---\n"
        "The quoted_text MUST be copied verbatim from the document. "
        "Include page numbers and section headings when identifiable."
    )

    messages = [
        {"role": "system", "content": "\n".join(system_parts)},
        {"role": "user", "content": query},
    ]

    file_ref = {
        "file_id": file_id,
        "filename": doc.original_filename,
        "document_id": str(doc.document_id),
        "provider": provider,
        "file_type": doc.file_type or "application/pdf",
        "file_size": doc.file_size or 0,
    }
    messages = ChatManager.format_messages_with_file_refs(messages, [file_ref], provider)

    # ── Call the LLM ─────────────────────────────────────────────
    llm_provider = await _get_llm_provider(provider, model, project, project_api_key)
    response = await llm_provider.generate_response(messages=messages)

    elapsed = int((time.time() - start) * 1000)
    if response.error:
        logger.warning(
            f"⚠️ DOC TOOL EXEC: Error analysing {doc.original_filename}: {response.error}"
        )
        return f"[Error reading document: {response.error}]"

    # ── Parse citations from response ────────────────────────────
    clean_text, citations = _parse_citations_block(response.text)

    # ── Save memory entry ────────────────────────────────────────
    memory_entry = {
        "query": query[:500],
        "insight": clean_text[:2000],
        "source_passages": citations[:10],
        "timestamp": timezone.now().isoformat(),
        "agent_name": agent_name,
    }

    if doc_summary:
        current_memory = doc_summary.memory if isinstance(doc_summary.memory, list) else []
        current_memory.append(memory_entry)
        doc_summary.memory = current_memory

        # Background DB writes — not needed for the current response.
        # The in-memory object is already updated; persist asynchronously.
        _doc_filename = doc.original_filename
        _mem_count = len(current_memory)
        _needs_condensation = _mem_count > CONDENSATION_THRESHOLD
        _needs_citation = not doc_summary.citation

        async def _background_persist():
            try:
                await sync_to_async(doc_summary.save)(update_fields=["memory", "updated_at"])
                logger.info(
                    f"🧠 DOC MEMORY: Saved entry #{_mem_count} for "
                    f"{_doc_filename} ({len(citations)} citations)"
                )
                if _needs_condensation:
                    await condense_document_memory(doc_summary, provider, model, project, project_api_key)
                if _needs_citation:
                    await extract_document_citation(
                        doc, doc_summary, file_id, provider, model, project, project_api_key
                    )
            except Exception as bg_err:
                logger.warning(f"⚠️ DOC MEMORY: Background persist failed for {_doc_filename}: {bg_err}")

        import asyncio
        asyncio.create_task(_background_persist())

    logger.info(
        f"✅ DOC TOOL EXEC: {doc.original_filename} answered in {elapsed}ms "
        f"({len(clean_text)} chars, {len(citations)} citations)"
    )

    # Append citation footer so the synthesis LLM sees source passages
    if citations:
        footer_lines = []
        for i, c in enumerate(citations[:10], start=1):
            qt = c.get("quoted_text", "")[:250]
            parts = []
            if c.get("page"):
                parts.append(f"p.{c['page']}")
            if c.get("section"):
                parts.append(c["section"])
            loc = f" ({', '.join(parts)})" if parts else ""
            footer_lines.append(f'[{i}] "{qt}"{loc}')
        return (
            clean_text
            + f"\n\nSource passages from {doc.original_filename}:\n"
            + "\n".join(footer_lines)
        )

    return clean_text


# ── extract_document_citation ────────────────────────────────────────

async def extract_document_citation(
    doc,
    doc_summary,
    file_id: str,
    provider: str,
    model: str,
    project: Any,
    project_api_key: Optional[str] = None,
) -> None:
    """
    Extract bibliographic metadata from the document and save to
    ``ProjectDocumentSummary.citation``.
    """
    from .chat_manager import ChatManager

    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a metadata extraction assistant. Extract bibliographic "
                    "citation metadata from the attached document."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Extract the following metadata from this document and return "
                    "ONLY valid JSON (no markdown, no explanation):\n"
                    "{\n"
                    '  "title": "full document title",\n'
                    '  "authors": ["author1", "author2"],\n'
                    '  "year": 2024,\n'
                    '  "source": "journal/conference/arXiv/book/report",\n'
                    '  "doi": "DOI if available or null",\n'
                    '  "url": "URL if available or null",\n'
                    '  "abstract": "first 200 words of abstract or null"\n'
                    "}\n"
                    "If a field cannot be determined, use null."
                ),
            },
        ]

        file_ref = {
            "file_id": file_id,
            "filename": doc.original_filename,
            "document_id": str(doc.document_id),
            "provider": provider,
            "file_type": doc.file_type or "application/pdf",
            "file_size": doc.file_size or 0,
        }
        messages = ChatManager.format_messages_with_file_refs(messages, [file_ref], provider)

        llm_provider = await _get_llm_provider(provider, model, project, project_api_key)
        response = await llm_provider.generate_response(messages=messages)

        if response.error:
            logger.warning(f"⚠️ CITATION EXTRACT: Error for {doc.original_filename}: {response.error}")
            return

        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        citation_data = json.loads(raw)
        if isinstance(citation_data, dict):
            citation_data["extracted_at"] = timezone.now().isoformat()
            doc_summary.citation = citation_data
            await sync_to_async(doc_summary.save)(update_fields=["citation", "updated_at"])
            logger.info(
                f"📚 CITATION: Extracted metadata for {doc.original_filename}: "
                f"title={citation_data.get('title', '?')[:60]}"
            )

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"⚠️ CITATION EXTRACT: Failed to parse for {doc.original_filename}: {e}")


# ── condense_document_memory ─────────────────────────────────────────

async def condense_document_memory(
    doc_summary,
    provider: str,
    model: str,
    project: Any,
    project_api_key: Optional[str] = None,
) -> None:
    """
    Condense old memory entries when the list exceeds the threshold.

    Keeps the most recent ``KEEP_RECENT_ENTRIES`` intact and summarises
    the older ones into a single condensed entry.
    """
    memory = doc_summary.memory
    if not isinstance(memory, list) or len(memory) <= CONDENSATION_THRESHOLD:
        return

    old_entries = memory[:-KEEP_RECENT_ENTRIES]
    recent_entries = memory[-KEEP_RECENT_ENTRIES:]

    # Build condensation prompt
    entries_text = "\n\n".join(
        f"Query: {e.get('query', '?')}\n"
        f"Insight: {e.get('insight', '')[:500]}\n"
        f"Citations: {json.dumps(e.get('source_passages', [])[:3])}"
        for e in old_entries
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a research notebook assistant. Condense the following "
                "research notes into a single comprehensive summary. "
                "Preserve ALL key facts, findings, and citations. "
                "Do not lose any important information."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Condense these {len(old_entries)} research notes into one "
                f"compact summary:\n\n{entries_text}\n\n"
                "Return ONLY the condensed summary text."
            ),
        },
    ]

    try:
        llm_provider = await _get_llm_provider(provider, model, project, project_api_key)
        response = await llm_provider.generate_response(messages=messages)

        if response.error:
            logger.warning(f"⚠️ MEMORY CONDENSE: Error: {response.error}")
            return

        # Collect all citations from old entries
        all_citations = []
        for e in old_entries:
            all_citations.extend(e.get("source_passages", [])[:3])

        condensed_entry = {
            "type": "condensed",
            "query": f"Condensed from {len(old_entries)} prior entries",
            "insight": response.text.strip()[:3000],
            "source_passages": all_citations[:20],
            "timestamp": timezone.now().isoformat(),
            "agent_name": "system",
            "condensed_count": len(old_entries),
        }

        doc_summary.memory = [condensed_entry] + recent_entries
        await sync_to_async(doc_summary.save)(update_fields=["memory", "updated_at"])

        logger.info(
            f"🗜️ MEMORY CONDENSE: Reduced {len(old_entries) + len(recent_entries)} entries → "
            f"{1 + len(recent_entries)} for {doc_summary.document.original_filename}"
        )

    except Exception as e:
        logger.warning(f"⚠️ MEMORY CONDENSE: Failed: {e}")


# ── _get_llm_provider ───────────────────────────────────────────────

async def _get_llm_provider(
    provider: str, model: str, project: Any, api_key: Optional[str] = None
):
    """Instantiate an LLM provider with the project's API key."""
    from project_api_keys.services import ProjectAPIKeyService

    if not api_key:
        key_service = ProjectAPIKeyService()
        api_key = await sync_to_async(key_service.get_project_api_key)(
            project, provider
        )

    if not api_key:
        raise ValueError(f"No API key configured for provider {provider}")

    if provider == "openai":
        from llm_eval.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key, model=model, max_tokens=4096, timeout=120)
    elif provider == "anthropic":
        from llm_eval.providers.claude_provider import ClaudeProvider
        return ClaudeProvider(api_key=api_key, model=model, max_tokens=4096, timeout=120)
    elif provider in ("google", "gemini"):
        from llm_eval.providers.gemini_provider import GeminiProvider
        return GeminiProvider(api_key=api_key, model=model, max_tokens=4096, timeout=120)
    elif provider == "ollama":
        from llm_eval.providers.ollama_provider import OllamaProvider
        return OllamaProvider(api_key='local', model=model, max_tokens=4096, timeout=900)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
