from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import UUIDPkMixin


class JournalDocumentType(str, enum.Enum):
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    BILL = "bill"
    PAYMENT = "payment"
    STOCK_ADJUSTMENT = "stock_adjustment"
    MANUAL = "manual"


class JournalStatus(str, enum.Enum):
    DRAFT = "draft"
    POSTED = "posted"
    VOIDED = "voided"


class JournalEntry(UUIDPkMixin, Base):
    __tablename__ = "journal_entries"

    document_type: Mapped[JournalDocumentType] = mapped_column(
        Enum(
            JournalDocumentType,
            name="journal_document_type",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    memo: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[JournalStatus] = mapped_column(
        Enum(
            JournalStatus,
            name="journal_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=JournalStatus.POSTED,
        server_default="posted",
    )
    entry_date: Mapped[datetime.date] = mapped_column(
        Date,
        nullable=False,
        default=datetime.date.today,
    )
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    journal_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    voided_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="JournalLine.entry_id",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'posted', 'voided')",
            name="ck_journal_entries_status",
        ),
        UniqueConstraint("journal_number", name="uq_journal_entries_journal_number"),
    )


class JournalLine(UUIDPkMixin, Base):
    __tablename__ = "journal_lines"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    debit_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    credit_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    entry: Mapped[JournalEntry] = relationship(
        back_populates="lines",
        foreign_keys=[entry_id],
    )
    account: Mapped["Account"] = relationship(lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "(debit_zar > 0 AND credit_zar = 0) OR (credit_zar > 0 AND debit_zar = 0)",
            name="ck_journal_lines_debit_or_credit",
        ),
    )


from app.models.account import Account  # noqa: E402
