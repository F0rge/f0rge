from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class PurchaseOrderStatus(str, enum.Enum):
    OPEN = "open"
    ON_WATER = "on_water"
    LANDED = "landed"
    RECEIVED = "received"


class PurchaseOrder(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    proforma_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("proformas.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(
            PurchaseOrderStatus,
            name="purchase_order_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=PurchaseOrderStatus.OPEN,
    )
    fx_to_zar: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    received_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    ordered_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    on_water_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    landed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    supplier: Mapped["Supplier"] = relationship()
    proforma: Mapped[Optional["Proforma"]] = relationship()
    received_location: Mapped[Optional["Location"]] = relationship()
    lines: Mapped[list["PoLine"]] = relationship(back_populates="purchase_order")
    bills: Mapped[list["LandingBill"]] = relationship(back_populates="purchase_order")


class PoLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "po_lines"

    po_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    factory_unit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_cost_zar: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")
    sku: Mapped["Sku"] = relationship()

    __table_args__ = (UniqueConstraint("po_id", "sku_id", name="uq_po_lines_po_sku"),)


class LandingBillKind(str, enum.Enum):
    FACTORY = "factory"
    FREIGHT = "freight"
    CLEARANCE = "clearance"


class LandingBill(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "landing_bills"

    po_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[LandingBillKind] = mapped_column(
        Enum(
            LandingBillKind,
            name="landing_bill_kind",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    pdf_storage_key: Mapped[str] = mapped_column(String, nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="bills")

    __table_args__ = (UniqueConstraint("po_id", "kind", name="uq_landing_bills_po_kind"),)


from app.models.location import Location  # noqa: E402
from app.models.proforma import Proforma  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.supplier import Supplier  # noqa: E402
