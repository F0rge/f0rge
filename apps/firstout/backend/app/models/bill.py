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
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.settlement import SettlementStatus, bill_settlement_status
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class Bill(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "bills"

    bill_number: Mapped[str] = mapped_column(String(128), nullable=False)
    is_archive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    fx_to_zar: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    amount_foreign: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # False when the bill is in a foreign currency and no ZAR rate is known (Cin7 history).
    # Then ``fx_to_zar`` and ``amount_zar`` are 0 placeholders; ``currency`` and
    # ``amount_foreign`` hold the original amount. APIs return ZAR as null.
    fx_rate_known: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    amount_paid_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    amount_paid_foreign: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    payment_status: Mapped[SettlementStatus] = mapped_column(
        Enum(
            SettlementStatus,
            name="bill_payment_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=SettlementStatus.UNPAID,
        server_default=SettlementStatus.UNPAID.value,
    )
    pdf_storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    supplier: Mapped["Supplier"] = relationship()
    lines: Mapped[list["BillLine"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillLine.sort_order",
    )

    __table_args__ = (UniqueConstraint("bill_number", name="uq_bills_bill_number"),)


class BillLine(UUIDPkMixin, Base):
    __tablename__ = "bill_lines"

    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_foreign: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    bill: Mapped[Bill] = relationship(back_populates="lines")


@event.listens_for(Bill, "before_insert")
@event.listens_for(Bill, "before_update")
def _sync_bill_payment_status(_mapper, _connection, target: Bill) -> None:
    target.payment_status = bill_settlement_status(
        target.amount_paid_foreign or Decimal(0),
        target.amount_foreign,
        target.amount_paid_zar or Decimal(0),
        target.amount_zar,
    )


from app.models.supplier import Supplier  # noqa: E402
