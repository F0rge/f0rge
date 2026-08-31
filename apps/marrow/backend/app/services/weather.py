"""Daily weather attach via Open-Meteo (no API key)."""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.weather import WeatherCRUD
from f0rge_core.exceptions import ExternalServiceError, NotFoundError
from app.models.weather import WeatherReading
from app.schemas.weather import WeatherDailySummary
from app.services.open_meteo import fetch_open_meteo_day
from app.utils.dates import local_today
from f0rge_db.tenant import current_user_id

logger = logging.getLogger(__name__)


class WeatherService:
    """One daily Open-Meteo snapshot per user+date, on check-in."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = WeatherCRUD(db)

    async def get_daily_summary(self, date: datetime.date) -> Optional[WeatherDailySummary]:
        """Compute daily weather aggregates for a given date."""
        readings = await self.crud.list_by_date(date)
        if not readings:
            return None

        pressures = [r.pressure_hpa for r in readings]
        temps = [r.temperature_c for r in readings]
        humidities = [r.humidity_pct for r in readings]

        pressure_mean = sum(pressures) / len(pressures)
        temp_mean = sum(temps) / len(temps)
        humidity_mean = sum(humidities) / len(humidities)

        yesterday = date - datetime.timedelta(days=1)
        yesterday_readings = await self.crud.list_by_date(yesterday)

        pressure_delta_24h = None
        if yesterday_readings:
            yesterday_pressures = [r.pressure_hpa for r in yesterday_readings]
            yesterday_mean = sum(yesterday_pressures) / len(yesterday_pressures)
            pressure_delta_24h = round(pressure_mean - yesterday_mean, 2)

        return WeatherDailySummary(
            date=date,
            pressure_mean=round(pressure_mean, 2),
            pressure_min=round(min(pressures), 2),
            pressure_max=round(max(pressures), 2),
            pressure_delta_24h=pressure_delta_24h,
            temp_mean=round(temp_mean, 2),
            temp_min=round(min(temps), 2),
            temp_max=round(max(temps), 2),
            humidity_mean=round(humidity_mean, 2),
            reading_count=len(readings),
        )

    async def get_daily_summary_or_404(self, date: datetime.date) -> WeatherDailySummary:
        """Return daily summary or raise NotFoundError."""
        summary = await self.get_daily_summary(date)
        if summary is None:
            raise NotFoundError(f"No weather data for {date}")
        return summary

    async def ensure_for_date(self, target_date: datetime.date) -> Optional[WeatherReading]:
        """Fetch and store one daily reading if this user+date has none."""
        if not settings.weather_fetch_enabled:
            return None

        existing = await self.crud.list_by_date(target_date)
        if existing:
            return existing[0]

        user_id = current_user_id()
        if user_id is None:
            logger.warning("Weather attach skipped: no current user")
            return None

        day = await fetch_open_meteo_day(target_date)
        if day is None:
            logger.warning("Open-Meteo returned no data for %s", target_date)
            return None

        reading = WeatherReading(
            user_id=user_id,
            timestamp=datetime.datetime.combine(target_date, datetime.time(12, 0)),
            date=target_date,
            temperature_c=round(day.temp_mean, 2),
            humidity_pct=round(day.humidity_mean, 2),
            pressure_hpa=round(day.pressure_mean, 2),
            weather_main=day.weather_main,
        )
        self.crud.add(reading)
        return await self.crud.commit_refresh(reading)

    async def fetch_today(self) -> WeatherReading:
        """Settings Fetch Now: store today's snapshot for the current user."""
        reading = await self.ensure_for_date(local_today())
        if reading is None:
            raise ExternalServiceError("Failed to fetch weather data")
        return reading


async def attach_weather_for_date(db: AsyncSession, target_date: datetime.date) -> None:
    """Best-effort daily weather after a check-in write. Never raises."""
    try:
        await WeatherService(db).ensure_for_date(target_date)
    except Exception:
        logger.exception("Weather attach failed for %s; check-in is unchanged", target_date)
        try:
            if db.in_transaction():
                await db.rollback()
        except Exception:
            logger.debug("Weather rollback after attach failure also failed", exc_info=True)
