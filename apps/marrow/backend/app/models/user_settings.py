from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user_id"),
        Index("ix_user_settings_user_id", "user_id"),
        Index(
            "uq_user_settings_external_api_token_hash",
            "external_api_token_hash",
            unique=True,
            postgresql_where=text("external_api_token_hash IS NOT NULL"),
        ),
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
    external_api_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    onboarding_completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    tagged_meal_mode: Mapped[str] = mapped_column(String, nullable=False, default="approve")
    profile_tag_filter_mode: Mapped[str] = mapped_column(String, nullable=False, default="off")
    # CSV of diet-tag keys (entry.diet_risk convention); "" = no tags selected.
    profile_filter_tags: Mapped[str] = mapped_column(String, nullable=False, default="")

    @property
    def profile_filter_tags_list(self) -> list[str]:
        """Decoded CSV — the single owner of the storage convention above."""
        return [t for t in self.profile_filter_tags.split(",") if t]

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
