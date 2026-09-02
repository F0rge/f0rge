from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class NiaHealthResponse(BaseModel):
    ok: bool
    llm: bool


class NiaThreadCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=512)


class NiaMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    structured_payload: Optional[dict[str, Any]] = None
    created_at: datetime.datetime


class NiaThreadSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    archived_at: Optional[datetime.datetime] = None


class NiaThreadResponse(NiaThreadSummaryResponse):
    messages: list[NiaMessageResponse]
