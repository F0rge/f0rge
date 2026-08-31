from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_entries_user_id_date"),
        Index("ix_entries_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    entry_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    period_of_day: Mapped[str | None] = mapped_column(String, nullable=True)
    overall: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bloating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # v1 fields kept for backwards compat; v2 entries leave them null.
    stool_normal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stool_type: Mapped[str | None] = mapped_column(String, nullable=True)
    # v2 stool fields. stool_status: 'normal' | 'abnormal' | 'none'.
    stool_status: Mapped[str | None] = mapped_column(String, nullable=True)
    bristol_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # v4: 'complete' | 'incomplete' | None (unrecorded).
    stool_completeness: Mapped[str | None] = mapped_column(String, nullable=True)
    joint_pain: Mapped[int] = mapped_column(Integer, nullable=False)
    neuro: Mapped[int] = mapped_column(Integer, nullable=False)
    sleep_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diet_risk: Mapped[str] = mapped_column(String, nullable=False)
    supplements: Mapped[str] = mapped_column(String, nullable=False)
    sick: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hot_shower: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alcohol_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caffeine_servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    symptoms_json: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB), nullable=False, default=dict, server_default="{}"
    )
    # List of medication-intake events for the day, e.g.
    # [{"key": "ibuprofen", "dose": "400mg", "reason": "headache", "time": "15:20"}].
    # `key` is a medication_catalog key but is NOT FK-constrained -- historical
    # entries keep their keys even after the catalog item is archived (same
    # leniency as `supplements`/diet tags).
    medications_json: Mapped[list] = mapped_column(
        MutableList.as_mutable(JSONB), nullable=False, default=list, server_default="[]"
    )
    # Timed symptom stamps for the day, e.g.
    # [{"key": "vss", "severity": 7, "time": "15:20"}].
    # `symptoms_json` stays the day's current score; this list is the clock.
    symptom_events_json: Mapped[list] = mapped_column(
        MutableList.as_mutable(JSONB), nullable=False, default=list, server_default="[]"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    photos: Mapped[list[Photo]] = relationship(
        "Photo", back_populates="entry", cascade="all, delete-orphan", lazy="selectin"
    )
