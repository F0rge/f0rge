from __future__ import annotations

import json

from app.services.vision_prompt import VisionResult, parse_vision_response


# ---------------------------------------------------------------------------
# Path 1: direct JSON parse
# ---------------------------------------------------------------------------


def test_direct_json_parse_minimal() -> None:
    raw = json.dumps(
        {
            "dish_name": "scrambled eggs",
            "confidence": 0.9,
            "ingredients": [
                {"name": "egg", "visible": True, "confidence": 0.95},
            ],
        }
    )
    result = parse_vision_response(raw)
    assert result.dish_name == "scrambled eggs"
    assert result.confidence == 0.9
    assert len(result.ingredients) == 1
    assert result.ingredients[0].name == "egg"
    assert result.ingredients[0].visible is True


def test_direct_json_parse_with_cuisine_and_multiple_ingredients() -> None:
    raw = json.dumps(
        {
            "dish_name": "pasta carbonara",
            "cuisine": "italian",
            "confidence": 0.92,
            "ingredients": [
                {"name": "spaghetti", "visible": True, "confidence": 1.0},
                {"name": "egg", "visible": True, "confidence": 0.85},
                {"name": "guanciale", "visible": False, "confidence": 0.6},
            ],
        }
    )
    result = parse_vision_response(raw)
    assert result.cuisine == "italian"
    assert len(result.ingredients) == 3
    assert result.ingredients[2].visible is False


def test_direct_json_parse_strips_whitespace() -> None:
    raw = "  \n  " + json.dumps(
        {"dish_name": "rice", "confidence": 1.0, "ingredients": []}
    ) + "  \n"
    result = parse_vision_response(raw)
    assert result.dish_name == "rice"


def test_direct_json_parse_empty_ingredients() -> None:
    raw = json.dumps({"dish_name": "unknown", "confidence": 0.0, "ingredients": []})
    result = parse_vision_response(raw)
    assert result.dish_name == "unknown"
    assert result.ingredients == []


# ---------------------------------------------------------------------------
# Path 2: markdown code block extraction
# ---------------------------------------------------------------------------


def test_code_block_with_json_language_tag() -> None:
    payload = {
        "dish_name": "salad",
        "confidence": 0.8,
        "ingredients": [{"name": "lettuce", "visible": True, "confidence": 0.9}],
    }
    raw = f"Here is the analysis:\n\n```json\n{json.dumps(payload)}\n```\n\nLet me know."
    result = parse_vision_response(raw)
    assert result.dish_name == "salad"
    assert result.ingredients[0].name == "lettuce"


def test_code_block_without_language_tag() -> None:
    payload = {
        "dish_name": "soup",
        "confidence": 0.7,
        "ingredients": [{"name": "broth", "visible": True, "confidence": 0.8}],
    }
    raw = f"```\n{json.dumps(payload)}\n```"
    result = parse_vision_response(raw)
    assert result.dish_name == "soup"


def test_code_block_preferred_when_direct_parse_fails() -> None:
    """If raw text has commentary before the code block, the direct parse
    fails and we fall through to code block extraction."""
    payload = {
        "dish_name": "stir fry",
        "confidence": 0.85,
        "ingredients": [{"name": "broccoli", "visible": True, "confidence": 0.95}],
    }
    raw = f"I analyzed the image. ```json\n{json.dumps(payload)}\n```"
    result = parse_vision_response(raw)
    assert result.dish_name == "stir fry"


# ---------------------------------------------------------------------------
# Path 3: brace extraction from surrounding text
# ---------------------------------------------------------------------------


def test_brace_extraction_from_commentary() -> None:
    payload = {
        "dish_name": "pizza",
        "confidence": 0.95,
        "ingredients": [{"name": "cheese", "visible": True, "confidence": 0.9}],
    }
    raw = (
        f"Sure, here's what I see in the image: {json.dumps(payload)} "
        "Please confirm if this is correct."
    )
    result = parse_vision_response(raw)
    assert result.dish_name == "pizza"


