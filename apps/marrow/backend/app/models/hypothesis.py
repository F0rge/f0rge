from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id

HYPOTHESIS_STATUSES = ("live", "weakening", "killed", "parked")
HYPOTHESIS_LAYERS = (1, 2)


class Hypothesis(Base):
    """User-owned care hypothesis. Killed rows stay; there is no hard-delete path."""

    __tablename__ = "hypotheses"
    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_hypotheses_user_id_slug"),
        CheckConstraint(
            "status IN ('live', 'weakening', 'killed', 'parked')",
            name="ck_hypotheses_status",
        ),
        CheckConstraint("layer IS NULL OR layer IN (1, 2)", name="ck_hypotheses_layer"),
        Index("ix_hypotheses_user_id", "user_id"),
        Index("ix_hypotheses_user_id_status", "user_id", "status"),
        Index("ix_hypotheses_user_id_sort_order", "user_id", "sort_order"),
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
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    layer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kill_test: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_move: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    cite: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
