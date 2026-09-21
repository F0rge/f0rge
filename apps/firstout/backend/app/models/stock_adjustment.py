from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class StockAdjustmentReason(str, enum.Enum):
    OPENING = "opening"
    DAMAGE = "damage"
    THEFT = "theft"
    COUNT_FIX = "count_fix"
    WRITE_OFF = "write_off"


class StockAdjustmentStatus(str, enum.Enum):
    DRAFT = "draft"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StockAdjustment(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "stock_adjustments"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reason: Mapped[StockAdjustmentReason] = mapped_column(
        Enum(
            StockAdjustmentReason,
            name="stock_adjustment_reason",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[StockAdjustmentStatus] = mapped_column(
        Enum(
            StockAdjustmentStatus,
            name="stock_adjustment_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    location: Mapped["Location"] = relationship()
    created_by: Mapped["User"] = relationship()
    lines: Mapped[list["StockAdjustmentLine"]] = relationship(back_populates="adjustment")

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'completed', 'cancelled')",
            name="ck_stock_adjustments_status",
        ),
        CheckConstraint(
            "reason IN ('opening', 'damage', 'theft', 'count_fix', 'write_off')",
            name="ck_stock_adjustments_reason",
        ),
    )


class StockAdjustmentLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "stock_adjustment_lines"

    adjustment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stock_adjustments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    qty_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_zar: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    adjustment: Mapped["StockAdjustment"] = relationship(back_populates="lines")
    sku: Mapped["Sku"] = relationship()

    __table_args__ = (
        CheckConstraint("qty_delta != 0", name="ck_stock_adjustment_lines_qty_delta"),
    )


from app.models.location import Location  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.user import User  # noqa: E402
