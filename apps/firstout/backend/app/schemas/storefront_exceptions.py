from __future__ import annotations

import datetime
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    repair_pending: bool = False
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


LIVE_EXCEPTION_ACTIONS = {
    "aged_hold": "release_expired_hold",
    "stale_sync": "refresh_projection",
    "missing_operational_paid_order": "retry_handoff",
    "unknown_payment": "verify_with_provider",
    "refund_mismatch": "reproject_verified_refund",
    "fulfilment_drift": "resync_fulfillment",
    "capacity_conflict": "acknowledge_capacity",
}


class StorefrontExceptionObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str = Field(min_length=1, max_length=255)
    kind: Literal[
        "aged_hold",
        "stale_sync",
        "missing_operational_paid_order",
        "unknown_payment",
        "refund_mismatch",
        "fulfilment_drift",
        "capacity_conflict",
    ]
    status: Literal["open", "aged", "terminal"]
    explanation: str = Field(min_length=1, max_length=500)
    safe_action: str
    last_error: Optional[str] = Field(default=None, max_length=255)
    provider_verified: bool = False
    blocks_checkout: bool = False
    detected_at: datetime.datetime
    amount_minor: Optional[int] = Field(default=None, gt=0)
    payment_reference: Optional[str] = Field(default=None, max_length=128)

    @field_validator("detected_at")
    @classmethod
    def utc_timestamp(cls, value: datetime.datetime) -> datetime.datetime:
        if value.tzinfo is None:
            raise ValueError("source timestamps require UTC offsets")
        return value.astimezone(datetime.timezone.utc)

    @model_validator(mode="after")
    def supported_action(self) -> StorefrontExceptionObservation:
        if self.safe_action != LIVE_EXCEPTION_ACTIONS[self.kind]:
            raise ValueError("source action does not match its exception kind")
        return self


class StorefrontExceptionObservations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: datetime.datetime
    observations: list[StorefrontExceptionObservation] = Field(max_length=10000)

    @field_validator("observed_at")
    @classmethod
    def utc_timestamp(cls, value: datetime.datetime) -> datetime.datetime:
        if value.tzinfo is None:
            raise ValueError("source timestamps require UTC offsets")
        return value.astimezone(datetime.timezone.utc)

    @model_validator(mode="after")
    def distinct_conditions(self) -> StorefrontExceptionObservations:
        identities = {(row.kind, row.correlation_id) for row in self.observations}
        if len(identities) != len(self.observations):
            raise ValueError("duplicate source condition")
        if any(row.detected_at > self.observed_at for row in self.observations):
            raise ValueError("condition detection follows scan time")
        return self


class StorefrontExceptionScanResponse(BaseModel):
    accepted: bool
    checkout_allowed: bool


class StorefrontExceptionCommandResponse(BaseModel):
    id: uuid.UUID
    correlation_id: str
    kind: str
    action: str
    idempotency_key: str


class StorefrontExceptionCommandList(BaseModel):
    items: list[StorefrontExceptionCommandResponse]


class StorefrontExceptionCommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["repaired", "not_repaired"]
    detail: str = Field(min_length=1, max_length=255)


class StorefrontExceptionCommandResultResponse(BaseModel):
    id: uuid.UUID
    outcome: Literal["repaired", "not_repaired"]
