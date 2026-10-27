from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import UUIDPkMixin


class PasswordResetToken(UUIDPkMixin, Base):
    """Single-use password reset. Only the SHA-256 hex of the token is stored."""

    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
        Index("ix_password_reset_tokens_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(), nullable=False)
    used_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(),
        nullable=False,
        default=datetime.datetime.utcnow,
    )
