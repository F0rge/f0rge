"""Structured vision output for marrow_classify_meal.

Kept next to the DAG so the worker never imports Marrow.

Gemini/OpenRouter tool-calling often fills nested object arrays with nulls.
Use string lists here; persist() maps them to Marrow's ingredient objects.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def coerce_name_list(value: Any) -> list[str]:
    """Accept strings, {name: ...} objects, and drop nulls."""
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item).strip()
        if name and name.lower() not in ("none", "null"):
            out.append(name)
    return out


class VisionResult(BaseModel):
    dish_name: str
    cuisine: str | None = None
    confidence: float
    visible_ingredients: list[str] = Field(default_factory=list)
    inferred_ingredients: list[str] = Field(default_factory=list)

    @field_validator("visible_ingredients", "inferred_ingredients", mode="before")
    @classmethod
    def _coerce_names(cls, value: Any) -> list[str]:
        return coerce_name_list(value)

    @model_validator(mode="after")
    def _require_ingredients_when_identified(self) -> VisionResult:
        if (
            self.dish_name.strip().lower() not in ("unknown", "")
            and self.confidence >= 0.3
            and not self.visible_ingredients
            and not self.inferred_ingredients
        ):
            raise ValueError(
                "visible_ingredients or inferred_ingredients required when a dish is identified"
            )
        return self

    def to_marrow_ingredients(self) -> list[dict[str, Any]]:
        visible = [
            {"name": name, "visible": True, "confidence": min(self.confidence, 0.95)}
            for name in self.visible_ingredients
        ]
        inferred = [
            {"name": name, "visible": False, "confidence": min(self.confidence * 0.6, 0.5)}
            for name in self.inferred_ingredients
        ]
        return visible + inferred


VisionResult.model_rebuild()