def test_brace_extraction_with_nested_braces_in_ingredients() -> None:
    """The brace regex is greedy — it captures from the first '{' to the
    last '}', which correctly includes the nested ingredient objects."""
    payload = {
        "dish_name": "tacos",
        "confidence": 0.88,
        "ingredients": [
            {"name": "tortilla", "visible": True, "confidence": 0.95},
            {"name": "beef", "visible": True, "confidence": 0.9},
        ],
    }
    raw = f"Analysis result: {json.dumps(payload)}\nDone."
    result = parse_vision_response(raw)
    assert result.dish_name == "tacos"
    assert len(result.ingredients) == 2


# ---------------------------------------------------------------------------
# Path 4: fallback on malformed output
# ---------------------------------------------------------------------------


def test_fallback_on_empty_string() -> None:
    result = parse_vision_response("")
    assert result.dish_name == "parse_error"
    assert result.confidence == 0.0
    assert result.ingredients == []


def test_fallback_on_whitespace_only() -> None:
    result = parse_vision_response("   \n\t  ")
    assert result.dish_name == "parse_error"


def test_fallback_on_plain_text_no_json() -> None:
    result = parse_vision_response("I cannot identify this food, sorry.")
    assert result.dish_name == "parse_error"


def test_fallback_on_malformed_json() -> None:
    # Unbalanced braces, missing quotes — every parse path should fail.
    result = parse_vision_response('{"dish_name": pizza, confidence: 0.5,}')
    assert result.dish_name == "parse_error"


def test_fallback_on_json_missing_required_fields() -> None:
    # Valid JSON but doesn't satisfy VisionResult schema (no ingredients).
    result = parse_vision_response('{"dish_name": "pizza"}')
    assert result.dish_name == "parse_error"


def test_fallback_on_code_block_with_invalid_json() -> None:
    raw = "```json\n{not valid json at all}\n```"
    result = parse_vision_response(raw)
    assert result.dish_name == "parse_error"


def test_fallback_returns_independent_instance() -> None:
    """The fallback constant is shared, but it's immutable enough that
    callers can't mutate it in ways that affect other calls. Confirm
    repeated calls return equivalent results."""
    r1 = parse_vision_response("garbage")
    r2 = parse_vision_response("more garbage")
    assert r1.dish_name == r2.dish_name == "parse_error"
    assert r1.ingredients == r2.ingredients == []


# ---------------------------------------------------------------------------
# Path priority: direct parse wins over later attempts when both could match
# ---------------------------------------------------------------------------


def test_direct_parse_wins_over_code_block() -> None:
    """A clean JSON string should hit attempt 1, not fall through to
    code block extraction (which would fail anyway here)."""
    payload = {
        "dish_name": "first",
        "confidence": 1.0,
        "ingredients": [],
    }
    raw = json.dumps(payload)
    result = parse_vision_response(raw)
    assert result.dish_name == "first"


def test_code_block_wins_over_brace_fallback() -> None:
    """When both a markdown code block AND a stray JSON-like substring
    exist in the text, the code block content is used."""
    real_payload = {"dish_name": "real", "confidence": 1.0, "ingredients": []}
    raw = (
        "Some prelude text mentioning {fake: 'object'}. "
        f"```json\n{json.dumps(real_payload)}\n```"
    )
    result = parse_vision_response(raw)
    assert result.dish_name == "real"


# ---------------------------------------------------------------------------
# VisionResult sanity
# ---------------------------------------------------------------------------


def test_fallback_is_vision_result_instance() -> None:
    result = parse_vision_response("")
    assert isinstance(result, VisionResult)


def test_ingredient_defaults_visible_true() -> None:
    """VisionIngredient.visible defaults to True when omitted from JSON."""
    raw = json.dumps(
        {
            "dish_name": "test",
            "confidence": 1.0,
            "ingredients": [{"name": "salt", "confidence": 1.0}],
        }
    )
    result = parse_vision_response(raw)
    assert result.ingredients[0].visible is True
