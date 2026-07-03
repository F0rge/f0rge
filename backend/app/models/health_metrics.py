from __future__ import annotations

import datetime

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HealthMetric(Base):
    __tablename__ = "health_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, unique=True, nullable=False, index=True)
    hrv_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    hrv_std: Mapped[float | None] = mapped_column(Float, nullable=True)
    resting_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_deep_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_rem_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_core_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_awake_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_deep_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_rem_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_efficiency: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_start: Mapped[str | None] = mapped_column(String, nullable=True)
    sleep_end: Mapped[str | None] = mapped_column(String, nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    spo2: Mapped[float | None] = mapped_column(Float, nullable=True)
    wrist_temp_deviation: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="health_auto_export")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
