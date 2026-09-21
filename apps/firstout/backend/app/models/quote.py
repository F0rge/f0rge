from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class QuoteStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Quote(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "quotes"

    quote_number: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[QuoteStatus] = mapped_column(
        Enum(
            QuoteStatus,
            name="quote_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    subtotal_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_inc_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    customer: Mapped["Customer"] = relationship()
    created_by: Mapped["User"] = relationship()
    lines: Mapped[list["QuoteLine"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("quote_number", name="uq_quotes_quote_number"),
        CheckConstraint(
            "status IN ('draft', 'sent', 'accepted', 'expired', 'cancelled')",
            name="ck_quotes_status",
        ),
    )


class QuoteLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "quote_lines"

    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    quote: Mapped[Quote] = relationship(back_populates="lines")
    sku: Mapped["Sku"] = relationship()

    __table_args__ = (CheckConstraint("qty > 0", name="ck_quote_lines_qty"),)


from app.models.customer import Customer  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.user import User  # noqa: E402
