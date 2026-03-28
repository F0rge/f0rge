from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.photo import PhotoResponse


class EntryCreate(BaseModel):
    date: datetime.date
    overall: int
    bloating: int
    stool_normal: bool
    joint_pain: int
    neuro: int
    sleep_quality: int
    stress: int
    diet_risk: str
    supplements: str
    sick: bool
    notes: Optional[str] = None


class EntryUpdate(BaseModel):
    overall: Optional[int] = None
    bloating: Optional[int] = None
    stool_normal: Optional[bool] = None
    joint_pain: Optional[int] = None
    neuro: Optional[int] = None
    sleep_quality: Optional[int] = None
    stress: Optional[int] = None
    diet_risk: Optional[str] = None
    supplements: Optional[str] = None
    sick: Optional[bool] = None
    notes: Optional[str] = None


class EntryResponse(BaseModel):
    id: int
    date: datetime.date
    overall: int
    bloating: int
    stool_normal: bool
    joint_pain: int
    neuro: int
    sleep_quality: int
    stress: int
    diet_risk: str
    supplements: str
    sick: bool
    notes: Optional[str] = None
    photos: list[PhotoResponse] = []
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
