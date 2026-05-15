from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, unique=True, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    entry_time: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    period_of_day: Mapped[str | None] = mapped_column(String, nullable=True)
    overall: Mapped[int] = mapped_column(Integer, nullable=False)
    bloating: Mapped[int] = mapped_column(Integer, nullable=False)
    # v1 fields kept for backwards compat; v2 entries leave them null.
    stool_normal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stool_type: Mapped[str | None] = mapped_column(String, nullable=True)
    # v2 stool fields. stool_status: 'normal' | 'abnormal' | 'none'.
    stool_status: Mapped[str | None] = mapped_column(String, nullable=True)
    bristol_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    joint_pain: Mapped[int] = mapped_column(Integer, nullable=False)
    neuro: Mapped[int] = mapped_column(Integer, nullable=False)
    sleep_quality: Mapped[int] = mapped_column(Integer, nullable=False)
    stress: Mapped[int] = mapped_column(Integer, nullable=False)
    diet_risk: Mapped[str] = mapped_column(String, nullable=False)
    supplements: Mapped[str] = mapped_column(String, nullable=False)
    sick: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hot_shower: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alcohol_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caffeine_servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    photos: Mapped[list[Photo]] = relationship(
        "Photo", back_populates="entry", cascade="all, delete-orphan"
    )
