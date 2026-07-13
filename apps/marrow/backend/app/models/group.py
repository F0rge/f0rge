from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 60", name="ck_groups_name_len"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("(now() at time zone 'utc')")
    )
    members: Mapped[list[GroupMember]] = relationship(
        "GroupMember",
        back_populates="group",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'member')", name="ck_group_members_role"),
        CheckConstraint("status IN ('invited', 'joined')", name="ck_group_members_status"),
        UniqueConstraint("group_id", "user_id", name="uq_group_members_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="member")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="invited")
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("(now() at time zone 'utc')")
    )
    joined_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    group: Mapped[Group] = relationship("Group", back_populates="members", lazy="selectin")
