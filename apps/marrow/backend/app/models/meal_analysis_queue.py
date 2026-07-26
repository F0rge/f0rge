from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id

# Worker lease marker — claim sets this; stale leases are reclaimable.
STAGE_RUNNING = "running"


class MealAnalysisQueue(Base):
    """Durable outbox for the meal analysis worker.

    Upload/retry enqueue a row; the worker claims with SKIP LOCKED, runs
    extract → enrich → gate → persist, then deletes the row on success.
    """

    __tablename__ = "meal_analysis_queue"
    __table_args__ = (
        UniqueConstraint("meal_id", name="uq_meal_analysis_queue_meal_id"),
        Index("ix_meal_analysis_queue_user_id", "user_id"),
        # Non-partial: meal_analysis_worker_max_attempts is configurable, so a
        # hardcoded ``attempts < N`` predicate would miss claimable rows.
        Index("ix_meal_analysis_queue_enqueued", "enqueued_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    meal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meals.id", ondelete="CASCADE"),
        nullable=False,
    )
    photo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("photos.id", ondelete="CASCADE"),
        nullable=False,
    )
    enqueued_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("now()"),
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_attempt_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
