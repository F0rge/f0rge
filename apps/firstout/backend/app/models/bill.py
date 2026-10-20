from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
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
    amount_paid_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    pdf_storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    purchase_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="SET NULL"),
        nullable=True,
    )

    supplier: Mapped["Supplier"] = relationship()
    lines: Mapped[list["BillLine"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillLine.sort_order",
    )

    __table_args__ = (
        UniqueConstraint("bill_number", name="uq_bills_bill_number"),
        Index(
            "uq_bills_supplier_ref_ci",
            "supplier_id",
            text("lower(supplier_ref)"),
            unique=True,
            postgresql_where=text("btrim(supplier_ref) <> ''"),
        ),
    )


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


from app.models.supplier import Supplier  # noqa: E402
