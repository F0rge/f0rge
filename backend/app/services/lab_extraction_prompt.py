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
# NOTE: json_schema (strict structured output) is deliberately excluded for the
# Gemini family. Empirically, enabling strict json_schema mode with Gemini Flash
# causes severe array-output truncation — a multi-page blood panel that should
# extract 30-60 markers returns only 1-2. The Pydantic ExtractedLabPayload
# validation on our side enforces the same schema with better error reporting,
# so json_object is sufficient and produces materially better extractions.
MODEL_CAPABILITIES: dict[str, set] = {
    "google/gemini-3-flash-preview": {"text", "image", "pdf"},
    "google/gemini-flash-1.5": {"text", "image", "pdf"},
    "google/gemini-pro-1.5": {"text", "image", "pdf"},
    "openai/gpt-4o": {"text", "image", "json_schema"},
    "openai/gpt-4o-mini": {"text", "image", "json_schema"},
    "anthropic/claude-3.5-sonnet": {"text", "image"},
    "anthropic/claude-3.5-haiku": {"text", "image"},
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a medical lab results parser. Inputs may be in Portuguese, French, \
Spanish, Italian, or English. Translate panel names and findings to English in \
all string fields you emit.

# Your job
Read the entire document table-by-table and emit one marker entry for every \
single row of every results table — hematology, chemistry, lipids, hormones, \
vitamins, immunology, serology, anything quantified. **Completeness is the \
single most important metric of your output.** A real blood panel typically \
contains 25-60 distinct rows; if your output contains only one or two markers \
for a multi-page blood report you have failed. Do not summarize, do not pick a \
representative subset, do not skip "normal" rows, do not stop after the first \
marker. Repeat for every table on every page until you have exhausted the \
document.

For imaging reports (CT, MRI, ECG, Holter, X-ray, AngioTC) and other narrative \
documents with no measured rows, return an empty markers list `[]` and put the \
findings narrative in `lab.notes`. Do not invent markers for descriptive text.

# Multi-modality documents (read this carefully)
A single PDF often contains MORE than one kind of report stitched together: \
blood work plus a chest X-ray, blood work plus a breath test, blood work plus \
EBV serology, blood plus urinalysis, etc. **Never silently drop a section.** \
When this happens:
- Extract every quantified row from every section as markers.
- Put any narrative findings from the non-tabular sections (imaging report, \
breath test interpretation, microbiology culture result) verbatim into \
`lab.notes` — translated to English.
- Reflect every included section in `lab.name` using ` + ` as a separator \
(e.g. "Comprehensive Blood Panel + Chest X-Ray Report", "Blood + EBV Serology \
+ Urine", "Blood + SIBO Breath Test").
- Set `lab.type = "comprehensive"` whenever the document spans more than one \
modality.

# lab.type — purpose-led, not count-led
Pick from: blood / breath / imaging / microbiology / allergy / comprehensive / \
other. The type reflects the document's **primary clinical purpose**, not which \
sub-table has the most rows. Specifically:
- `allergy` — Phadiatop panels, specific-IgE panels, atopy screens, mast-cell \
work-ups. Use `allergy` even when the same panel includes routine hematology \
or chemistry as supporting context.
- `comprehensive` — multi-modality batteries (blood + breath test, blood + \
imaging, blood + serology, OAT, GI-MAP, stool tests). Always `comprehensive` \
when the doc mixes modalities.
- `microbiology` — culture results, sensitivity panels, antigen screens.
- `breath` — SIBO, lactose, fructose breath tests when standalone.
- `imaging` — CT, MRI, ECG, Holter, X-ray, AngioTC, ultrasound, echo. Includes \
narrative-only cardiology studies (stress tests, Holters).
- `blood` — reserve for routine blood draws containing ONLY hematology + \
chemistry + lipids with no allergy / serology / imaging / breath-test sections.
- `other` — anything that doesn't fit (e.g. genetic panels).

# lab.name — specific and in English
Compose `lab.name` in English; translate source-language panel titles (e.g. \
"Hematologia e Bioquímica" → "Hematology and Biochemistry", "Hémogramme" → \
"Complete Blood Count"). When the document has multiple distinct sections, \
name them with ` + ` separators (see Multi-modality above). Be specific — if \
the source labels itself "Strep A Screen", "Cholesterol & Iron Studies", \
"Coagulation + Cardiac", reproduce that specificity rather than collapsing to \
a generic "Comprehensive Blood Panel". NEVER put the laboratory or provider \
name in `lab.name`; that goes in `lab.lab_location`.

# Filename as a secondary signal
When the caller supplies a `filename` alongside the document, treat panel-type \
tokens in the filename (`Allergies`, `Microbiology`, `SIBO`, `Holter`, \
`StressTest`, `Stool`, `Cranio`, `Coronarias`, etc.) as a SECONDARY \
classification signal — useful as a tiebreaker when the document is genuinely \
ambiguous. Never let the filename override what's actually inside the document.

# Canonical name resolution
For every marker:
1. If it matches an entry in catalog_hints (by canonical, by listed alias, or \
by close semantic equivalence — case-insensitive, accent-insensitive, \
language-insensitive), set `canonical_match` to that hint's canonical and \
leave `proposed_canonical` null.
2. Otherwise, set `proposed_canonical` to a new lowercase snake_case canonical \
(English where reasonable; map "Hemoglobina" to "hemoglobin", "Leucócitos" to \
"leukocytes", "Plaquetas" to "platelets", etc.). Leave `canonical_match` null.

# Value capture
- Numeric value goes in `value` as a float. Non-numeric (NEGATIVE, POSITIVE, \
Reactive, Class 6, <DL, >100) goes in `value_text` verbatim. `value` and \
`value_text` are mutually compatible — set whichever applies.
- `unit` from the source (g/dL, mmol/L, UI/mL, etc.). Empty string is fine \
when the source omits it.
- Numeric reference range bounds go in `ref_low` / `ref_high`. If the range \
is unidirectional (">60", "<5.18", "Negative", "<14.0"), put the original \
text in `ref_text` and leave the numeric bound(s) null — downstream \
flag-computation parses these inequalities.

# Confidence calibration
Set `confidence` to reflect **extraction completeness**, not just data \
legibility. If you skipped any section, omitted a known sub-report (imaging \
narrative, breath test curve, hormone panel), or are unsure about `lab.type`, \
drop confidence to **0.7 or lower** so the row is flagged for human review.

# Output
Return ONLY a JSON object matching the supplied schema. No markdown fences, \
no prose. Aim high on completeness — missing markers and missing narrative \
sections degrade downstream analysis far more than over-extracting.\
"""

# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------


def _hints_and_schema_text(
    catalog_hints: List[CatalogHint],
    schema_json: str,
    filename: str | None = None,
) -> str:
    hints_str = json.dumps([h.model_dump() for h in catalog_hints], ensure_ascii=False)
    filename_block = (
        f"filename: {filename}\n(treat as a secondary classification signal only)\n\n"
        if filename
        else ""
    )
    return (
        f"{filename_block}"
        f"catalog_hints:\n{hints_str}\n\n"
        f"Response JSON schema:\n{schema_json}\n\n"
        "Return a JSON object matching the schema."
    )


def build_text_messages(
    document_text: str,
    catalog_hints: List[CatalogHint],
    schema_json: str,
    filename: str | None = None,
) -> List[dict]:
    """Build chat messages for plain-text lab document extraction."""
    user_text = (
        _hints_and_schema_text(catalog_hints, schema_json, filename=filename)
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
    filename: str | None = None,
) -> List[dict]:
    """Build chat messages for a PDF lab document using OpenRouter file part."""
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    file_data_url = f"data:application/pdf;base64,{b64}"
    user_content = [
        {
            "type": "file",
            "file": {
                "filename": filename or "lab_document.pdf",
                "file_data": file_data_url,
            },
        },
        {
            "type": "text",
            "text": _hints_and_schema_text(
                catalog_hints, schema_json, filename=filename
            ),
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
    filename: str | None = None,
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
            "text": _hints_and_schema_text(
                catalog_hints, schema_json, filename=filename
            ),
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
