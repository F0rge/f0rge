from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class RepeatingInvoice(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "repeating_invoices"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)
    next_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    customer: Mapped["Customer"] = relationship()
    lines: Mapped[list["RepeatingInvoiceLine"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="RepeatingInvoiceLine.sort_order",
    )

    __table_args__ = (
        CheckConstraint(
            "day_of_month >= 1 AND day_of_month <= 28",
            name="ck_repeating_invoices_day_of_month",
        ),
    )


class RepeatingInvoiceLine(UUIDPkMixin, Base):
    __tablename__ = "repeating_invoice_lines"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repeating_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    schedule: Mapped[RepeatingInvoice] = relationship(back_populates="lines")

    __table_args__ = (CheckConstraint("qty > 0", name="ck_repeating_invoice_lines_qty"),)


from app.models.customer import Customer  # noqa: E402
