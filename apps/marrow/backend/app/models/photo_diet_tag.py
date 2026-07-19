from __future__ import annotations

import datetime
import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id


class PhotoDietTag(Base):
    """Explicit per-photo diet tag (key into the user's diet_tag_catalog)."""

    __tablename__ = "photo_diet_tags"
    __table_args__ = (
        UniqueConstraint("photo_id", "key", name="uq_photo_diet_tags_photo_id_key"),
        Index("ix_photo_diet_tags_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    photo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("photos.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
