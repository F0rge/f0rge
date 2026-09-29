from __future__ import annotations

import uuid
import datetime
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class OpsCommerceOrder(UUIDPkMixin, TimestampMixin, Base):
    """Immutable accepted Storefront order and gateway snapshot with mutable delivery status."""

    __tablename__ = "ops_commerce_orders"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    external_order_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    gateway_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    gateway_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    captured_amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    failure_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fulfillment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="confirmed", server_default=text("'confirmed'")
    )
    fulfillment_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_attempt_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    imported_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_orders.id", ondelete="RESTRICT"), nullable=False
    )
    payment_journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "channel", "external_order_id", name="uq_ops_commerce_order_identity"
        ),
        UniqueConstraint(
            "company_id", "channel", "external_payment_id", name="uq_ops_commerce_payment_identity"
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'stock_conflict', 'imported', 'failed')",
            name="ck_ops_commerce_orders_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_ops_commerce_orders_attempt_count"),
        CheckConstraint(
            "fulfillment_status IN ('confirmed', 'ready_for_delivery', 'out_for_delivery', "
            "'delivered', 'ready_for_collection', 'collected')",
            name="ck_ops_commerce_orders_fulfillment_status",
        ),
        CheckConstraint(
            "fulfillment_revision >= 0", name="ck_ops_commerce_orders_fulfillment_revision"
        ),
        CheckConstraint("captured_amount_minor > 0", name="ck_ops_commerce_orders_captured_amount"),
    )
