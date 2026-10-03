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
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class OpsCommerceRefund(UUIDPkMixin, TimestampMixin, Base):
    """A durable Storefront refund command and its verified financial outcome."""

    __tablename__ = "ops_commerce_refunds"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    handoff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ops_commerce_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_orders.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    request_origin: Mapped[str] = mapped_column(String(16), nullable=False, default="staff")
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_amount_minor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    allocation: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    selected_lines: Mapped[dict[str, int]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict
    )
    cancel_order: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="requested")
    provider_outcome: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    provider_refund_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider_result_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sales_order_balance_adjusted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    financial_journal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("handoff_id", "idempotency_key", name="uq_ops_commerce_refund_key"),
        UniqueConstraint("provider_refund_id", name="uq_ops_commerce_refund_provider_id"),
        CheckConstraint("amount_minor > 0", name="ck_ops_commerce_refunds_amount"),
        CheckConstraint(
            "provider_amount_minor IS NULL OR provider_amount_minor > 0",
            name="ck_ops_commerce_refunds_provider_amount",
        ),
        CheckConstraint("currency_code = 'ZAR'", name="ck_ops_commerce_refunds_currency"),
        CheckConstraint(
            "request_origin IN ('staff', 'provider')", name="ck_ops_commerce_refunds_origin"
        ),
        CheckConstraint(
            "status IN ('requested', 'dispatching', 'unknown', 'pending', 'succeeded', 'failed', 'needs_review')",
            name="ck_ops_commerce_refunds_status",
        ),
        CheckConstraint(
            "provider_outcome IS NULL OR provider_outcome IN ('succeeded', 'pending', 'failed', 'unknown')",
            name="ck_ops_commerce_refunds_provider_outcome",
        ),
    )


class OpsCommerceRefundEvent(UUIDPkMixin, TimestampMixin, Base):
    """Append-only, signature-verified Peach refund observation, including out-of-band events."""

    __tablename__ = "ops_commerce_refund_events"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    handoff_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_commerce_orders.id", ondelete="RESTRICT"), nullable=True
    )
    refund_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ops_commerce_refunds.id", ondelete="RESTRICT"),
        nullable=True,
    )
    provider_refund_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_key: Mapped[str] = mapped_column(String(260), nullable=False)
    webhook_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    referenced_capture_id: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    result_code: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    canonical_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    resolution_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    provider_event_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    received_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    financial_journal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("event_key", name="uq_ops_commerce_refund_events_event_key"),
        UniqueConstraint("webhook_id", name="uq_ops_commerce_refund_events_webhook_id"),
        CheckConstraint("amount_minor > 0", name="ck_ops_commerce_refund_events_amount"),
        CheckConstraint("currency_code = 'ZAR'", name="ck_ops_commerce_refund_events_currency"),
        CheckConstraint(
            "outcome IN ('succeeded', 'pending', 'failed', 'unknown', 'needs_review')",
            name="ck_ops_commerce_refund_events_outcome",
        ),
    )
