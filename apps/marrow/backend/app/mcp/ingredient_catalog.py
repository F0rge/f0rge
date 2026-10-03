from __future__ import annotations

from typing import Any

from app.models.dietary_ingredient import DietaryIngredient
from app.services.diet_flags import HISTAMINE_FLAG_THRESHOLD

FODMAP_AXES = ("oligos", "fructose", "polyols", "lactose")


def catalog_item_flags(item: DietaryIngredient) -> dict[str, Any]:
    """Plain-dict diet flags for one catalogue row (safe to use after the session closes)."""
    fodmap = {axis: getattr(item, f"fodmap_{axis}") for axis in FODMAP_AXES}
    histamine = item.histamine_score
    return {
        "histamine_score": histamine,
        "fodmap": fodmap,
        "contains_gluten": bool(item.contains_gluten),
        "contains_dairy": bool(item.contains_dairy),
        "high_histamine": (histamine or 0) >= HISTAMINE_FLAG_THRESHOLD,
        "high_fodmap": any(value == "high" for value in fodmap.values()),
    }


def catalog_item_payload(item: DietaryIngredient) -> dict[str, Any]:
    aliases = sorted(a.alias for a in item.aliases if a.alias != item.canonical_name)
    return {
        "canonical_name": item.canonical_name,
        "category": item.category,
        "aliases": aliases,
        "flags": catalog_item_flags(item),
    }
