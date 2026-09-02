from __future__ import annotations

import datetime
import enum
import uuid
from typing import Any, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class NiaMessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class NiaThread(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "nia_threads"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    archived_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    pending_tools: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    agent_messages: Mapped[Optional[list[Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    user: Mapped["User"] = relationship()
    team: Mapped["Team"] = relationship()
    messages: Mapped[list["NiaMessage"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="NiaMessage.created_at",
        lazy="selectin",
    )


class NiaMessage(UUIDPkMixin, Base):
    __tablename__ = "nia_messages"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nia_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
    )

    thread: Mapped[NiaThread] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')",
            name="ck_nia_messages_role",
        ),
    )


class NiaAuditEvent(UUIDPkMixin, Base):
    __tablename__ = "nia_audit_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nia_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    args: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
    )

    user: Mapped["User"] = relationship()
    thread: Mapped[Optional["NiaThread"]] = relationship()


class NiaUsageEvent(UUIDPkMixin, Base):
    __tablename__ = "nia_usage_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nia_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
    )
    openrouter_generation_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class NiaScheduledTask(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "nia_scheduled_tasks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="Africa/Johannesburg")
    cadence: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_only_if_changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_run_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_output_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship()
    team: Mapped["Team"] = relationship()
    runs: Mapped[list["NiaScheduledRun"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="NiaScheduledRun.started_at",
    )

    __table_args__ = (
        CheckConstraint(
            "last_status IS NULL OR last_status IN ('ok', 'skipped', 'error', 'needs_ok')",
            name="ck_nia_scheduled_tasks_last_status",
        ),
    )


class NiaScheduledRun(UUIDPkMixin, Base):
    __tablename__ = "nia_scheduled_runs"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nia_scheduled_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nia_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    task: Mapped[NiaScheduledTask] = relationship(back_populates="runs")
    thread: Mapped[Optional["NiaThread"]] = relationship()

    __table_args__ = (
        CheckConstraint(
            "status IN ('ok', 'skipped', 'error', 'needs_ok')",
            name="ck_nia_scheduled_runs_status",
        ),
    )


from app.models.team import Team  # noqa: E402
from app.models.user import User  # noqa: E402
