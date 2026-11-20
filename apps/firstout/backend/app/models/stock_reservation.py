from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import UUIDPkMixin

HOLDER_BASKET = "basket"
HOLDER_HELD_SALE = "held_sale"
HOLDER_INVOICE = "invoice"


class StockReservation(TenantOwnedMixin, UUIDPkMixin, Base):
    """A company-wide claim on units of one SKU, owned by one basket, held sale or invoice.

    Live while ``expires_at`` is NULL or in the future.
    """

    __tablename__ = "stock_reservations"

    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skus.id", ondelete="RESTRICT")
    )
    qty: Mapped[int] = mapped_column(Integer)
    holder_kind: Mapped[str] = mapped_column(String(16))
    holder_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # The showroom that created it, for "Reserved at Kramerville".
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "location_id"],
            ["locations.team_id", "locations.id"],
            name="fk_stock_reservations_showroom_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "holder_kind", "holder_id", "sku_id", name="uq_stock_reservations_holder_sku"
        ),
        CheckConstraint("qty > 0", name="ck_stock_reservations_qty"),
        CheckConstraint(
            "holder_kind IN ('basket', 'held_sale', 'invoice')",
            name="ck_stock_reservations_holder_kind",
        ),
        Index("ix_stock_reservations_sku", "team_id", "sku_id"),
        Index("ix_stock_reservations_holder", "team_id", "holder_kind", "holder_id"),
    )
