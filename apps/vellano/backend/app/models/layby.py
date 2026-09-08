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


class LaybyStatus(str, enum.Enum):
    OPEN = "open"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Layby(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "laybys"

    layby_number: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    hold_stock: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[LaybyStatus] = mapped_column(
        Enum(
            LaybyStatus,
            name="layby_status",
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
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    customer: Mapped["Customer"] = relationship()
    location: Mapped["Location"] = relationship()
    invoice: Mapped[Optional["TaxInvoice"]] = relationship()
    created_by: Mapped["User"] = relationship()
    lines: Mapped[list["LaybyLine"]] = relationship(
        back_populates="layby",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["LaybyPayment"]] = relationship(
        back_populates="layby",
        cascade="all, delete-orphan",
        order_by="LaybyPayment.created_at",
    )

    __table_args__ = (
        UniqueConstraint("layby_number", name="uq_laybys_layby_number"),
        CheckConstraint(
            "status IN ('open', 'ready', 'completed', 'cancelled')",
            name="ck_laybys_status",
        ),
    )


class LaybyLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "layby_lines"

    layby_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("laybys.id", ondelete="CASCADE"),
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

    layby: Mapped[Layby] = relationship(back_populates="lines")
    sku: Mapped["Sku"] = relationship()

    __table_args__ = (CheckConstraint("qty > 0", name="ck_layby_lines_qty"),)


class LaybyPayment(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "layby_payments"

    layby_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("laybys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tender: Mapped[str] = mapped_column(Text, nullable=False)
    paid_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    layby: Mapped[Layby] = relationship(back_populates="payments")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_layby_payments_amount"),
        CheckConstraint(
            "tender IN ('cash', 'card')",
            name="ck_layby_payments_tender",
        ),
    )


from app.models.customer import Customer  # noqa: E402
from app.models.location import Location  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.tax_invoice import TaxInvoice  # noqa: E402
from app.models.user import User  # noqa: E402
