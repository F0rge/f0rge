from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

DEFAULT_BIN_CODE = "FLOOR"
DEFAULT_ROW_CODE = "F"
DEFAULT_BAY = 1
DEFAULT_LEVEL = 1


def grid_bin_code(row_code: str, bay: int, level: int) -> str:
    return f"{row_code}-{bay:02d}-{level}"


class LocationBin(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "location_bins"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    row_code: Mapped[str] = mapped_column(String(8), nullable=False)
    bay: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    location: Mapped["Location"] = relationship()

    __table_args__ = (
        Index(
            "uq_location_bins_location_code_active",
            "location_id",
            text("lower(code)"),
            unique=True,
            postgresql_where=text("NOT is_archived"),
        ),
        Index(
            "uq_location_bins_location_slot_active",
            "location_id",
            "row_code",
            "bay",
            "level",
            unique=True,
            postgresql_where=text("NOT is_archived"),
        ),
        Index(
            "uq_location_bins_one_active_default",
            "location_id",
            unique=True,
            postgresql_where=text("is_default AND NOT is_archived"),
        ),
        CheckConstraint("bay >= 1", name="ck_location_bins_bay"),
        CheckConstraint("level >= 1", name="ck_location_bins_level"),
    )


class BinStock(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "bin_stock"

    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    bin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("location_bins.id", ondelete="RESTRICT"),
        nullable=False,
    )
    on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sku: Mapped["Sku"] = relationship()
    bin: Mapped["LocationBin"] = relationship()

    __table_args__ = (
        UniqueConstraint("sku_id", "bin_id", name="uq_bin_stock_sku_bin"),
        CheckConstraint("on_hand >= 0", name="ck_bin_stock_on_hand"),
    )


from app.models.location import Location  # noqa: E402
from app.models.sku import Sku  # noqa: E402


def new_floor_bin(location_id: uuid.UUID) -> LocationBin:
    return LocationBin(
        location_id=location_id,
        code=DEFAULT_BIN_CODE,
        row_code=DEFAULT_ROW_CODE,
        bay=DEFAULT_BAY,
        level=DEFAULT_LEVEL,
        is_default=True,
        is_archived=False,
    )
