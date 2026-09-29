from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class OpsCommerceFulfillmentEvent(UUIDPkMixin, TimestampMixin, Base):
    """Durable, acknowledged Storefront status message for one paid order."""

    __tablename__ = "ops_commerce_fulfillment_events"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    handoff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ops_commerce_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    external_order_id: Mapped[str] = mapped_column(String(255), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    fulfillment_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    fulfillment_promise: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    acknowledged_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "handoff_id", "revision", name="uq_ops_commerce_fulfillment_event_revision"
        ),
        CheckConstraint("revision > 0", name="ck_ops_commerce_fulfillment_events_revision"),
        CheckConstraint(
            "fulfillment_type IN ('delivery', 'collection')",
            name="ck_ops_commerce_fulfillment_events_type",
        ),
        CheckConstraint(
            "status IN ('ready_for_delivery', 'out_for_delivery', 'delivered', "
            "'ready_for_collection', 'collected')",
            name="ck_ops_commerce_fulfillment_events_status",
        ),
        Index(
            "ix_ops_commerce_fulfillment_events_pending",
            "company_id",
            "occurred_at",
            postgresql_where="acknowledged_at IS NULL",
        ),
    )
