from __future__ import annotations

import enum
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class PickSourceType(str, enum.Enum):
    INVOICE = "invoice"
    LAYBY = "layby"
    TILL = "till"


class PickStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PICKING = "picking"
    STAGED = "staged"
    CANCELLED = "cancelled"


class Pick(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "picks"

    number: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[PickSourceType] = mapped_column(
        Enum(
            PickSourceType,
            name="pick_source_type",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    kit_sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    kit_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PickStatus] = mapped_column(
        Enum(
            PickStatus,
            name="pick_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    staging_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    kit_sku: Mapped["Sku"] = relationship(foreign_keys=[kit_sku_id])
    staging_location: Mapped[Optional["Location"]] = relationship(
        foreign_keys=[staging_location_id]
    )
    customer: Mapped[Optional["Customer"]] = relationship()
    invoice: Mapped[Optional["TaxInvoice"]] = relationship()
    lines: Mapped[list["PickLine"]] = relationship(
        back_populates="pick",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("number", name="uq_picks_number"),
        CheckConstraint("kit_qty > 0", name="ck_picks_kit_qty"),
        CheckConstraint(
            "source_type IN ('invoice', 'layby', 'till')",
            name="ck_picks_source_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'picking', 'staged', 'cancelled')",
            name="ck_picks_status",
        ),
    )


class PickLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "pick_lines"

    pick_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("picks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    qty_needed: Mapped[int] = mapped_column(Integer, nullable=False)

    pick: Mapped[Pick] = relationship(back_populates="lines")
    sku: Mapped["Sku"] = relationship()
    allocations: Mapped[list["PickAllocation"]] = relationship(
        back_populates="pick_line",
        cascade="all, delete-orphan",
    )

    __table_args__ = (CheckConstraint("qty_needed > 0", name="ck_pick_lines_qty_needed"),)


class PickAllocation(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "pick_allocations"

    pick_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pick_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)

    pick_line: Mapped[PickLine] = relationship(back_populates="allocations")
    location: Mapped["Location"] = relationship()

    __table_args__ = (CheckConstraint("qty > 0", name="ck_pick_allocations_qty"),)


from app.models.customer import Customer  # noqa: E402
from app.models.location import Location  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.tax_invoice import TaxInvoice  # noqa: E402
