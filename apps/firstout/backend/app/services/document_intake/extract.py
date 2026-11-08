"""Turn a supplier PDF or photo into structured JSON via OpenRouter.

Text-layer PDFs are sent as text. Photos and scans are sent to a
vision-capable model. Tests mock ``extract_supplier_document``.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import settings
from app.exceptions import DocumentLlmUnconfiguredError
from app.schemas.document_intake import ExtractedDocument, ModelUsage
from f0rge_core.exceptions import ValidationError

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
_TEXT_ALNUM_MIN = 80
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SYSTEM_PROMPT = """You read supplier proformas and invoices for a South African furniture shop.
Return one JSON object and nothing else. Use these keys:
document_kind (proforma or invoice),
supplier: {name, vat_number, address},
document_number, document_date (YYYY-MM-DD), currency (ISO code, ZAR if rands),
po_reference (the buyer's purchase order number if printed, else null),
proforma_number (the supplier proforma number if printed, else null),
lines: [{supplier_code, description, qty, unit_price, discount_percent, discount_amount, vat_rate, vat_amount, line_total}],
charges: [{description, amount}] for shipping or other charges that are not products,
subtotal, vat_total, total, payment_terms, deposit.
Numbers are decimals. vat_rate is a fraction (0.15 for 15%). Use null when a field is not on the document.
Do not invent lines. Keep the supplier's product code separate from the description.
"""


@dataclass
class PreparedDocument:
    text: str = ""
    images: list[tuple[str, bytes]] = field(default_factory=list)
    pdf_bytes: Optional[bytes] = None
    filename: str = "document"


def sniff_content_type(data: bytes, filename: str, content_type: Optional[str]) -> str:
    stated = (content_type or "").split(";")[0].strip().lower()
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if stated in {"application/pdf", "image/png", "image/jpeg", "image/jpg"}:
        return "image/jpeg" if stated == "image/jpg" else stated
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    raise ValidationError("Upload a PDF, JPG, or PNG.")


def stored_extension(content_type: str) -> str:
    if content_type == "image/png":
        return "png"
    if content_type == "image/jpeg":
        return "jpg"
    return "pdf"


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError:
        return ""
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return ""
    parts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            extracted = page.extract_text() or ""
        except Exception:
            extracted = ""
        if extracted.strip():
            parts.append(f"--- page {index} ---\n{extracted.strip()}")
    return "\n\n".join(parts)


def text_is_usable(text: str) -> bool:
    return sum(1 for char in text if char.isalnum()) >= _TEXT_ALNUM_MIN


def prepare_document(data: bytes, filename: str, content_type: str) -> PreparedDocument:
    if content_type == "application/pdf":
        text = _pdf_text(data)
        prepared = PreparedDocument(text=text, filename=filename or "document.pdf")
        if not text_is_usable(text):
            prepared.pdf_bytes = data
        return prepared
    return PreparedDocument(
        images=[(content_type, data)],
        filename=filename or "scan.jpg",
    )


def _data_url(media_type: str, data: bytes) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _user_parts(prepared: PreparedDocument, kind: str) -> list[dict]:
    parts: list[dict] = [
        {
            "type": "text",
            "text": (
                f"This is a supplier {kind}. Extract it as JSON. "
                "If a field is not visible, use null."
            ),
        }
    ]
    if prepared.text:
        parts.append({"type": "text", "text": prepared.text})
    for media_type, image in prepared.images:
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": _data_url(media_type, image)},
            }
        )
    if prepared.pdf_bytes is not None:
        parts.append(
            {
                "type": "file",
                "file": {
                    "filename": prepared.filename or "document.pdf",
                    "file_data": _data_url("application/pdf", prepared.pdf_bytes),
                },
            }
        )
    return parts


def _parse_json_content(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "Could not read this document. Try a clearer photo or a PDF with a text layer."
        ) from exc
    if not isinstance(parsed, dict):
        raise ValidationError(
            "Could not read this document. Try a clearer photo or a PDF with a text layer."
        )
    return parsed


async def _post_chat(parts: list[dict]) -> tuple[str, ModelUsage]:
    api_key = settings.openrouter_api_key.strip()
    if not api_key:
        raise DocumentLlmUnconfiguredError()
    model = (settings.openrouter_document_model or settings.openrouter_model).strip()
    base = (settings.openrouter_base_url or _OPENROUTER_URL).rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": parts},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise ValidationError("The document reader could not be reached. Try again.") from exc
    if response.status_code >= 400:
        logger.warning("document intake model http %s", response.status_code)
        raise ValidationError(
            "The document reader failed. Try again or type the document in by hand."
        )
    body = response.json()
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValidationError("The document reader returned an empty response.") from exc
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    usage_body = body.get("usage") or {}
    usage = ModelUsage(
        model=str(body.get("model") or model),
        prompt_tokens=int(usage_body.get("prompt_tokens") or 0),
        completion_tokens=int(usage_body.get("completion_tokens") or 0),
        total_tokens=int(usage_body.get("total_tokens") or 0),
    )
    logger.info(
        "document intake model=%s prompt_tokens=%s completion_tokens=%s",
        usage.model,
        usage.prompt_tokens,
        usage.completion_tokens,
    )
    return str(content), usage


async def extract_supplier_document(
    data: bytes,
    filename: str,
    content_type: Optional[str],
    *,
    kind: str,
) -> tuple[ExtractedDocument, ModelUsage]:
    if not data:
        raise ValidationError("Choose a PDF, JPG, or PNG.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError("That file is larger than 8 MB.")
    sniffed = sniff_content_type(data, filename, content_type)
    prepared = prepare_document(data, filename, sniffed)
    content, usage = await _post_chat(_user_parts(prepared, kind))
    parsed = _parse_json_content(content)
    parsed["document_kind"] = kind
    try:
        extracted = ExtractedDocument.model_validate(parsed)
    except Exception as exc:
        raise ValidationError(
            "Could not read this document. Try a clearer photo or a PDF with a text layer."
        ) from exc
    return extracted, usage


_SKU_HINT_PROMPT = """You help a furniture shop name a new catalogue SKU from one supplier line.
Return JSON with keys name, design, fabric, category.
category is a short catalogue group such as Soft Furnishings, or null if the hint does not say.
Do not invent a price or a barcode. Keep name under 255 characters.
"""


async def suggest_sku_fields(description: str, supplier_code: Optional[str], hint: str) -> dict:
    """Ask the document model to apply a plain-language hint. Returns a dict."""
    parts = [
        {
            "type": "text",
            "text": (
                f"Line description: {description}\n"
                f"Supplier code: {supplier_code or ''}\n"
                f"Instruction from the user: {hint}"
            ),
        }
    ]
    api_key = settings.openrouter_api_key.strip()
    if not api_key:
        raise DocumentLlmUnconfiguredError()
    model = (settings.openrouter_document_model or settings.openrouter_model).strip()
    base = (settings.openrouter_base_url or _OPENROUTER_URL).rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SKU_HINT_PROMPT},
            {"role": "user", "content": parts},
        ],
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise ValidationError("The document reader could not be reached. Try again.") from exc
    if response.status_code >= 400:
        raise ValidationError("Could not apply that hint. You can still fill the SKU in yourself.")
    body = response.json()
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValidationError(
            "Could not apply that hint. You can still fill the SKU in yourself."
        ) from exc
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    usage_body = body.get("usage") or {}
    logger.info(
        "document intake sku hint model=%s prompt_tokens=%s completion_tokens=%s",
        body.get("model") or model,
        usage_body.get("prompt_tokens") or 0,
        usage_body.get("completion_tokens") or 0,
    )
    return _parse_json_content(str(content))
