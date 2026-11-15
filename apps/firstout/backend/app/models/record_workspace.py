"""Durable outcomes for repeat-safe, tenant-scoped record workspace batches."""

from __future__ import annotations

import uuid
from typing import Any

from f0rge_db.mixins import TimestampMixin, UUIDPkMixin
from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin


class RecordWorkspaceBatch(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    """Insert the completed outcome in the same transaction as its domain writes.

    Signed preflight tokens expire independently. This row retains the actor,
    frozen record identities/revisions and result without persisting edit values.
    Replace JSON values as a whole; do not mutate them in place.
    """

    __tablename__ = "record_workspace_batches"

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    selection: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "team_id", "actor_user_id", "request_id", name="uq_record_workspace_batch_request"
        ),
    )
