from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
from typing import List, Optional

from pydantic import ValidationError as PydanticValidationError

from app.config import settings
from app.exceptions import ValidationError
from app.schemas.lab_marker import (
    CatalogHint,
    ExtractedLabPayload,
    ExtractionResult,
)
from app.services.lab_extraction_prompt import (
    MODEL_CAPABILITIES,
    build_image_messages,
    build_pdf_messages,
    build_text_messages,
    get_response_format,
    parse_response,
)

logger = logging.getLogger(__name__)

_AUDIT_LOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "extraction_audit.jsonl"
)
_AUDIT_LOG_PATH = os.path.normpath(_AUDIT_LOG_PATH)

_MAX_ATTEMPTS = 3
_AUDIT_MAX_BYTES = 64 * 1024  # 64 KB


def _audit_log(
    *,
    model: str,
    attempts: int,
    confidence: float,
    retried_due_to: List[str],
    raw_response: str,
) -> None:
    """Append a single JSONL audit entry. Never raises — failures are logged only."""
    try:
        os.makedirs(os.path.dirname(_AUDIT_LOG_PATH), exist_ok=True)
        entry = {
            "ts": datetime.datetime.utcnow().isoformat(),
            "model": model,
            "attempts": attempts,
            "confidence": confidence,
            "retried_due_to": retried_due_to,
            "raw_response": raw_response[:_AUDIT_MAX_BYTES],
        }
        with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("Failed to write extraction audit log")


def _hint_canonicals(catalog_hints: List[CatalogHint]) -> set:
    return {h.canonical for h in catalog_hints}


def _cross_check_and_fix(
    payload: ExtractedLabPayload,
    catalog_hints: List[CatalogHint],
    retried_due_to: List[str],
) -> ExtractedLabPayload:
    """Demote hallucinated canonical_match values to proposed_canonical.

    The LLM occasionally returns a canonical_match that does not exist in the
    supplied hints. We silently fix it rather than triggering a retry, but we
    record it in retried_due_to so the UI can surface it.
    """
    valid = _hint_canonicals(catalog_hints)
    fixed_markers = []
    for m in payload.markers:
        if m.canonical_match is not None and m.canonical_match not in valid:
            retried_due_to.append(
                f"hallucinated canonical_match={m.canonical_match!r}; demoted to proposed_canonical"
            )
            fixed = m.model_copy(
                update={
                    "proposed_canonical": m.canonical_match,
                    "canonical_match": None,
                }
            )
            fixed_markers.append(fixed)
        else:
            fixed_markers.append(m)
    return payload.model_copy(update={"markers": fixed_markers})


async def _call_openrouter(messages: List[dict], model: str) -> str:
    """Make a single call to OpenRouter and return the raw content string."""
    from app.services.llm.openrouter import OpenRouterClient
    from app.exceptions import ExternalServiceError

    response_format = get_response_format(model)
    llm_client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        default_model=model,
    )
    try:
        return await llm_client.complete(
            messages,
            model=model,
            response_format=response_format,
            temperature=0.0,
            max_tokens=8192,
        )
    except ExternalServiceError as exc:
        # Preserve existing caller contract: upstream errors raise ValidationError.
        # This mapping is intentionally wrong (502 -> 400) and tracked as a follow-up.
        raise ValidationError(exc.detail) from exc


async def _extract(
    initial_messages: List[dict],
    catalog_hints: List[CatalogHint],
) -> ExtractionResult:
    """Core retry loop shared by all three public extract methods."""
    model = settings.openrouter_model
    messages = list(initial_messages)
    retried_due_to: List[str] = []
    last_error = ""
    last_raw = ""

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        raw = await _call_openrouter(messages, model)
        last_raw = raw

        try:
            parsed_dict = parse_response(raw)
        except ValueError as exc:
            last_error = str(exc)
            if attempt < _MAX_ATTEMPTS:
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Your previous response failed validation: {last_error}. "
                            "Please return a corrected JSON object."
                        ),
                    }
                )
                retried_due_to.append(last_error)
            continue

        try:
            payload = ExtractedLabPayload.model_validate(parsed_dict)
        except PydanticValidationError as exc:
            last_error = str(exc)
            if attempt < _MAX_ATTEMPTS:
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Your previous response failed validation: {last_error}. "
                            "Please return a corrected JSON object."
                        ),
                    }
                )
                retried_due_to.append(last_error)
            continue

        # Cross-check canonical_match values against supplied hints.
        payload = _cross_check_and_fix(payload, catalog_hints, retried_due_to)

        result = ExtractionResult(
            payload=payload,
            raw_response=raw,
            model=model,
            attempts=attempt,
            retried_due_to=retried_due_to,
        )
        await asyncio.to_thread(
            _audit_log,
            model=model,
            attempts=attempt,
            confidence=payload.confidence,
            retried_due_to=retried_due_to,
            raw_response=raw,
        )
        return result

    # All attempts exhausted.
    await asyncio.to_thread(
        _audit_log,
        model=model,
        attempts=_MAX_ATTEMPTS,
        confidence=0.0,
        retried_due_to=retried_due_to,
        raw_response=last_raw,
    )
    raise ValidationError(f"Lab extraction failed after {_MAX_ATTEMPTS} attempts: {last_error}")


class LabExtractionService:
    """DB-free, multimodal lab extraction service backed by OpenRouter."""

    async def extract_text(
        self,
        document_text: str,
        catalog_hints: List[CatalogHint],
        filename: Optional[str] = None,
    ) -> ExtractionResult:
        schema_json = ExtractedLabPayload.model_json_schema().__str__()
        messages = build_text_messages(document_text, catalog_hints, schema_json, filename=filename)
        return await _extract(messages, catalog_hints)

    async def extract_pdf(
        self,
        pdf_bytes: bytes,
        catalog_hints: List[CatalogHint],
        filename: Optional[str] = None,
    ) -> ExtractionResult:
        model = settings.openrouter_model
        caps = MODEL_CAPABILITIES.get(model, set())
        if "pdf" not in caps:
            raise ValidationError(
                f"Current model {model!r} does not support PDF; switch model or convert to image."
            )
        schema_json = ExtractedLabPayload.model_json_schema().__str__()
        messages = build_pdf_messages(pdf_bytes, catalog_hints, schema_json, filename=filename)
        return await _extract(messages, catalog_hints)

    async def extract_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        catalog_hints: List[CatalogHint],
        filename: Optional[str] = None,
    ) -> ExtractionResult:
        model = settings.openrouter_model
        caps = MODEL_CAPABILITIES.get(model, set())
        if "image" not in caps:
            raise ValidationError(f"Current model {model!r} does not support image input.")
        schema_json = ExtractedLabPayload.model_json_schema().__str__()
        messages = build_image_messages(
            image_bytes, mime_type, catalog_hints, schema_json, filename=filename
        )
        return await _extract(messages, catalog_hints)

    async def preview_upload(
        self,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
        catalog_hints: List[CatalogHint],
    ) -> ExtractionResult:
        """Dispatch to the correct extract method based on MIME type.

        Used by the extract-upload router endpoint to keep the router thin.
        Does not persist anything to the database.
        """
        if mime_type == "application/pdf":
            return await self.extract_pdf(file_bytes, catalog_hints, filename=filename)
        if mime_type.startswith("image/"):
            return await self.extract_image(file_bytes, mime_type, catalog_hints, filename=filename)
        raise ValidationError(f"Unsupported MIME type for extraction: {mime_type}")
