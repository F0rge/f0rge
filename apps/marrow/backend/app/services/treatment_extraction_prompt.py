from __future__ import annotations

import base64
from typing import List, Optional

from app.schemas.treatment import ExtractedTreatmentsPayload
from app.services.lab_extraction_prompt import MODEL_CAPABILITIES, parse_response

SYSTEM_PROMPT = """\
You are a medical prescription parser. Inputs may be in Portuguese, French, \
Spanish, Italian, or English. Emit drug names in the original language when \
clear; otherwise use English.

# Your job
Read the entire prescription and emit one entry in `treatments` for every \
distinct medication prescribed. **Completeness matters** — if the document lists \
three drugs, return three treatment objects.

For each medication extract:
- `name`: drug name (required)
- `type`: one of antibiotic, antimicrobial, prescription, intervention, protocol, other \
(default prescription for standard meds)
- `start_date`: ISO date YYYY-MM-DD when the course starts (use prescription date if shown)
- `end_date`: ISO date when the course ends, or null if ongoing / not specified
- `dose`: free-text dose e.g. "550mg", "1 comprimido"
- `doses_per_day`: integer 1-12 from frequency (e.g. "3x daily" → 3), or null
- `notes`: prescriber instructions, warnings, or pharmacy notes
- `group_name`: optional batch label e.g. prescription date or doctor name

Set document-level `confidence` 0.0-1.0 reflecting how clearly you could read the \
prescription. Use confidence below 0.5 only when the document is largely illegible.

If the document contains no identifiable medications (blank, unreadable handwriting \
only, or not a prescription), return `treatments` as an empty list with confidence 0.

Return ONLY valid JSON matching the schema provided.
"""


def _schema_text(schema_json: str, filename: Optional[str] = None) -> str:
    parts = ["Return a JSON object matching this schema:", schema_json]
    if filename:
        parts.append(f"\nSource filename: {filename}")
    return "\n".join(parts)


def build_pdf_messages(
    pdf_bytes: bytes,
    schema_json: str,
    filename: Optional[str] = None,
) -> List[dict]:
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    file_data_url = f"data:application/pdf;base64,{b64}"
    user_content = [
        {
            "type": "file",
            "file": {
                "filename": filename or "prescription.pdf",
                "file_data": file_data_url,
            },
        },
        {"type": "text", "text": _schema_text(schema_json, filename=filename)},
    ]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_image_messages(
    image_bytes: bytes,
    mime_type: str,
    schema_json: str,
    filename: Optional[str] = None,
) -> List[dict]:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"
    user_content = [
        {"type": "image_url", "image_url": {"url": data_url}},
        {"type": "text", "text": _schema_text(schema_json, filename=filename)},
    ]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def get_response_format(model: str) -> dict:
    caps = MODEL_CAPABILITIES.get(model, set())
    if "json_schema" in caps:
        schema = ExtractedTreatmentsPayload.model_json_schema()
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "ExtractedTreatmentsPayload",
                "strict": True,
                "schema": schema,
            },
        }
    return {"type": "json_object"}


__all__ = [
    "MODEL_CAPABILITIES",
    "SYSTEM_PROMPT",
    "build_image_messages",
    "build_pdf_messages",
    "get_response_format",
    "parse_response",
]
