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


NiaScheduleCadence = Literal[
    "weekdays_08",
    "daily_08",
    "weekly_mon_08",
    "hourly",
    "custom",
]
NiaScheduleStatus = Literal["ok", "skipped", "error", "needs_ok"]


class NiaScheduledTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    prompt: str = Field(..., min_length=1, max_length=8000)
    timezone: str = Field(default="Africa/Johannesburg", max_length=64)
    cadence: NiaScheduleCadence = "weekdays_08"
    cron: Optional[str] = Field(default=None, max_length=64)
    enabled: bool = True
    notify_only_if_changed: bool = False

    @field_validator("name", "prompt", "timezone", mode="after")
    @classmethod
    def strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty")
        return stripped


class NiaScheduledTaskUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    prompt: Optional[str] = Field(default=None, min_length=1, max_length=8000)
    timezone: Optional[str] = Field(default=None, max_length=64)
    cadence: Optional[NiaScheduleCadence] = None
    cron: Optional[str] = Field(default=None, max_length=64)
    enabled: Optional[bool] = None
    notify_only_if_changed: Optional[bool] = None

    @field_validator("name", "prompt", "timezone", mode="after")
    @classmethod
    def strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty")
        return stripped


class NiaScheduledTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prompt: str
    timezone: str
    cadence: str
    cron: Optional[str] = None
    enabled: bool
    notify_only_if_changed: bool
    last_run_at: Optional[datetime.datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    next_run_at: Optional[datetime.datetime] = None
    last_thread_id: Optional[uuid.UUID] = None
    created_at: datetime.datetime


class NiaScheduledRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    started_at: datetime.datetime
    finished_at: Optional[datetime.datetime] = None
    status: str
    thread_id: Optional[uuid.UUID] = None
