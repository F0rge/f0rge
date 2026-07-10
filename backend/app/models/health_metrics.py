from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id


class HealthMetric(Base):
    __tablename__ = "health_metrics"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_health_metrics_user_id_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=default_user_id,
    )
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
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
