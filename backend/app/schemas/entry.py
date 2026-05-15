from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.photo import PhotoResponse


class EntryCreate(BaseModel):
    date: datetime.date
    schema_version: Optional[int] = 2
    entry_time: Optional[datetime.datetime] = None
    period_of_day: Optional[str] = None
    overall: int
    bloating: int
    # v1 fields (optional; v2 clients should send stool_status / bristol_type)
    stool_normal: Optional[bool] = None
    stool_type: Optional[str] = None
    stool_status: Optional[str] = Field(
        default=None,
        description="v2: 'normal' | 'abnormal' | 'none'",
    )
    bristol_type: Optional[int] = Field(default=None, ge=1, le=7)
    joint_pain: int
    neuro: int
    sleep_quality: int
    stress: int
    diet_risk: str
    supplements: str
    sick: bool
    hot_shower: Optional[bool] = False
    alcohol_units: Optional[int] = Field(default=None, ge=0, le=10)
    caffeine_servings: Optional[int] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = None


class EntryUpdate(BaseModel):
    schema_version: Optional[int] = None
    entry_time: Optional[datetime.datetime] = None
    period_of_day: Optional[str] = None
    overall: Optional[int] = None
    bloating: Optional[int] = None
    stool_normal: Optional[bool] = None
    stool_type: Optional[str] = None
    stool_status: Optional[str] = None
    bristol_type: Optional[int] = Field(default=None, ge=1, le=7)
    joint_pain: Optional[int] = None
    neuro: Optional[int] = None
    sleep_quality: Optional[int] = None
    stress: Optional[int] = None
    diet_risk: Optional[str] = None
    supplements: Optional[str] = None
    sick: Optional[bool] = None
    hot_shower: Optional[bool] = None
    alcohol_units: Optional[int] = Field(default=None, ge=0, le=10)
    caffeine_servings: Optional[int] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = None


class EntryResponse(BaseModel):
    id: int
    date: datetime.date
    schema_version: int
    entry_time: Optional[datetime.datetime] = None
    period_of_day: Optional[str] = None
    overall: int
    bloating: int
    stool_normal: Optional[bool] = None
    stool_type: Optional[str] = None
    stool_status: Optional[str] = None
    bristol_type: Optional[int] = None
    joint_pain: int
    neuro: int
    sleep_quality: int
    stress: int
    diet_risk: str
    supplements: str
    sick: bool
    hot_shower: bool = False
    alcohol_units: Optional[int] = None
    caffeine_servings: Optional[int] = None
    notes: Optional[str] = None
    photos: list[PhotoResponse] = []
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
