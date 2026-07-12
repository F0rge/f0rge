from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id


class WeatherReading(Base):
    __tablename__ = "weather_readings"
    __table_args__ = (
        Index("ix_weather_readings_user_id", "user_id"),
        Index("ix_weather_readings_timestamp", "timestamp"),
        Index("ix_weather_readings_date", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    pressure_hpa: Mapped[float] = mapped_column(Float, nullable=False)
    weather_main: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)
