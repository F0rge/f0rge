from __future__ import annotations

import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

TrackerKind = Literal["counter", "binary"]


class TrackerCreate(BaseModel):
    name: str
    kind: TrackerKind
    icon: Optional[str] = None
    unit: Optional[str] = None
    position: int = 0


class TrackerUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    unit: Optional[str] = None
    position: Optional[int] = None
    archived: Optional[bool] = None


class TrackerResponse(BaseModel):
    id: int
    name: str
    kind: str
    icon: Optional[str] = None
    unit: Optional[str] = None
    position: int
    archived: bool
    is_seed: bool
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TrackerValueResponse(BaseModel):
    tracker_id: int
    date: datetime.date
    value: int
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TrackerValueUpsert(BaseModel):
    value: int


class OrderRequest(BaseModel):
    order: list[int]
