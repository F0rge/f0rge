from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MealAnalysisResolveRequest(BaseModel):
    photo_id: int
    user_id: str


class MealAnalysisResolveResponse(BaseModel):
    analysis_id: int
    file_path: str
    catalog_context: str = ""
    content_type: str = "image/jpeg"


class VisionIngredientIn(BaseModel):
    name: str
    visible: bool = True
    confidence: float


class MealAnalysisCompleteRequest(BaseModel):
    user_id: str
    dish_name: str
    cuisine: Optional[str] = None
    confidence: float
    ingredients: list[VisionIngredientIn] = Field(default_factory=list)


class MealAnalysisFailRequest(BaseModel):
    user_id: Optional[str] = None
    error_message: str


class MealAnalysisEnqueueResponse(BaseModel):
    dag_run_id: Optional[str] = None
    via_airflow: bool
    analysis_id: Optional[int] = None
