from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class PaymentDirection(str, enum.Enum):
    IN = "in"
    OUT = "out"


class Payment(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    payment_number: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[PaymentDirection] = mapped_column(
        Enum(
            PaymentDirection,
            name="payment_direction",
            native_enum=False,
            length=8,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    bill_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bills.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    fx_to_zar: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False, default=1)
    amount_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fx_gain_loss_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    paid_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_reconciled: Mapped[bool] = mapped_column(nullable=False, default=False)
    reconciled_at: Mapped[Optional[datetime.datetime]] = mapped_column(nullable=True)

    invoice: Mapped[Optional["TaxInvoice"]] = relationship()
    bill: Mapped[Optional["Bill"]] = relationship()

    __table_args__ = (
        UniqueConstraint("payment_number", name="uq_payments_payment_number"),
        CheckConstraint(
            "(direction = 'in' AND invoice_id IS NOT NULL AND bill_id IS NULL) OR "
            "(direction = 'out' AND bill_id IS NOT NULL AND invoice_id IS NULL)",
            name="ck_payments_direction_target",
        ),
    )


from app.models.bill import Bill  # noqa: E402
from app.models.tax_invoice import TaxInvoice  # noqa: E402
