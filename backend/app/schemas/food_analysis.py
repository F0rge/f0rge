from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class IngredientResponse(BaseModel):
    id: int
    name: str
    canonical_name: Optional[str] = None
    visible: bool
    confidence: float
    user_edited: bool
    histamine_score: Optional[int] = None
    fodmap_oligos: Optional[str] = None
    fodmap_fructose: Optional[str] = None
    fodmap_polyols: Optional[str] = None
    fodmap_lactose: Optional[str] = None
    contains_gluten: Optional[bool] = None
    contains_dairy: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class PhotoAnalysisResponse(BaseModel):
    id: int
    photo_id: int
    status: str
    dish_name: Optional[str] = None
    cuisine: Optional[str] = None
    dish_confidence: Optional[float] = None
    ingredients: list[IngredientResponse] = []
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class IngredientCreate(BaseModel):
    name: str
    canonical_name: Optional[str] = None
    visible: bool = True
    confidence: float = 1.0


class IngredientUpdate(BaseModel):
    name: Optional[str] = None
    canonical_name: Optional[str] = None
    histamine_score: Optional[int] = None
    fodmap_oligos: Optional[str] = None
    fodmap_fructose: Optional[str] = None
    fodmap_polyols: Optional[str] = None
    fodmap_lactose: Optional[str] = None
    contains_gluten: Optional[bool] = None
    contains_dairy: Optional[bool] = None
