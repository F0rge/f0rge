from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.database import Base

LEO_PLACEHOLDER_PASSWORD_HASH = "$2b$12$placeholderplaceholderplaceholderplac"


def default_user_id() -> uuid.UUID:
    return uuid.UUID(settings.default_storage_user_id)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    handle: Mapped[str | None] = mapped_column(CITEXT, unique=True, nullable=True)
    avatar_default_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    avatar_custom_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
    )
    infrastructure_provisioned_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
