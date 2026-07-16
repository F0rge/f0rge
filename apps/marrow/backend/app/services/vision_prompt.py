from __future__ import annotations

import base64
import json
import re
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pydantic models for structured vision response
# ---------------------------------------------------------------------------


class VisionIngredient(BaseModel):
    name: str
    visible: bool = True
    confidence: float


class VisionResult(BaseModel):
    dish_name: str
    cuisine: Optional[str] = None
    confidence: float
    ingredients: list[VisionIngredient]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a food identification assistant. Given a photo, you output \
structured JSON describing the dish and its ingredients.

## Process
1. Identify the dish or meal. If the photo contains multiple dishes, pick \
the most prominent one and note others in dish_name (e.g. "rice with \
grilled chicken and side salad").
2. List every ingredient you can see in the photo. Mark each as \
visible=true.
3. Infer additional ingredients that are likely present based on common \
recipes for this dish. Mark each as visible=false.
4. Assign a confidence score (0.0-1.0) to each ingredient. If you are \
unsure, set confidence below 0.5 — do not guess.
5. Assign an overall confidence score for the dish identification.

## Output format
Return ONLY a JSON object (no markdown, no commentary) matching this schema:

{
  "dish_name": "string — lowercase, concise name",
  "cuisine": "string or null — e.g. italian, japanese, mexican",
  "confidence": 0.0-1.0,
  "ingredients": [
    {"name": "ingredient", "visible": true, "confidence": 0.0-1.0}
  ]
}

## Ingredient naming rules
- Lowercase, singular form: "tomato" not "Tomatoes", "egg" not "eggs"
- Use common English names: "cilantro" not "coriander leaf"
- Be specific when visible: "red bell pepper" not just "pepper"

## Edge cases
- Non-food image: {"dish_name": "unknown", "cuisine": null, "confidence": 0, \
"ingredients": []}
- Unclear or blurry image: set confidence below 0.3 and include only what \
you can identify with reasonable certainty.
- Multiple separate dishes: describe the primary dish; mention others in \
dish_name if relevant.\
"""

# Appended when catalog_context is provided. ~2–4k tokens for a typical seed
# catalog (~287 entries); soft cap at 500 entries keeps worst case bounded.
CATALOG_PROMPT_ADDENDUM = """\

## User ingredient catalog
The user maintains a personal ingredient catalog below. Use it to align \
ingredient names with their tracked vocabulary.

Rules:
- When a visible or inferred ingredient plausibly matches a catalog entry, \
emit the exact canonical_name from the list in ingredients[].name.
- Treat listed aliases as recognition aids only — never emit an alias as \
the ingredient name; always output the canonical_name.
- If nothing in the catalog fits what you see, use the best free-form \
visual name (lowercase, singular) and apply normal confidence rules.

Catalog (alphabetical, canonical names):
"""

USER_PROMPT = (
    "Analyze this food photo. Return a JSON object with dish_name, "
    "cuisine, confidence, and ingredients array."
)


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------


def build_messages(
    image_bytes: bytes,
    *,
    catalog_context: Optional[str] = None,
) -> list[dict]:
    """Build OpenRouter-compatible chat messages with an embedded image.

    Encodes the image as a base64 data URL and returns messages in
    the OpenAI vision chat-completions format.

    When catalog_context is a non-empty string, appends the user ingredient
    catalog instructions and list to the system prompt.
    """
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = "data:image/jpeg;base64," + b64

    system_content = SYSTEM_PROMPT
    if catalog_context:
        system_content = system_content + CATALOG_PROMPT_ADDENDUM + catalog_context

    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                },
                {
                    "type": "text",
                    "text": USER_PROMPT,
                },
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)
_BRACE_RE = re.compile(r"\{.*\}", re.DOTALL)

_FALLBACK = VisionResult(
    dish_name="parse_error",
    cuisine=None,
    confidence=0.0,
    ingredients=[],
)


def parse_vision_response(raw_text: str) -> VisionResult:
    """Parse the model's text output into a VisionResult.

    Handles clean JSON, JSON in markdown code blocks, JSON embedded in
    surrounding text, and falls back gracefully on malformed output.
    """
    text = raw_text.strip()

    # Attempt 1: direct parse
    try:
        return VisionResult(**json.loads(text))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Attempt 2: extract from markdown code block
    match = _CODE_BLOCK_RE.search(text)
    if match:
        try:
            return VisionResult(**json.loads(match.group(1)))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # Attempt 3: find first { ... last } in the text
    match = _BRACE_RE.search(text)
    if match:
        try:
            return VisionResult(**json.loads(match.group(0)))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    return _FALLBACK


# ---------------------------------------------------------------------------
# Expected JSON schema (for structured-output / tool-use prompts)
# ---------------------------------------------------------------------------

EXPECTED_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "dish_name": {"type": "string"},
        "cuisine": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "visible": {"type": "boolean"},
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                },
                "required": ["name", "confidence"],
            },
        },
    },
    "required": ["dish_name", "confidence", "ingredients"],
}
