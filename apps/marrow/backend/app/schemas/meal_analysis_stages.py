from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.vision_prompt import VisionResult


class StagePhotoRef(BaseModel):
    photo_id: int
    user_id: uuid.UUID


class ExtractResponse(BaseModel):
    analysis_id: int
    photo_id: int
    user_id: uuid.UUID
    raw_content: str
    vision: VisionResult
    skipped: bool = False
    skip_reason: Optional[str] = None


class EnrichRequest(BaseModel):
    user_id: uuid.UUID
    vision: VisionResult


class IngredientPayload(BaseModel):
    name: str
    canonical_name: Optional[str] = None
    visible: bool = True
    confidence: float
    histamine_score: Optional[int] = None
    fodmap_oligos: Optional[str] = None
    fodmap_fructose: Optional[str] = None
    fodmap_polyols: Optional[str] = None
    fodmap_lactose: Optional[str] = None
    contains_gluten: Optional[bool] = None
    contains_dairy: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class EnrichResponse(BaseModel):
    ingredients: list[IngredientPayload]


class GateRequest(BaseModel):
    vision: VisionResult


class GateResponse(BaseModel):
    status: str


class PersistRequest(BaseModel):
    user_id: uuid.UUID
    analysis_id: int
    photo_id: int
    raw_content: str
    vision: VisionResult
    ingredients: list[IngredientPayload]
    status: str


class PersistResponse(BaseModel):
    status: str
    analysis_id: int


class FailRequest(BaseModel):
    user_id: uuid.UUID
    analysis_id: int
    error_message: str = Field(max_length=500)


class FailResponse(BaseModel):
    status: str = "failed"


class TriggerResult(BaseModel):
    dag_run_id: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None
    inline: bool = False
