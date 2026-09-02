from __future__ import annotations

import datetime
import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NiaHealthResponse(BaseModel):
    ok: bool
    llm: bool


class NiaThreadCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=512)


class NiaThreadUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)

    @field_validator("title", mode="after")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped


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


class NiaResumeRequest(BaseModel):
    decision: Literal["accept", "decline", "cancel", "submit_fields"]
    tool_call_id: Optional[str] = None
    fields: Optional[dict[str, Any]] = None


class NiaAuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    thread_id: Optional[uuid.UUID] = None
    tool_name: str
    args: Optional[dict[str, Any]] = None
    decision: str
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    created_at: datetime.datetime


class NiaUsageMeResponse(BaseModel):
    used: int
    cap: int
    remaining: int
    period_start: datetime.datetime


class NiaUsageUserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: Optional[str] = None
    used: int
    cap: int
    override: Optional[int] = None
    remaining: int


class NiaUsageCapUpdate(BaseModel):
    nia_monthly_token_cap: Optional[int] = None
