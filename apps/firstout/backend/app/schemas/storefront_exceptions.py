from __future__ import annotations

import datetime
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StorefrontExceptionRepairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=8, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=64)


class StorefrontExceptionAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID
    reason: str
    outcome: str
    detail: Optional[str] = None
    created_at: datetime.datetime


class StorefrontExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    status: str
    age_seconds: int
    correlation_id: str
    explanation: str
    safe_action: str
    last_error: Optional[str] = None
    financial: bool
    amount_minor: Optional[int] = None
    payment_reference: Optional[str] = None
    provider_verified: bool
    blocks_checkout: bool
    can_repair: bool
    detected_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None
    repair_count: int
    audits: list[StorefrontExceptionAuditResponse] = Field(default_factory=list)


class StorefrontExceptionListResponse(BaseModel):
    items: list[StorefrontExceptionResponse]
    checkout_allowed: bool
    paid_recovery_retained: Literal[True] = True


class StorefrontCheckoutSafetyResponse(BaseModel):
    checkout_allowed: bool
    reason: Optional[str] = None
    paid_recovery_retained: Literal[True] = True


class StorefrontExceptionAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    queue_class: str
    context: dict[str, object]
    created_at: datetime.datetime


class StorefrontExceptionAlertListResponse(BaseModel):
    items: list[StorefrontExceptionAlertResponse]


class StorefrontExceptionAlertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exception_id: Optional[uuid.UUID] = None
