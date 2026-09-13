from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id


class NOf1Slot(Base):
    """At most one active n-of-1 experiment slot per user."""

    __tablename__ = "n_of_1_slots"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_n_of_1_slots_user_id"),
        Index("ix_n_of_1_slots_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    change: Mapped[str] = mapped_column(Text, nullable=False)
    start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    watch_field: Mapped[str] = mapped_column(Text, nullable=False)
    stop_rule: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
        server_default=text("(now() at time zone 'utc')"),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        server_default=text("(now() at time zone 'utc')"),
    )
