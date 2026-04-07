import json
import logging
import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

from asgiref.sync import sync_to_async
from django.db import transaction

from agent_orchestration.chat_manager import ChatManager
from agent_orchestration.llm_file_service import LLMFileUploadService
from agent_orchestration.llm_provider_manager import LLMProviderManager
from users.models import IntelliDocProject, ProjectDocument, ProjectDocumentSummary

logger = logging.getLogger(__name__)


def _upsert_document_summary_sync(
    document: ProjectDocument,
    long_summary: str,
    short_summary: str,
    llm_provider: str,
    llm_model: str,
) -> ProjectDocumentSummary:
    """
    Synchronous ORM upsert helper.
    Must be executed via sync_to_async when called from async context.
    """
    with transaction.atomic():
        summary_obj, _ = ProjectDocumentSummary.objects.update_or_create(
            document=document,
            defaults={
                "long_summary": long_summary,
                "short_summary": short_summary,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "summarizer_used": "file_api_llm",
            },
        )
    return summary_obj


@dataclass
class DocumentSummaryResult:
    long_summary: str
    short_summary: str
    raw_response: str


def _extract_json_object(raw: str) -> Optional[str]:
    """
    Extract the first top-level JSON object from a model response.
    Handles code-fences and leading/trailing commentary defensively.
    """
    if not raw:
        return None

    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE).strip()

    # Find first `{` and last `}` and attempt to parse the substring.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return cleaned[start : end + 1]


def _try_parse_json(text: str) -> Optional[dict]:
    """Try multiple strategies to parse JSON from LLM output."""
    if not text:
        return None

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: fix common escape issues from local models
    # Ollama sometimes produces: {"key": "value with \"quotes\""}
    # which is valid JSON, but sometimes the extraction mangles it
    try:
        # Try replacing escaped quotes that got double-escaped
        fixed = text.replace('\\"', '"').replace('\\\\', '\\')
        # Re-extract JSON object after fixing
        start = fixed.find("{")
        end = fixed.rfind("}")
        if start >= 0 and end > start:
            return json.loads(fixed[start:end + 1])
    except json.JSONDecodeError:
        pass

    # Strategy 3: use regex to extract key-value pairs directly
    try:
        long_match = re.search(r'"long[_-]?summary"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}]', text, re.DOTALL)
        short_match = re.search(r'"short[_-]?summary"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}]', text, re.DOTALL)
        if long_match or short_match:
            result = {}
            if long_match:
                result['long_summary'] = long_match.group(1).replace('\\"', '"').replace('\\n', '\n')
            if short_match:
                result['short_summary'] = short_match.group(1).replace('\\"', '"').replace('\\n', '\n')
            return result
    except Exception:
        pass

    return None


def _parse_long_short_summaries(raw_response: str) -> Tuple[str, str]:
    """
    Parse provider output into (long_summary, short_summary).
    Handles various JSON formats from cloud and local LLMs.
    """
    json_obj_str = _extract_json_object(raw_response)

    # Try parsing the extracted JSON with multiple strategies
    data = _try_parse_json(json_obj_str) if json_obj_str else None

    # Also try parsing the full raw response (some models return clean JSON)
    if not data:
        data = _try_parse_json(raw_response)

    if data and isinstance(data, dict):
        long_summary = (data.get("long_summary") or data.get("longSummary") or "").strip()
        short_summary = (data.get("short_summary") or data.get("shortSummary") or "").strip()
        if long_summary or short_summary:
            return long_summary, short_summary

    # Heuristic fallback: look for text markers
    long_m = re.search(r"long[_ ]summary\s*[:\-]\s*", raw_response, flags=re.IGNORECASE)
    short_m = re.search(r"short[_ ]summary\s*[:\-]\s*", raw_response, flags=re.IGNORECASE)

    if long_m and short_m and short_m.start() > long_m.start():
        long_part = raw_response[long_m.end() : short_m.start()].strip().strip('"').strip()
        short_part = raw_response[short_m.end() :].strip().strip('"').strip('}').strip()
        return long_part, short_part

    return raw_response.strip(), ""


async def ensure_document_file_uploaded(
    project: IntelliDocProject,
    document: ProjectDocument,
    llm_provider: str,
) -> Tuple[str, str]:
    """
    Ensure document has a provider file_id (lazy upload if missing).

    Returns:
      (normalized_provider, file_id)
    where normalized_provider is one of: openai, anthropic, google
    """
    provider_norm = (llm_provider or "").lower().strip()
    if provider_norm == "gemini":
        provider_norm = "google"

    field_map = {
        "openai": "llm_file_id_openai",
        "anthropic": "llm_file_id_anthropic",
        "google": "llm_file_id_google",
    }
    file_field = field_map.get(provider_norm)
    if not file_field:
        raise ValueError(f"Unsupported llm_provider for doc summarization: {llm_provider}")

    existing = getattr(document, file_field, None)
    if existing:
        return provider_norm, existing

    service = LLMFileUploadService(project)
    upload_result = await service._upload_to_provider(document, provider_norm)
    file_id = upload_result.get("file_id")
    if not file_id:
        raise RuntimeError(f"Failed to upload document to provider {provider_norm}: {upload_result.get('error')}")

    # Refresh document so subsequent writes use the persisted file_id field.
    await sync_to_async(document.refresh_from_db)()

    existing2 = getattr(document, file_field, None)
    if not existing2:
        # As a safety net, if the DB refresh didn't pick up, trust returned file_id
        return provider_norm, file_id

    return provider_norm, existing2


