from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class CreditNote(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "credit_notes"

    credit_note_number: Mapped[str] = mapped_column(String(32), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    subtotal_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_inc_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    invoice: Mapped["TaxInvoice"] = relationship("TaxInvoice", back_populates="credit_note")

    __table_args__ = (
        UniqueConstraint("credit_note_number", name="uq_credit_notes_credit_note_number"),
    )
