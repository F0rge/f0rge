from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class TransferStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class Transfer(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "transfers"

    transfer_number: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TransferStatus] = mapped_column(
        Enum(
            TransferStatus,
            name="transfer_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    from_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    to_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    dispatched_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    dispatched_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    received_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    received_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    received_display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pick_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("picks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    from_location: Mapped["Location"] = relationship(foreign_keys=[from_location_id])
    to_location: Mapped["Location"] = relationship(foreign_keys=[to_location_id])
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])
    dispatched_by: Mapped[Optional["User"]] = relationship(foreign_keys=[dispatched_by_user_id])
    received_by: Mapped[Optional["User"]] = relationship(foreign_keys=[received_by_user_id])
    lines: Mapped[list["TransferLine"]] = relationship(
        back_populates="transfer",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("transfer_number", name="uq_transfers_transfer_number"),
        CheckConstraint(
            "status IN ('draft', 'in_transit', 'received', 'cancelled')",
            name="ck_transfers_status",
        ),
        CheckConstraint(
            "from_location_id != to_location_id",
            name="ck_transfers_distinct_locations",
        ),
    )


class TransferLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "transfer_lines"

    transfer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    qty_dispatched: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_received: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    from_bin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("location_bins.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_bin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("location_bins.id", ondelete="SET NULL"),
        nullable=True,
    )
    unit_cost_zar: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    transfer: Mapped[Transfer] = relationship(back_populates="lines")
    sku: Mapped["Sku"] = relationship()
    from_bin: Mapped[Optional["LocationBin"]] = relationship(foreign_keys=[from_bin_id])
    to_bin: Mapped[Optional["LocationBin"]] = relationship(foreign_keys=[to_bin_id])

    __table_args__ = (
        CheckConstraint("qty_dispatched > 0", name="ck_transfer_lines_qty_dispatched"),
        CheckConstraint(
            "qty_received IS NULL OR qty_received >= 0",
            name="ck_transfer_lines_qty_received",
        ),
    )


from app.models.location import Location  # noqa: E402
from app.models.location_bin import LocationBin  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.user import User  # noqa: E402
