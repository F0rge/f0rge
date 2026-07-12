from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (Index("ix_photos_user_id", "user_id"),)

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
    filename: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    meal_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )

    entry: Mapped[Entry] = relationship("Entry", back_populates="photos", lazy="selectin")
    # cascade="all, delete-orphan" is required: PhotoAnalysis.photo_id is
    # NOT NULL, so without an ORM-level cascade SQLAlchemy tries to NULL
    # the FK on photo delete and the commit blows up with an IntegrityError.
    analysis: Mapped[Optional[PhotoAnalysis]] = relationship(
        "PhotoAnalysis",
        back_populates="photo",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
        lazy="selectin",
    )
