from __future__ import annotations

import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProposedBackupPolicyResponse(BaseModel):
    status: Literal["proposal"]
    agreed_sla: Literal[False]
    daily_copies: int
    recovery_point_hours: int
    restoration_hours_after_operator_start: int


class StorefrontRecoveryOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restore_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{7,39}$")
    later_payment: bool = False
    later_refund: bool = False


class StorefrontRecoveryReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restore_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{7,39}$")
    effect: Literal["payment", "refund", "order", "operational_posting", "email"]
    idempotency_key: str = Field(min_length=8, max_length=64)
    provider_verified: bool = False
    reason: str = Field(min_length=8, max_length=500)


class StorefrontRecoveryReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restore_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{7,39}$")
    truth: Literal["provider", "order", "stock", "capacity"]
    idempotency_key: str = Field(min_length=8, max_length=64)
    provider_verified: bool = False
    reason: str = Field(min_length=8, max_length=500)


class BackupDatasetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    byte_size: int
    sha256: str = Field(max_length=128)


class StorefrontBackupCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backup_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
    captured_at: datetime.datetime
    credentials_included: bool
    datasets: list[BackupDatasetInput]
    now: Optional[datetime.datetime] = None
    operator_started_at: Optional[datetime.datetime] = None
    operator_finished_at: Optional[datetime.datetime] = None


class StorefrontRecoveryAlertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Literal[
        "stale_stock",
        "aged_paid_handoff",
        "webhook_failure",
        "job_failure",
        "email_failure",
        "spending",
        "backup_missing",
        "backup_corrupt",
        "backup_stale",
    ]
    backup_id: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
    dataset: Optional[str] = Field(default=None, max_length=64)


class StorefrontRecoveryResponse(BaseModel):
    restore_id: str
    correlation_id: str
    checkout_allowed: bool
    checkout: Literal["gated", "open"]
    reason: Optional[str] = None
    paid_recovery_retained: Literal[True] = True
    firstout_dependency: Literal["required"] = "required"
    ops_reachable: bool
    live_restore: Literal[False] = False
    agreed_sla: Literal[False] = False
    truths: dict[str, str]
    effects: dict[str, int]
    proposal: ProposedBackupPolicyResponse


class StorefrontBackupCheckResponse(BaseModel):
    ok: bool
    code: str
    message: Optional[str] = None
    live_restore: Literal[False] = False
    agreed_sla: Literal[False] = False
    proposal: ProposedBackupPolicyResponse
    measured: dict[str, object]
    alert_id: Optional[str] = None
    context: Optional[dict[str, object]] = None
