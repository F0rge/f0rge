from __future__ import annotations

import datetime

from sqlalchemy import DateTime, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    llm_provider: Mapped[str] = mapped_column(String, nullable=False, default="openrouter")
    llm_api_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_provider: Mapped[str] = mapped_column(String, nullable=False, default="openrouter")
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
    external_api_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
