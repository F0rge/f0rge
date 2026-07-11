from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

DIETARY_INGREDIENT_CATEGORIES = {
    "beverages",
    "condiments",
    "dairy",
    "eggs",
    "fermented",
    "fish",
    "fruit",
    "grains",
    "legumes",
    "meat",
    "nuts_seeds",
    "oils_fats",
    "seafood",
    "spices",
    "sweets",
    "vegetables",
}

FODMAP_LEVELS = {"low", "moderate", "high"}


def _validate_category(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in DIETARY_INGREDIENT_CATEGORIES:
        raise ValueError(f"category must be one of {sorted(DIETARY_INGREDIENT_CATEGORIES)} or null")
    return value


def _validate_fodmap_level(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in FODMAP_LEVELS:
        raise ValueError(f"fodmap level must be one of {sorted(FODMAP_LEVELS)} or null")
    return value


class AliasResponse(BaseModel):
    id: int
    alias: str
    canonical_name: str
    language: str

    model_config = ConfigDict(from_attributes=True)


class AliasCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=200)
    language: str = Field(default="en", min_length=2, max_length=8)


class DietaryIngredientResponse(BaseModel):
    id: int
    canonical_name: str
    category: Optional[str] = None
    histamine_score: Optional[int] = None
    fodmap_oligos: Optional[str] = None
    fodmap_fructose: Optional[str] = None
    fodmap_polyols: Optional[str] = None
    fodmap_lactose: Optional[str] = None
    contains_gluten: bool
    contains_dairy: bool
    source: Optional[str] = None
    source_version: Optional[str] = None
    archived: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    aliases: list[AliasResponse] = []

    model_config = ConfigDict(from_attributes=True)


class DietaryIngredientCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=200)
    category: Optional[str] = None
    histamine_score: Optional[int] = Field(default=None, ge=0, le=3)
    fodmap_oligos: Optional[str] = None
    fodmap_fructose: Optional[str] = None
    fodmap_polyols: Optional[str] = None
    fodmap_lactose: Optional[str] = None
    contains_gluten: bool = False
    contains_dairy: bool = False
    source: Optional[str] = Field(default="user", max_length=64)
    source_version: Optional[str] = Field(default=None, max_length=64)

    _validate_category = field_validator("category")(_validate_category)
    _validate_fodmap = field_validator(
        "fodmap_oligos", "fodmap_fructose", "fodmap_polyols", "fodmap_lactose"
    )(_validate_fodmap_level)


class DietaryIngredientUpdate(BaseModel):
    # canonical_name is intentionally NOT updatable here: ingredient_aliases.canonical_name
    # is a plain FK to this column with no ON UPDATE CASCADE (see migrations/versions/001_baseline.py),
    # so a rename would orphan any existing aliases against a Postgres FK violation.
    category: Optional[str] = None
    histamine_score: Optional[int] = Field(default=None, ge=0, le=3)
    fodmap_oligos: Optional[str] = None
    fodmap_fructose: Optional[str] = None
    fodmap_polyols: Optional[str] = None
    fodmap_lactose: Optional[str] = None
    contains_gluten: Optional[bool] = None
    contains_dairy: Optional[bool] = None
    source: Optional[str] = Field(default=None, max_length=64)
    source_version: Optional[str] = Field(default=None, max_length=64)
    archived: Optional[bool] = None

    _validate_category = field_validator("category")(_validate_category)
    _validate_fodmap = field_validator(
        "fodmap_oligos", "fodmap_fructose", "fodmap_polyols", "fodmap_lactose"
    )(_validate_fodmap_level)
