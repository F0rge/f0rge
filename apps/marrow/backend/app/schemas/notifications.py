from __future__ import annotations

import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    payload: dict
    read_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    count: int


class MarkReadRequest(BaseModel):
    ids: list[uuid.UUID] = Field(default_factory=list)
    all: bool = False
