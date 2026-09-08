from __future__ import annotations

import datetime
import enum

from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class LocationType(str, enum.Enum):
    WAREHOUSE = "warehouse"
    SHOWROOM = "showroom"


class Location(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[LocationType] = mapped_column(
        Enum(
            LocationType,
            name="location_type",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            "ix_locations_name_active_lower",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("NOT is_archived"),
        ),
        CheckConstraint(
            "type IN ('warehouse', 'showroom')",
            name="ck_locations_type",
        ),
    )
