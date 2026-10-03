from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Migrated rows were never named by the user. The settings list shows this name.
LEGACY_EXTERNAL_API_TOKEN_NAME = "existing token"


class ExternalApiToken(Base):
    """One live MCP bearer token. Many rows per user; auth matches any hash."""

    __tablename__ = "external_api_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_external_api_tokens_token_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # Null for a hash copied from user_settings — that column has no issued-at.
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
