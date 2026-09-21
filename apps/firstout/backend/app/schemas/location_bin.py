from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BinCreate(BaseModel):
    row_code: str = Field(min_length=1, max_length=8)
    bay: int = Field(ge=1)
    level: int = Field(ge=1)


class BinGridCreate(BaseModel):
    rows: list[str] = Field(min_length=1)
    bays: int = Field(ge=1, le=99)
    levels: int = Field(ge=1, le=99)


class BinUpdate(BaseModel):
    is_archived: Optional[bool] = None
    is_default: Optional[bool] = None


class LocationBinResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    code: str
    row_code: str
    bay: int
    level: int
    is_default: bool
    is_archived: bool
    archived_at: Optional[datetime.datetime]

    model_config = ConfigDict(from_attributes=True)


class BinOnHandResponse(BaseModel):
    bin_id: uuid.UUID
    code: str
    on_hand: int
