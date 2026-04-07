import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from agent_orchestration.llm_provider_manager import LLMProviderManager
from users.models import (
    IntelliDocProject,
    ProjectDocument,
    ProjectDocumentFolderOrganization,
    ProjectDocumentSummary,
)

logger = logging.getLogger(__name__)


def _extract_json_object(raw_text: str) -> str:
    """
    Extract the first JSON object from a model response.
    We intentionally avoid over-clever parsing here and fall back to a safe heuristic.
    """
    if not raw_text:
        return "{}"

    # Prefer fenced JSON blocks if present.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    # Fallback: best-effort brace extraction.
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start >= 0 and end > start:
        return raw_text[start : end + 1].strip()

    # As a last resort, return empty object.
    return "{}"


def _sanitize_folder_segment(segment: str) -> str:
    seg = (segment or "").strip()
    seg = seg.replace("/", "-").replace("\\", "-")
    # Allow letters/numbers/spaces/underscore/hyphen.
    seg = re.sub(r"[^A-Za-z0-9 _-]", "", seg)
    seg = re.sub(r"\s+", " ", seg).strip()
    return seg


def sanitize_folder_path(folder_path: str, *, max_depth: int = 2, fallback: str = "General") -> str:
    """
    Normalize folder paths to a safe depth<=2 representation like:
    - "Legal"
    - "Legal/Contracts"
    """
    raw = (folder_path or "").strip()
    raw = raw.replace("\\", "/")
    parts = [p for p in raw.split("/") if p.strip()]

    if not parts:
        return fallback

    sanitized_parts = [_sanitize_folder_segment(p) for p in parts]
    sanitized_parts = [p for p in sanitized_parts if p]
    if not sanitized_parts:
        return fallback

    # Enforce maximum depth.
    sanitized_parts = sanitized_parts[:max_depth]
    return "/".join(sanitized_parts)


def _build_one_shot_prompt(docs_payload: List[Dict[str, str]], *, max_folders: int = 10, max_depth: int = 2) -> str:
    # Keep the prompt short; short_summary is already ~200 words.
    return (
        "You are a document organization assistant.\n"
        f"Create an LLM folder taxonomy (up to {max_folders} folders) and assign every document to exactly one folder.\n"
        f"Folder paths must be depth <= {max_depth} (e.g., \"Category\" or \"Category/Subcategory\").\n"
        "Folder names must be concise, human-readable, and reflect the documents' topics/roles.\n"
        "Return ONLY valid JSON (no markdown, no commentary) with this exact schema:\n"
        "{\n"
        '  "folders": ["Category", "Category/Subcategory", ...],\n'
        '  "assignments": { "DOCUMENT_ID": "Category/Subcategory", ... }\n'
        "}\n\n"
        "Documents (each with a short_summary):\n"
        + json.dumps(docs_payload, ensure_ascii=False)
    )


async def _llm_call_assign_folders(
    project: IntelliDocProject,
    llm_provider: str,
    llm_model: str,
    docs_payload: List[Dict[str, str]],
) -> Dict[str, Any]:
    llm_manager = LLMProviderManager()
    provider = await llm_manager.get_llm_provider(
        {"llm_provider": llm_provider, "llm_model": llm_model, "max_tokens": 2500},
        project,
    )
    if not provider:
        raise RuntimeError(f"Could not initialize LLM provider '{llm_provider}' for folder organization")

    messages = [
        {
            "role": "system",
            "content": (
                "Return ONLY valid JSON. Do not include markdown. "
                "If you cannot decide, still return JSON with best-effort assignments."
            ),
        },
        {
            "role": "user",
            "content": _build_one_shot_prompt(docs_payload),
        },
    ]

    response = await provider.generate_response(messages=messages)
    raw_text = getattr(response, "text", None) or getattr(response, "raw", None) or ""
    json_text = _extract_json_object(raw_text)
    parsed = json.loads(json_text)
    return parsed


