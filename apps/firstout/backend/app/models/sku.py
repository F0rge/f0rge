from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class Sku(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "skus"

    our_ref: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    our_barcode: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    design: Mapped[str] = mapped_column(String(255), nullable=False)
    fabric: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    preferred_supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    made_to_order_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    made_to_order_lead_time_min_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    made_to_order_lead_time_max_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    made_to_order_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    made_to_order_offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, unique=True
    )
    reorder_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    photo_storage_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    wholesale_ex_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    retail_ex_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    carton_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    storefront_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    __table_args__ = (
        Index(
            "ix_skus_design_fabric_lower",
            text("lower(design)"),
            text("lower(fabric)"),
            unique=True,
        ),
        CheckConstraint("carton_count >= 1", name="ck_skus_carton_count"),
        CheckConstraint(
            "(made_to_order_capacity IS NULL AND made_to_order_lead_time_min_days IS NULL "
            "AND made_to_order_lead_time_max_days IS NULL AND made_to_order_expires_at IS NULL "
            "AND made_to_order_offer_id IS NULL) OR "
            "(made_to_order_capacity >= 0 AND made_to_order_lead_time_min_days >= 1 "
            "AND made_to_order_lead_time_max_days >= made_to_order_lead_time_min_days "
            "AND made_to_order_expires_at IS NOT NULL AND made_to_order_offer_id IS NOT NULL)",
            name="ck_skus_made_to_order_offer_complete",
        ),
    )
