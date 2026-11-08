"""Exact-key identity/capability directories, never customer business-data access.

Organisation IDs here are approval metadata. CustomerPortalUser and all customer
data remain tenant-owned under FORCE RLS; only a verified binding establishes it.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class PortalAccess(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "portal_access"
    clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    portal_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_portal_users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(), nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organisation_id", "customer_id"],
            ["customers.team_id", "customers.id"],
            name="fk_portal_access_customer_scope",
        ),
        ForeignKeyConstraint(
            ["organisation_id", "portal_user_id"],
            ["customer_portal_users.team_id", "customer_portal_users.id"],
            name="fk_portal_access_user_scope",
        ),
        UniqueConstraint(
            "clerk_user_id", "organisation_id", name="uq_portal_access_subject_organisation"
        ),
    )


class PortalInvitation(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "portal_invitations"
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(), nullable=False)
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    used_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(), nullable=True)
    accepted_by_clerk_user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(), nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organisation_id", "customer_id"],
            ["customers.team_id", "customers.id"],
            name="fk_portal_invitation_customer_scope",
        ),
    )
