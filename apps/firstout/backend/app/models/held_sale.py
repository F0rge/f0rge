from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import UUIDPkMixin


class HeldSale(TenantOwnedMixin, UUIDPkMixin, Base):
    __tablename__ = "held_sales"

    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    customer_name: Mapped[str] = mapped_column(String(255))
    held_by_name: Mapped[str] = mapped_column(String(255))
    held_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    # Hold time after being held; the reservations expire with it.
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now() + interval '3 hours'")
    )
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    note: Mapped[Optional[str]] = mapped_column(String(500))
    # The sale's invoice notes, kept with the cart until the sale is completed.
    note_printed: Mapped[Optional[str]] = mapped_column(Text)
    note_internal: Mapped[Optional[str]] = mapped_column(Text)
    # The sales colleague, checked when the sale is completed.
    sales_staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    estimated_total_inc_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 2))
    pick_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    # Selections and display snapshots survive later catalogue/customer changes.
    linked_pick_ids: Mapped[dict[str, str]] = mapped_column(JSONB)
    lines: Mapped[list[dict]] = mapped_column(JSONB)

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "location_id"],
            ["locations.team_id", "locations.id"],
            name="fk_held_sales_showroom_tenant",
            ondelete="RESTRICT",
        ),
        Index("ix_held_sales_showroom_held_at", "team_id", "location_id", "held_at"),
        CheckConstraint("version >= 1", name="ck_held_sales_version"),
    )