class FileBasedDocumentSummarizer:
    """
    Generate exactly one long+short summary per document by calling the provider LLM
    with the uploaded document file reference (LLM File API).
    """

    def __init__(self):
        self.llm_provider_manager = LLMProviderManager()

    async def generate_document_summaries(
        self,
        project: IntelliDocProject,
        document: ProjectDocument,
        llm_provider: str,
        llm_model: str,
    ) -> DocumentSummaryResult:
        provider_norm = (llm_provider or "").lower().strip()
        is_local = provider_norm == "ollama"

        system_prompt = (
            "You are a professional document analyst. "
            "Return ONLY valid JSON. Do not include markdown."
        )

        if is_local:
            # Ollama / local models: send extraction_text directly (no File API)
            doc_text = await sync_to_async(lambda: document.extraction_text)()
            if not doc_text:
                raise RuntimeError(f"No extracted text for document {document.original_filename}")
            # Truncate to fit context (local models have smaller context windows)
            max_chars = 24000  # ~6K tokens for a 4B model
            truncated = doc_text[:max_chars]
            if len(doc_text) > max_chars:
                truncated += "\n\n[Document truncated for summarization]"

            user_prompt = (
                f"Below is the text of the document '{document.original_filename}':\n\n"
                f"---\n{truncated}\n---\n\n"
                "Create:\n"
                "1) long_summary: approximately 1500 words covering all major sections, arguments, and conclusions.\n"
                "2) short_summary: approximately 150 words capturing the core essence.\n"
                "Output JSON only with keys: long_summary, short_summary. No other keys or commentary.\n"
            )
            formatted_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        else:
            # Cloud providers: use File API upload
            provider_norm_file, file_id = await ensure_document_file_uploaded(
                project=project,
                document=document,
                llm_provider=llm_provider,
            )
            provider_norm = provider_norm_file

            user_prompt = (
                "Using the attached document, create:\n"
                "1) long_summary: approximately 3000 words covering all major sections, arguments, and conclusions.\n"
                "2) short_summary: approximately 200 words capturing the core essence.\n"
                "Requirements:\n"
                "- Output JSON only with keys: long_summary, short_summary.\n"
                "- long_summary must be the main ~3000-word summary; short_summary must be derived from it.\n"
                "- Do not output any other keys or commentary.\n"
            )

            base_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            file_references = [
                {
                    "file_id": file_id,
                    "filename": document.original_filename,
                    "provider": provider_norm,
                    "file_type": document.file_type,
                    "file_size": document.file_size,
                }
            ]
            formatted_messages = ChatManager.format_messages_with_file_refs(
                messages=base_messages,
                file_references=file_references,
                provider=provider_norm,
            )

        agent_config = {
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "max_tokens": 8000 if is_local else 12000,
        }
        llm_provider_instance = await self.llm_provider_manager.get_llm_provider(agent_config, project)
        if not llm_provider_instance:
            raise RuntimeError(f"Could not initialize LLM provider {llm_provider} for project {project.project_id}")

        response = await llm_provider_instance.generate_response(messages=formatted_messages)
        if getattr(response, "error", None):
            raise RuntimeError(f"LLM summary generation failed: {response.error}")

        long_summary, short_summary = _parse_long_short_summaries(response.text or "")
        return DocumentSummaryResult(
            long_summary=long_summary,
            short_summary=short_summary,
            raw_response=response.text or "",
        )


async def upsert_document_summary(
    project: IntelliDocProject,
    document: ProjectDocument,
    llm_provider: str,
    llm_model: str,
) -> ProjectDocumentSummary:
    """
    Generate (if needed) and persist document-level summaries.
    """
    existing = await sync_to_async(ProjectDocumentSummary.objects.select_related("document").filter(document=document).first)()
    if existing and existing.long_summary and existing.short_summary:
        return existing

    summarizer = FileBasedDocumentSummarizer()
    result = await summarizer.generate_document_summaries(
        project=project,
        document=document,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )

    # Idempotent upsert: one summary row per document.
    summary_obj = await sync_to_async(_upsert_document_summary_sync)(
        document=document,
        long_summary=result.long_summary,
        short_summary=result.short_summary,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
    return summary_obj

