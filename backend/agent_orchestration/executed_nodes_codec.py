"""
Serialize / deserialize workflow node outputs stored in execution_record.executed_nodes.

Values are usually plain strings. When an agent produces structured citations (doc-tool
synthesis), we store {"text": str, "citations": [...]} so downstream agents can receive
grounding metadata while conversation_history stays plain text.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Keys for structured handoff (must match JSON stored in executed_nodes)
TEXT_KEY = "text"
CITATIONS_KEY = "citations"


def pack_executed_output(text: str, citations: Optional[List[Dict[str, Any]]] = None) -> Any:
    """
    Store node output for executed_nodes. Uses a dict only when citations are non-empty.
    """
    if citations:
        return {TEXT_KEY: text, CITATIONS_KEY: list(citations)}
    return text if text is not None else ""


def plain_executed_output(value: Any) -> str:
    """User-facing / conversation_history text."""
    if value is None:
        return ""
    if isinstance(value, dict) and TEXT_KEY in value:
        t = value.get(TEXT_KEY)
        return t if isinstance(t, str) else str(t)
    return str(value)


def citations_from_executed_output(value: Any) -> List[Dict[str, Any]]:
    """Structured citations from a packed executed_nodes value, or []."""
    if isinstance(value, dict):
        raw = value.get(CITATIONS_KEY)
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
    return []


def format_upstream_citations_block(agent_name: str, citations: List[Dict[str, Any]]) -> str:
    """
    Human-readable block appended for downstream LLM prompts so [N] markers stay interpretable.
    """
    if not citations:
        return ""
    lines = [
        "",
        f'=== Grounded source references from upstream agent "{agent_name}" '
        f"(maps to [N] markers in the text above) ===",
    ]
    for c in citations:
        ref = c.get("ref", "?")
        title = c.get("document_title") or "Document"
        qt = (c.get("quoted_text") or "").replace("\n", " ").strip()
        if len(qt) > 400:
            qt = qt[:400] + "…"
        loc_parts = []
        if c.get("page") is not None:
            loc_parts.append(f"p.{c['page']}")
        if c.get("section"):
            loc_parts.append(str(c["section"]))
        loc = f" ({', '.join(loc_parts)})" if loc_parts else ""
        lines.append(f'  [{ref}] {title}{loc}: "{qt}"')
    return "\n".join(lines)
