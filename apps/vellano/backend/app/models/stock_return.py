from __future__ import annotations

import enum
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class StockReturnReason(str, enum.Enum):
    DAMAGED = "damaged"
    UNWANTED = "unwanted"
    WRONG_ITEM = "wrong_item"
    OTHER = "other"


class StockReturnDisposition(str, enum.Enum):
    RESTOCK = "restock"
    WRITE_OFF = "write_off"


class StockReturnStatus(str, enum.Enum):
    DRAFT = "draft"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StockReturn(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "stock_returns"

    return_number: Mapped[str] = mapped_column(Text, nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    credit_note_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("credit_notes.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    reason: Mapped[StockReturnReason] = mapped_column(
        Enum(
            StockReturnReason,
            name="stock_return_reason",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    disposition: Mapped[StockReturnDisposition] = mapped_column(
        Enum(
            StockReturnDisposition,
            name="stock_return_disposition",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    status: Mapped[StockReturnStatus] = mapped_column(
        Enum(
            StockReturnStatus,
            name="stock_return_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    invoice: Mapped["TaxInvoice"] = relationship()
    location: Mapped["Location"] = relationship()
    credit_note: Mapped[Optional["CreditNote"]] = relationship()
    created_by: Mapped["User"] = relationship()
    lines: Mapped[list["StockReturnLine"]] = relationship(back_populates="stock_return")

    __table_args__ = (
        UniqueConstraint("return_number", name="uq_stock_returns_return_number"),
        CheckConstraint(
            "status IN ('draft', 'completed', 'cancelled')",
            name="ck_stock_returns_status",
        ),
        CheckConstraint(
            "reason IN ('damaged', 'unwanted', 'wrong_item', 'other')",
            name="ck_stock_returns_reason",
        ),
        CheckConstraint(
            "disposition IN ('restock', 'write_off')",
            name="ck_stock_returns_disposition",
        ),
    )


class StockReturnLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "stock_return_lines"

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stock_returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoice_lines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sku_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=True,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)

    stock_return: Mapped[StockReturn] = relationship(back_populates="lines")
    invoice_line: Mapped["InvoiceLine"] = relationship()
    sku: Mapped[Optional["Sku"]] = relationship()

    __table_args__ = (CheckConstraint("qty > 0", name="ck_stock_return_lines_qty"),)


from app.models.credit_note import CreditNote  # noqa: E402
from app.models.location import Location  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.tax_invoice import InvoiceLine, TaxInvoice  # noqa: E402
from app.models.user import User  # noqa: E402
