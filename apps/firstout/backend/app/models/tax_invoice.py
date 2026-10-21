from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.settlement import SettlementStatus, settlement_status
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class TaxInvoice(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tax_invoices"

    invoice_number: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    subtotal_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_inc_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    payment_status: Mapped[SettlementStatus] = mapped_column(
        Enum(
            SettlementStatus,
            name="invoice_payment_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=SettlementStatus.UNPAID,
        server_default=SettlementStatus.UNPAID.value,
    )
    prices_include_vat: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    is_archive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    reminders_paused: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    customer: Mapped["Customer"] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.sort_order",
    )
    credit_note: Mapped[Optional["CreditNote"]] = relationship(  # noqa: F821
        "CreditNote",
        back_populates="invoice",
        uselist=False,
    )

    __table_args__ = (UniqueConstraint("invoice_number", name="uq_tax_invoices_invoice_number"),)


class InvoiceLine(UUIDPkMixin, Base):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    inc_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sku_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=True,
    )
    price_warning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    invoice: Mapped[TaxInvoice] = relationship(back_populates="lines")


@event.listens_for(TaxInvoice, "before_insert")
@event.listens_for(TaxInvoice, "before_update")
def _sync_invoice_payment_status(_mapper, _connection, target: TaxInvoice) -> None:
    target.payment_status = settlement_status(target.amount_paid, target.total_inc_vat)


from app.models.customer import Customer  # noqa: E402
