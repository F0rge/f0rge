from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MealTag(Base):
    __tablename__ = "meal_tags"
    __table_args__ = (
        UniqueConstraint("source_photo_id", "tagged_user_id", name="uq_meal_tags_pair"),
        Index("ix_meal_tags_tagged_user", "tagged_user_id"),
        Index("ix_meal_tags_tagger", "tagger_id"),
        Index("ix_meal_tags_source", "source_photo_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_photo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("photos.id", ondelete="CASCADE"),
        nullable=False,
    )
    tagger_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tagged_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending_analysis")
    source_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_dish_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_photo_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("photos.id", ondelete="SET NULL"),
        nullable=True,
    )
