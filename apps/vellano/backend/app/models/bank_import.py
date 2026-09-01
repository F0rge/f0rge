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

    bank_import: Mapped["BankImport"] = relationship(back_populates="lines")
    matched_payment: Mapped[Optional["Payment"]] = relationship()


from app.models.payment import Payment  # noqa: E402
