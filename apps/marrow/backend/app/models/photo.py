from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.entry import Entry
from app.models.user import User, default_user_id


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (
        Index("ix_photos_user_id", "user_id"),
        Index("ix_photos_meal_id", "meal_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False
    )
    meal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    meal_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    source_photo_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("photos.id", ondelete="SET NULL"),
        nullable=True,
    )
    tagged_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )

    entry: Mapped[Entry] = relationship("Entry", back_populates="photos", lazy="selectin")
    meal: Mapped["Meal"] = relationship("Meal", back_populates="photos", lazy="selectin")
    tagged_by_user: Mapped[Optional[User]] = relationship(
        "User",
        foreign_keys=[tagged_by_user_id],
        lazy="selectin",
    )
    analysis: Mapped[Optional["PhotoAnalysis"]] = relationship(
        "PhotoAnalysis",
        primaryjoin="Photo.meal_id == PhotoAnalysis.meal_id",
        foreign_keys="PhotoAnalysis.meal_id",
        viewonly=True,
        uselist=False,
        lazy="selectin",
    )
