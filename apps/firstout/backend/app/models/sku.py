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
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class Sku(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "skus"

    our_ref: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    our_barcode: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    design: Mapped[str] = mapped_column(String(255), nullable=False)
    fabric: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
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
    gallery_photo_keys: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    setting_photo_storage_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    detail_photo_storage_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    second_detail_photo_storage_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Finish colour as lowercase #rrggbb, shown as a dot on storefront product cards.
    swatch_hex: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    width_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    depth_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    height_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    diameter_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    piece_count: Mapped[Optional[int]] = mapped_column(Integer)
    storefront_catalogue_selected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    stockist_ex_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    wholesale_ex_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    decorator_ex_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    retail_ex_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    carton_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    is_sellable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    till_no_stock_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # Delivery, installation and similar lines earn no sales commission.
    exclude_from_commission: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    storefront_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    storefront_hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    archived_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        Index("ix_skus_team_id_is_archived", "team_id", "is_archived"),
        Index(
            "ix_skus_design_fabric_lower",
            text("lower(design)"),
            text("lower(fabric)"),
            unique=True,
        ),
        CheckConstraint("carton_count >= 1", name="ck_skus_carton_count"),
        CheckConstraint(
            "width_cm > 0 AND depth_cm > 0 AND height_cm > 0 AND diameter_cm > 0",
            name="ck_skus_positive_dimensions",
        ),
        CheckConstraint("piece_count >= 1", name="ck_skus_positive_piece_count"),
        CheckConstraint(
            "swatch_hex IS NULL OR swatch_hex ~ '^#[0-9a-f]{6}$'", name="ck_skus_swatch_hex"
        ),
        CheckConstraint(
            "cardinality(gallery_photo_keys) = 3 AND array_position(gallery_photo_keys, NULL) IS NULL",
            name="ck_skus_three_gallery_photos",
        ),
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
