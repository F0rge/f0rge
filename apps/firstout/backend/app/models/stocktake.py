from __future__ import annotations

import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class StocktakeStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Stocktake(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "stocktakes"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[StocktakeStatus] = mapped_column(
        Enum(
            StocktakeStatus,
            name="stocktake_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    location: Mapped["Location"] = relationship()
    created_by: Mapped["User"] = relationship()
    lines: Mapped[list["StocktakeLine"]] = relationship(back_populates="stocktake")

    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'cancelled')",
            name="ck_stocktakes_status",
        ),
        Index(
            "uq_stocktakes_location_in_progress",
            "location_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
    )


class StocktakeLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "stocktake_lines"

    stocktake_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stocktakes.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    expected_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    counted_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    stocktake: Mapped["Stocktake"] = relationship(back_populates="lines")
    sku: Mapped["Sku"] = relationship()

    __table_args__ = (
        UniqueConstraint("stocktake_id", "sku_id", name="uq_stocktake_lines_stocktake_sku"),
    )


from app.models.location import Location  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.user import User  # noqa: E402