def _persist_folder_organization(
    project: IntelliDocProject,
    documents: List[ProjectDocument],
    assignments: Dict[str, str],
    llm_provider: str,
    llm_model: str,
) -> Dict[str, str]:
    """
    Persist doc->folder_path mappings. Returns a guaranteed map for provided documents.
    """
    # Normalize keys to string UUIDs.
    doc_ids = [str(d.document_id) for d in documents]
    normalized_assignments = {str(k): v for k, v in (assignments or {}).items()}

    result_map: Dict[str, str] = {}
    for doc_id in doc_ids:
        result_map[doc_id] = sanitize_folder_path(normalized_assignments.get(doc_id), fallback="General")

    # Upsert per document (one row per document).
    # Using ORM sync operations here is fine: unified_services_fixed invokes this in a worker context.
    for doc in documents:
        folder_path = result_map[str(doc.document_id)]
        ProjectDocumentFolderOrganization.objects.update_or_create(
            document=doc,
            defaults={
                "folder_path": folder_path,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "organization_method": "llm_folder_org",
            },
        )

    return result_map


def generate_and_persist_document_folder_organization(
    *,
    project: IntelliDocProject,
    documents: List[ProjectDocument],
    llm_provider: Optional[str],
    llm_model: Optional[str],
) -> Dict[str, str]:
    """
    Generate LLM folder paths for each document using ProjectDocumentSummary.short_summary
    and persist them into ProjectDocumentFolderOrganization.

    Returns:
      Map: document_id(str UUID) -> folder_path(str, depth<=2).
    """
    if not documents:
        return {}

    # If we don't have LLM config, we cannot do the LLM decision.
    if not llm_provider or not llm_model:
        return {str(d.document_id): "General" for d in documents}

    # Load existing folder assignments if present.
    existing = ProjectDocumentFolderOrganization.objects.filter(document__project=project).filter(
        document__in=documents
    ).values_list("document__document_id", "folder_path")
    existing_map = {str(doc_id): folder_path for doc_id, folder_path in existing}

    # Determine which docs need an LLM assignment.
    missing = [d for d in documents if str(d.document_id) not in existing_map]
    if not missing:
        return {str(d.document_id): existing_map[str(d.document_id)] for d in documents}

    # Load short summaries (short_description input) for missing docs.
    summary_rows = ProjectDocumentSummary.objects.filter(document__project=project).filter(
        document__in=missing
    ).values_list("document__document_id", "short_summary")
    short_map = {str(doc_id): (short_summary or "") for doc_id, short_summary in summary_rows}

    # Build payload for LLM.
    docs_payload: List[Dict[str, str]] = []
    for doc in missing:
        short_summary = (short_map.get(str(doc.document_id), "") or "").strip()
        if not short_summary:
            # We can't meaningfully organize without the short description.
            short_summary = "No short summary available."

        # Keep the payload bounded.
        short_summary = " ".join(short_summary.split())
        docs_payload.append(
            {
                "document_id": str(doc.document_id),
                "short_summary": short_summary[:6000],
                "original_filename": doc.original_filename[:255],
            }
        )

    # One-shot assignment for this initial implementation.
    # If you expect extremely large document sets, we can upgrade this to a taxonomy+batch strategy.
    # asyncio.run() creates an isolated event loop — safe in a sync Django view context and
    # does not depend on any shared ThreadPoolExecutor that can fail on interpreter shutdown.
    parsed = asyncio.run(_llm_call_assign_folders(project, llm_provider, llm_model, docs_payload))

    assignments = (parsed or {}).get("assignments") or {}
    return _persist_folder_organization(
        project=project,
        documents=missing,
        assignments=assignments,
        llm_provider=llm_provider,
        llm_model=llm_model,
    ) | {
        str(d.document_id): existing_map[str(d.document_id)]
        for d in documents
        if str(d.document_id) in existing_map
    }

