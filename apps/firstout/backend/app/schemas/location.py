from __future__ import annotations

import datetime
import uuid

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.location import LocationType


class LocationCreate(BaseModel):
    name: str = Field(min_length=1)
    type: LocationType


class LocationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    is_archived: Optional[bool] = None


class LocationResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: LocationType
    is_archived: bool
    archived_at: Optional[datetime.datetime]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
