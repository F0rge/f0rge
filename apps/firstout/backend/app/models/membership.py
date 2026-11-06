from __future__ import annotations

import uuid

from f0rge_db.mixins import TimestampMixin, UUIDPkMixin
from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Membership(UUIDPkMixin, TimestampMixin, Base):
    """Identity directory; home membership survives Clerk deletion during dual-auth."""

    __tablename__ = "memberships"
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    permission_source: Mapped[str] = mapped_column(String(32), nullable=False, default="legacy")
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_legacy_home: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    __table_args__ = (
        UniqueConstraint("user_id", "team_id", name="uq_memberships_user_team"),
        Index(
            "uq_memberships_legacy_home",
            "user_id",
            unique=True,
            postgresql_where=text("is_legacy_home"),
        ),
    )
