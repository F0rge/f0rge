from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.weather import WeatherCRUD
from app.database import async_session_maker
from f0rge_core.exceptions import ExternalServiceError, NotFoundError
from app.models.user import default_user_id
from app.models.weather import WeatherReading
from app.schemas.weather import WeatherDailySummary
from f0rge_db.tenant import apply_session_user_id

logger = logging.getLogger(__name__)


async def fetch_and_store_weather() -> Optional[WeatherReading]:
    """Fetch current weather from OpenWeatherMap and store it.

    Uses async httpx and its own async SQLAlchemy session — this runs from the
    background loop (no request context to borrow a session from).
    Returns the reading or None if the hour was already recorded or the fetch failed.
    """
    api_key = settings.openweathermap_api_key
    city = settings.openweathermap_city
    if not api_key:
        logger.warning("No OpenWeatherMap API key configured, skipping fetch")
        return None

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("Failed to fetch weather data")
        return None

    now = datetime.datetime.utcnow()
    truncated = now.replace(minute=0, second=0, microsecond=0)

    try:
        async with async_session_maker() as db:
            await apply_session_user_id(db, default_user_id())
            crud = WeatherCRUD(db)
            existing = await crud.get_by_timestamp(truncated)

            if existing:
                logger.debug("Weather reading for %s already exists, skipping", truncated)
                return existing

            weather_main = None
            if data.get("weather") and len(data["weather"]) > 0:
                weather_main = data["weather"][0].get("main")

            main = data.get("main", {})
            reading = WeatherReading(
                timestamp=truncated,
                date=truncated.date(),
                temperature_c=main.get("temp", 0.0),
                humidity_pct=main.get("humidity", 0.0),
                pressure_hpa=main.get("pressure", 0.0),
                weather_main=weather_main,
            )
            crud.add(reading)
            reading = await crud.commit_refresh(reading)
            logger.info("Stored weather reading for %s", truncated)
            return reading
    except Exception:
        logger.exception("Failed to store weather reading")
        return None


async def trigger_weather_fetch() -> WeatherReading:
    """Fetch and store weather; raise ExternalServiceError on failure."""
    reading = await fetch_and_store_weather()
    if reading is None:
        raise ExternalServiceError("Failed to fetch weather data")
    return reading


async def weather_background_loop() -> None:
    """Run weather fetch every hour in a background task."""
    while True:
        try:
            await fetch_and_store_weather()
        except Exception:
            logger.exception("Error in weather background loop")
        await asyncio.sleep(3600)


class WeatherService:
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

        # Compute pressure delta vs yesterday
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
