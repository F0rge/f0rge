"""Structured vision output for marrow_classify_meal.

Kept next to the DAG so the worker never imports Marrow. Gemini/OpenRouter
structured output sometimes emits ingredients as nulls or bare strings.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


def coerce_ingredients(value: Any) -> list[Any]:
    """Drop nulls and coerce strings so VisionResult can validate."""
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    out: list[Any] = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, str):
            name = item.strip()
            if name:
                out.append({"name": name, "visible": True, "confidence": 0.5})
            continue
        if isinstance(item, dict):
            name = item.get("name")
            if not name:
                continue
            out.append(item)
            continue
        out.append(item)
    return out


class VisionIngredient(BaseModel):
    name: str
    visible: bool = True
    confidence: float = 0.5


class VisionResult(BaseModel):
    dish_name: str
    cuisine: str | None = None
    confidence: float
    ingredients: list[VisionIngredient] = Field(default_factory=list)

    @field_validator("ingredients", mode="before")
    @classmethod
    def _drop_null_ingredients(cls, value: Any) -> list[Any]:
        return coerce_ingredients(value)


VisionResult.model_rebuild()
