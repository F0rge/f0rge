from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class BankImport(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "bank_imports"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    account: Mapped["Account"] = relationship(lazy="selectin")
    lines: Mapped[list["BankImportLine"]] = relationship(
        back_populates="bank_import",
        cascade="all, delete-orphan",
        order_by="BankImportLine.transaction_date",
    )


class BankImportLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "bank_import_lines"

    import_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bank_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    amount_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    matched_payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    matched_journal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    bank_import: Mapped["BankImport"] = relationship(back_populates="lines")
    matched_payment: Mapped[Optional["Payment"]] = relationship()
    matched_journal: Mapped[Optional["JournalEntry"]] = relationship()
    allocations: Mapped[list["BankImportLineAllocation"]] = relationship(
        back_populates="line",
        cascade="all, delete-orphan",
    )


class BankImportLineAllocation(UUIDPkMixin, TimestampMixin, Base):
    """One bank line can pay several invoices or bills. The first payment is also
    stored on the line so existing matched checks keep working.
    """

    __tablename__ = "bank_import_line_allocations"

    line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bank_import_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    document_number: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    line: Mapped[BankImportLine] = relationship(back_populates="allocations")
    payment: Mapped["Payment"] = relationship()


from app.models.account import Account  # noqa: E402
from app.models.journal import JournalEntry  # noqa: E402
from app.models.payment import Payment  # noqa: E402
