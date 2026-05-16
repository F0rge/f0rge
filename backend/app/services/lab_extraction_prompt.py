from __future__ import annotations

import base64
import json
import re
from typing import List

from app.schemas.lab_marker import CatalogHint, ExtractedLabPayload

# ---------------------------------------------------------------------------
# Model capability registry
# ---------------------------------------------------------------------------

# Maps OpenRouter model identifiers to the input modalities they support.
# When "json_schema" is present, we use response_format=json_schema for
# structured output; otherwise we fall back to json_object + prompt-side schema.
MODEL_CAPABILITIES: dict[str, set] = {
    "google/gemini-3-flash-preview": {"text", "image", "pdf", "json_schema"},
    "google/gemini-flash-1.5": {"text", "image", "pdf", "json_schema"},
    "google/gemini-pro-1.5": {"text", "image", "pdf", "json_schema"},
    "openai/gpt-4o": {"text", "image", "json_schema"},
    "openai/gpt-4o-mini": {"text", "image", "json_schema"},
    "anthropic/claude-3.5-sonnet": {"text", "image"},
    "anthropic/claude-3.5-haiku": {"text", "image"},
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a medical lab results parser. Your input may be in Portuguese or English.
Extract all lab markers and return a single JSON object.

For every marker:
1. If it matches an entry in catalog_hints (by canonical name, by listed alias, \
or by close semantic equivalence — case-insensitive, accent-insensitive), set \
canonical_match to that hint's canonical name and leave proposed_canonical null.
2. Otherwise, set proposed_canonical to a new canonical name (lowercase, \
underscore-separated, English where reasonable) and leave canonical_match null.

Rules:
- Capture non-numeric values verbatim in value_text (e.g. "Negative", "Reactive").
- Preserve raw reference-range text in ref_text when the range is not a clean \
pair of numbers (e.g. ">60", "<5.18", "Negative").
- Set confidence (0.0-1.0) to reflect your overall certainty in the extraction.
- Return ONLY a JSON object matching the supplied schema. No markdown, no prose.\
"""

# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------


def _hints_and_schema_text(
    catalog_hints: List[CatalogHint],
    schema_json: str,
) -> str:
    hints_str = json.dumps([h.model_dump() for h in catalog_hints], ensure_ascii=False)
    return (
        f"catalog_hints:\n{hints_str}\n\n"
        f"Response JSON schema:\n{schema_json}\n\n"
        "Return a JSON object matching the schema."
    )


def build_text_messages(
    document_text: str,
    catalog_hints: List[CatalogHint],
    schema_json: str,
) -> List[dict]:
    """Build chat messages for plain-text lab document extraction."""
    user_text = (
        _hints_and_schema_text(catalog_hints, schema_json)
        + f"\n\nDocument:\n{document_text}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]


def build_pdf_messages(
    pdf_bytes: bytes,
    catalog_hints: List[CatalogHint],
    schema_json: str,
) -> List[dict]:
    """Build chat messages for a PDF lab document using OpenRouter file part."""
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    file_data_url = f"data:application/pdf;base64,{b64}"
    user_content = [
        {
            "type": "file",
            "file": {
                "filename": "lab_document.pdf",
                "file_data": file_data_url,
            },
        },
        {
            "type": "text",
            "text": _hints_and_schema_text(catalog_hints, schema_json),
        },
    ]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_image_messages(
    image_bytes: bytes,
    mime_type: str,
    catalog_hints: List[CatalogHint],
    schema_json: str,
) -> List[dict]:
    """Build chat messages for an image lab document."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"
    user_content = [
        {
            "type": "image_url",
            "image_url": {"url": data_url},
        },
        {
            "type": "text",
            "text": _hints_and_schema_text(catalog_hints, schema_json),
        },
    ]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Response parser — three-tier defensive recovery
# ---------------------------------------------------------------------------

_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def parse_response(content: str) -> dict:
    """Attempt to extract a JSON dict from the model's raw output.

    Tier 1: direct json.loads on the stripped text.
    Tier 2: extract from a ```json ... ``` fenced block.
    Tier 3: slice from the first '{' to the last balanced '}'.
    Raises ValueError if all tiers fail.
    """
    text = content.strip()

    # Tier 1 — raw parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Tier 2 — fenced code block
    match = _CODE_BLOCK_RE.search(text)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Tier 3 — first balanced brace pair
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        result = json.loads(text[start : i + 1])
                        if isinstance(result, dict):
                            return result
                    except (json.JSONDecodeError, ValueError):
                        break

    raise ValueError(f"Could not extract JSON from model response: {text[:200]!r}")


def get_response_format(model: str) -> dict:
    """Return the appropriate response_format parameter for the given model."""
    caps = MODEL_CAPABILITIES.get(model, set())
    if "json_schema" in caps:
        schema = ExtractedLabPayload.model_json_schema()
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "ExtractedLabPayload",
                "strict": True,
                "schema": schema,
            },
        }
    return {"type": "json_object"}
