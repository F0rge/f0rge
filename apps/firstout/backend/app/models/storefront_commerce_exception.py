from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

EXCEPTION_KINDS = (
    "aged_hold",
    "stale_sync",
    "missing_operational_paid_order",
    "unknown_payment",
    "refund_mismatch",
    "fulfilment_drift",
    "capacity_conflict",
)
FINANCIAL_KINDS = frozenset({"unknown_payment", "refund_mismatch"})
EXCEPTION_STATUSES = ("open", "aged", "terminal", "resolved")


class StorefrontCommerceException(UUIDPkMixin, TimestampMixin, Base):
    """Operator-visible commerce exception awaiting a safe, audited repair."""

    __tablename__ = "storefront_commerce_exceptions"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    seed_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(String(500), nullable=False)
    safe_action: Mapped[str] = mapped_column(String(64), nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount_minor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    provider_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocks_checkout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effect_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    repair_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detected_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "seed_key", name="uq_storefront_exception_seed"),
        CheckConstraint(
            "kind IN ('aged_hold', 'stale_sync', 'missing_operational_paid_order', "
            "'unknown_payment', 'refund_mismatch', 'fulfilment_drift', 'capacity_conflict')",
            name="ck_storefront_exceptions_kind",
        ),
        CheckConstraint(
            "status IN ('open', 'aged', 'terminal', 'resolved')",
            name="ck_storefront_exceptions_status",
        ),
        CheckConstraint("repair_count >= 0", name="ck_storefront_exceptions_repair_count"),
        CheckConstraint(
            "amount_minor IS NULL OR amount_minor > 0",
            name="ck_storefront_exceptions_amount",
        ),
    )


class StorefrontExceptionAudit(UUIDPkMixin, TimestampMixin, Base):
    """Append-only repair attempt against a commerce exception."""

    __tablename__ = "storefront_exception_audits"

    exception_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("storefront_commerce_exceptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "exception_id", "idempotency_key", name="uq_storefront_exception_audit_key"
        ),
        CheckConstraint(
            "outcome IN ('repaired', 'already_resolved', 'denied', 'needs_provider')",
            name="ck_storefront_exception_audit_outcome",
        ),
    )


class StorefrontExceptionAlert(UUIDPkMixin, TimestampMixin, Base):
    """Test-route alert delivery with redacted operator context."""

    __tablename__ = "storefront_exception_alerts"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    exception_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("storefront_commerce_exceptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    queue_class: Mapped[str] = mapped_column(String(16), nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "queue_class IN ('aged', 'terminal', 'retrying')",
            name="ck_storefront_exception_alert_class",
        ),
    )
