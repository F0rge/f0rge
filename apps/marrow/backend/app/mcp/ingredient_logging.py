"""Shared ingredient-row building + per-ingredient status payloads for log_meal / set_ingredients."""

from __future__ import annotations

from typing import Any, Sequence

from f0rge_core.exceptions import ValidationError

from app.mcp.ingredient_catalog import catalog_item_flags
from app.mcp.tools._common import _ingredient_to_dict
from app.models.photo_ingredient import PhotoIngredient
from app.services.ingredient_resolver import (
    APPROXIMATE,
    COMPOSITE_HINT,
    MAX_INGREDIENTS_PER_CALL,
    UNMATCHED,
    IngredientResolver,
    Resolution,
    dedupe_names,
)


def prepare_ingredient_names(ingredients: Sequence[str]) -> tuple[list[str], list[str]]:
    """Strip/dedupe names and enforce the per-call cap. Returns (names, duplicates_dropped)."""
    names, dropped = dedupe_names(ingredients)
    if len(names) > MAX_INGREDIENTS_PER_CALL:
        raise ValidationError(
            f"At most {MAX_INGREDIENTS_PER_CALL} ingredients per meal; got {len(names)}. "
            "Keep the main ingredients that matter for gluten, dairy, FODMAP or histamine."
        )
    return names, dropped


def build_ingredient_row(
    resolution: Resolution, *, user_id: Any, analysis_id: int
) -> PhotoIngredient:
    """Build a PhotoIngredient. Flags are copied only for exact/alias/normalised matches."""
    entry = resolution.entry
    return PhotoIngredient(
        user_id=user_id,
        analysis_id=analysis_id,
        name=resolution.input_name,
        canonical_name=entry.canonical_name if entry else None,
        visible=True,
        confidence=1.0,
        user_edited=True,
        histamine_score=entry.histamine_score if entry else None,
        fodmap_oligos=entry.fodmap_oligos if entry else None,
        fodmap_fructose=entry.fodmap_fructose if entry else None,
        fodmap_polyols=entry.fodmap_polyols if entry else None,
        fodmap_lactose=entry.fodmap_lactose if entry else None,
        contains_gluten=entry.contains_gluten if entry else None,
        contains_dairy=entry.contains_dairy if entry else None,
    )


def stage_ingredient_rows(
    db_add: Any, resolutions: Sequence[Resolution], *, user_id: Any, analysis_id: int
) -> list[PhotoIngredient]:
    rows = [build_ingredient_row(r, user_id=user_id, analysis_id=analysis_id) for r in resolutions]
    for row in rows:
        db_add(row)
    return rows


def _match_payload(resolution: Resolution) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": resolution.status,
        "matched_alias": resolution.matched_alias,
        "flags_attached": resolution.attaches_flags,
        "suggestions": resolution.suggestions,
    }
    if resolution.status == APPROXIMATE:
        payload["hint"] = (
            "Close to a catalogue entry but not the same ingredient, so no catalogue flags were "
            "attached. If it is the same thing, resend it with the exact canonical_name from "
            "suggestions; if it is a product, split it into constituent ingredients."
        )
    elif resolution.status == UNMATCHED:
        payload["hint"] = (
            "No catalogue entry matches, so this is stored without FODMAP/histamine/gluten/dairy "
            "flags. Call search_ingredients for a canonical name, or decompose it."
        )
    if resolution.composite_suspected:
        payload["composite_suspected"] = True
        payload["composite_hint"] = COMPOSITE_HINT
    return payload


def ingredient_payload(row: PhotoIngredient, resolution: Resolution) -> dict[str, Any]:
    payload = _ingredient_to_dict(row)
    payload["flags"] = catalog_item_flags(resolution.entry) if resolution.entry else None
    payload["match"] = _match_payload(resolution)
    return payload


def next_step(resolutions: Sequence[Resolution], *, tool: str) -> str:
    unmatched = [r for r in resolutions if r.status == UNMATCHED]
    approximate = [r for r in resolutions if r.status == APPROXIMATE]
    if not resolutions:
        return "No ingredients were stored. Pass the meal's decomposed ingredient list."
    if not unmatched and not approximate:
        return f"All {len(resolutions)} ingredient(s) matched the catalogue and carry their flags."
    parts: list[str] = []
    if approximate:
        parts.append(
            f"{len(approximate)} ingredient(s) only approximately match (stored without flags): "
            "resend with the exact canonical_name from match.suggestions"
        )
    if unmatched:
        parts.append(
            f"{len(unmatched)} ingredient(s) have no catalogue match (stored without flags): "
            "call search_ingredients, and split any composite product into its constituents"
        )
    again = (
        "call set_ingredients with this photo_id and the corrected list"
        if tool == "log_meal"
        else "call set_ingredients again with the corrected list"
    )
    return "; ".join(parts) + f". Then {again}."


def summary_fields(resolutions: Sequence[Resolution], dropped: Sequence[str]) -> dict[str, Any]:
    return {
        "ingredient_count": len(resolutions),
        "matched_count": sum(1 for r in resolutions if r.attaches_flags),
        "unmatched": [r.input_name for r in resolutions if r.status == UNMATCHED],
        "approximate": [r.input_name for r in resolutions if r.status == APPROXIMATE],
        "composite_suspected": [r.input_name for r in resolutions if r.composite_suspected],
        "duplicates_dropped": list(dropped),
    }


async def resolve_for_current_user(db: Any, ingredients: Sequence[str]):
    names, dropped = prepare_ingredient_names(ingredients)
    resolver = await IngredientResolver.for_current_user(db)
    return resolver.resolve_many(names), dropped
