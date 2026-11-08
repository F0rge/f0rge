"""Provisioning is a capability directory; invitations are tenant-owned business rows."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class TenantProvisioningAttempt(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tenant_provisioning_attempts"

    clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    clerk_org_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    result_team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True
    )


class TenantInvitation(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tenant_invitations"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    clerk_invitation_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        Index(
            "uq_pending_tenant_invitation_email",
            "team_id",
            "email",
            unique=True,
            postgresql_where=text("status='pending'"),
        ),
    )
