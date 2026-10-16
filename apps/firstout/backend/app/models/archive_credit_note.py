from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class ArchiveCreditNote(UUIDPkMixin, TimestampMixin, Base):
    """Historical Cin7 credit note (``CR-*``).

    Kept apart from ``credit_notes`` on purpose: a book credit note needs exactly one
    tax invoice and posts a reversal. Archive credit notes post nothing, move no stock,
    and are never read by VAT201, receivables, or the ledger.
    """

    __tablename__ = "archive_credit_notes"

    document_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    subtotal_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_inc_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="cin7")

    lines: Mapped[list["ArchiveCreditNoteLine"]] = relationship(
        "ArchiveCreditNoteLine",
        back_populates="credit_note",
        cascade="all, delete-orphan",
        order_by="ArchiveCreditNoteLine.sort_order",
    )


class ArchiveCreditNoteLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "archive_credit_note_lines"

    credit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("archive_credit_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skus.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    sku_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    inc_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    credit_note: Mapped[ArchiveCreditNote] = relationship(ArchiveCreditNote, back_populates="lines")
