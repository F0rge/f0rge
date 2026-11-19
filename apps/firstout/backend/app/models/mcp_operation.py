from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKeyConstraint, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import UUIDPkMixin


class McpOperation(TenantOwnedMixin, UUIDPkMixin, Base):
    __tablename__ = "mcp_operations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "user_id", "token_id"],
            ["mcp_tokens.team_id", "mcp_tokens.user_id", "mcp_tokens.id"],
            name="fk_mcp_operations_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("team_id", "token_id", "request_id", name="uq_mcp_operations_request"),
    )

    user_id: Mapped[uuid.UUID]
    token_id: Mapped[uuid.UUID]
    token_version: Mapped[int]
    request_id: Mapped[uuid.UUID]
    action_name: Mapped[str] = mapped_column(String(80))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB)
    preview: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[uuid.UUID | None]
