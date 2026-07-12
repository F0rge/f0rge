from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user_id"),
        Index("ix_user_settings_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    llm_provider: Mapped[str] = mapped_column(String, nullable=False, default="openrouter")
    llm_api_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_provider: Mapped[str] = mapped_column(String, nullable=False, default="openrouter")
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
    external_api_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    onboarding_completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    tagged_meal_mode: Mapped[str] = mapped_column(String, nullable=False, default="approve")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
