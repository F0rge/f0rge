from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import UUIDPkMixin


class TillBasket(TenantOwnedMixin, UUIDPkMixin, Base):
    """A cashier's one open basket per showroom, kept off the browser."""

    __tablename__ = "till_baskets"

    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    note: Mapped[Optional[str]] = mapped_column(String(500))
    # The sale's invoice notes, kept with the cart until the sale is completed.
    note_printed: Mapped[Optional[str]] = mapped_column(Text)
    note_internal: Mapped[Optional[str]] = mapped_column(Text)
    # The sales colleague, checked when the sale is completed.
    sales_staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    pick_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    linked_pick_ids: Mapped[dict[str, str]] = mapped_column(JSONB)
    lines: Mapped[list[dict]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    last_operation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    # Set while the basket has lines; the clock restarts on every change.
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    # When the basket was last emptied by expiry, so the till can say so.
    expired_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "location_id"],
            ["locations.team_id", "locations.id"],
            name="fk_till_baskets_showroom_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("location_id", "user_id", name="uq_till_baskets_user_showroom"),
        CheckConstraint("version >= 1", name="ck_till_baskets_version"),
    )
