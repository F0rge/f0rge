from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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


class SalesOrderStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    AWAITING_STOCK = "awaiting_stock"
    INVOICED = "invoiced"
    CANCELLED = "cancelled"


class SalesOrder(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "sales_orders"

    so_number: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quote_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quotes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    hold_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    awaiting_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[SalesOrderStatus] = mapped_column(
        Enum(
            SalesOrderStatus,
            name="sales_order_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    subtotal_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_inc_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    customer: Mapped["Customer"] = relationship()
    quote: Mapped[Optional["Quote"]] = relationship(foreign_keys=[quote_id])
    location: Mapped[Optional["Location"]] = relationship()
    invoice: Mapped[Optional["TaxInvoice"]] = relationship()
    created_by: Mapped[Optional["User"]] = relationship()
    lines: Mapped[list["SalesOrderLine"]] = relationship(
        back_populates="sales_order",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["SalesOrderPayment"]] = relationship(
        back_populates="sales_order",
        cascade="all, delete-orphan",
        order_by="SalesOrderPayment.created_at",
    )

    __table_args__ = (
        UniqueConstraint("so_number", name="uq_sales_orders_so_number"),
        CheckConstraint(
            "status IN ('draft', 'open', 'awaiting_stock', 'invoiced', 'cancelled')",
            name="ck_sales_orders_status",
        ),
    )


class SalesOrderLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "sales_order_lines"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    held_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hold_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    hold_unit_cost_zar: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    sales_order: Mapped[SalesOrder] = relationship(back_populates="lines")
    sku: Mapped["Sku"] = relationship()
    hold_location: Mapped[Optional["Location"]] = relationship(foreign_keys=[hold_location_id])

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_sales_order_lines_qty"),
        CheckConstraint("held_qty >= 0", name="ck_sales_order_lines_held_qty"),
    )


class SalesOrderPayment(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "sales_order_payments"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tender: Mapped[str] = mapped_column(Text, nullable=False)
    paid_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    sales_order: Mapped[SalesOrder] = relationship(back_populates="payments")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_sales_order_payments_amount"),
        CheckConstraint(
            "tender IN ('cash', 'eft')",
            name="ck_sales_order_payments_tender",
        ),
    )


from app.models.customer import Customer  # noqa: E402
from app.models.location import Location  # noqa: E402
from app.models.quote import Quote  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.tax_invoice import TaxInvoice  # noqa: E402
from app.models.user import User  # noqa: E402
