from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal, Optional

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import UUIDPkMixin


class McpToken(TenantOwnedMixin, UUIDPkMixin, Base):
    __tablename__ = "mcp_tokens"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "team_id"],
            ["memberships.user_id", "memberships.team_id"],
            name="fk_mcp_tokens_membership",
            ondelete="CASCADE",
        ),
        UniqueConstraint("team_id", "digest", name="uq_mcp_tokens_team_digest"),
        UniqueConstraint("team_id", "user_id", "id", name="uq_mcp_tokens_owner_id"),
        Index("ix_mcp_tokens_owner_created", "team_id", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID]
    name: Mapped[str] = mapped_column(String(80))
    digest: Mapped[Optional[str]] = mapped_column(
        String(64), deferred=True, deferred_raiseload=True
    )
    suffix: Mapped[str] = mapped_column(String(4))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    @property
    def status(self) -> Literal["active", "revoked", "expired"]:
        if self.revoked_at is not None:
            return "revoked"
        return "expired" if self.expires_at <= datetime.now(UTC) else "active"


class McpTokenActivity(TenantOwnedMixin, UUIDPkMixin, Base):
    __tablename__ = "mcp_token_activity"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "user_id", "token_id"],
            ["mcp_tokens.team_id", "mcp_tokens.user_id", "mcp_tokens.id"],
            name="fk_mcp_token_activity_owner",
            ondelete="CASCADE",
        ),
        Index("ix_mcp_token_activity_owner_time", "team_id", "user_id", "occurred_at"),
    )

    user_id: Mapped[uuid.UUID]
    token_id: Mapped[uuid.UUID]
    token_name: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(12))
    result: Mapped[str] = mapped_column(String(12))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
