"""
IntelliDoc platform system prompt addendum (hybrid: global core + per node type).

Appended after the user's system_message / instructions in ChatManager; not exposed
or editable in the workflow UI. Edit this module to change platform-wide behavior.

The addendum is context-aware: citation instructions are only included when the
agent actually has sources to cite (documents, web search, or file attachments).
"""
from __future__ import annotations

from typing import Any, Dict, Set

# Visible delimiter so logs/debugging can spot the injection (not shown to end users in UI)
SECTION_HEADER = "\n\n=== IntelliDoc platform guidance ===\n"

# Always included for every agent type.
INTELLIDOC_CORE = """You are operating inside AICC IntelliDoc. Obey the user and node instructions above first.
- Prioritize accuracy over completeness; if context is insufficient, say so clearly.
- Do not invent quotes, page numbers, section labels, or citations that are not supported by supplied content."""

# Appended only when the agent will receive at least one source (docs, web, files).
INTELLIDOC_SOURCES_ADDENDUM = (
    "- When project documents, tool results, or retrieved context are provided, "
    "ground factual claims in them.\n"
    "- CITATION RENDERING: Bracket references like [1] are rendered as interactive "
    "citation chips in the UI — clicking them shows a tooltip with the source title "
    "and a quoted passage. Reserve [N] notation EXCLUSIVELY for entries in the "
    "---CITATIONS--- block. Do NOT use [N] for step numbers, field IDs, option "
    "lists, or any other enumeration — use plain text or alternative notation "
    '(e.g. "(field 18)" or "option 3") instead.'
)

# Full citation format — only for AssistantAgent when sources are available.
CITATION_FORMAT_BLOCK = (
    "CITATION FORMAT: When citing sources, place [N] on the SAME LINE immediately after the claim it "
    "supports — never on a separate line, never as a standalone paragraph. "
    "Append a ---CITATIONS--- block at the very END of your entire response. "
    "Each [N] must correspond to exactly one entry in that block. Assign a NEW integer to each distinct "
    "source; never reuse the same [N] for a different source, and never use [N] for anything other than "
    "a citation (e.g. do not write 'Step [3]' or 'Field [18]').\n\n"
    "IMPORTANT — do NOT use markdown hyperlink syntax [text](url) anywhere in your response body. "
    "All source references must go through the [N] chip system above. "
    "Bare URLs (https://...) are fine to include as plain text.\n\n"
    "The citations block must be valid JSON in this exact format:\n"
    "---CITATIONS---\n"
    '[{"ref": 1, "document_title": "Page or document title", "quoted_text": "Exact short excerpt that supports the claim", "url": "https://example.com/page", "source": "web"}]\n'
    "---END_CITATIONS---\n\n"
    "For document (non-web) sources, omit 'url'/'source' and include 'page' (integer) and/or 'section' (string) instead. "
    "Keep quoted_text under 300 characters. If a claim is not supported by any supplied source, do not fabricate a citation — state the limitation instead."
)

# Per workflow node `type` — guidance that doesn't depend on sources being present.
INTELLIDOC_BY_AGENT_TYPE: Dict[str, str] = {
    "AssistantAgent": "",  # citation block is added conditionally below
    "UserProxyAgent": (
        "Represent the user or human input clearly and concisely for downstream agents; do not override "
        "workflow routing unless configured to do so."
    ),
    "DelegateAgent": (
        "Focus on your delegated subtask; synthesize inputs you are given without restating full "
        "workflow instructions from other agents."
    ),
    "GroupChatManager": (
        "Synthesize delegate outputs fairly; preserve critical constraints and conflicts from upstream "
        "context in your summary."
    ),
    "MCPServer": (
        "When invoking tools, follow the tool schema; return results in the shape downstream nodes expect."
    ),
    "StartNode": "",
    "EndNode": "",
}


def intellidoc_addendum_for_node(
    agent_node: Dict[str, Any],
    has_sources: bool = False,
) -> str:
    """
    Build the full platform addendum for this graph node.

    Args:
        agent_node: The workflow graph node dict.
        has_sources: True if the agent will receive at least one source
                     (documents, web search results, file attachments, or
                     upstream agent citations).  When False, citation
                     instructions are omitted to avoid confusing the LLM.
    """
    if not agent_node or not isinstance(agent_node, dict):
        return ""

    node_type = agent_node.get("type") or "AssistantAgent"
    parts = [INTELLIDOC_CORE.strip()]

    # Source-aware guidance
    if has_sources:
        parts.append(INTELLIDOC_SOURCES_ADDENDUM.strip())
        if node_type == "AssistantAgent":
            parts.append(CITATION_FORMAT_BLOCK.strip())

    # Per-type guidance (non-citation)
    extra = INTELLIDOC_BY_AGENT_TYPE.get(node_type, "").strip()
    if extra:
        parts.append(extra)

    body = "\n\n".join(parts)
    return SECTION_HEADER + body
