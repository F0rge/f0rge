from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Meal(Base):
    """Canonical food event — one image + one analysis shared across placements."""

    __tablename__ = "meals"
    __table_args__ = (Index("ix_meals_owner_user_id", "owner_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    icon_key: Mapped[str | None] = mapped_column(String, nullable=True)
    platform_meal_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("platform_meals.id", ondelete="SET NULL"),
        nullable=True,
    )
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    meal_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )

    photos: Mapped[list[Photo]] = relationship(
        "Photo",
        back_populates="meal",
        lazy="selectin",
    )
    analysis: Mapped[Optional[PhotoAnalysis]] = relationship(
        "PhotoAnalysis",
        back_populates="meal",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
