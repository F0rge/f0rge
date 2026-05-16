from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.weather import WeatherReading
from app.schemas.weather import WeatherDailySummary

logger = logging.getLogger(__name__)


def fetch_and_store_weather() -> Optional[WeatherReading]:
    """Fetch current weather from OpenWeatherMap and store it.

    Uses sync httpx and sync SQLAlchemy. Returns the reading or None
    if the hour was already recorded or the fetch failed.
    """
    api_key = settings.openweathermap_api_key
    city = settings.openweathermap_city
    if not api_key:
        logger.warning("No OpenWeatherMap API key configured, skipping fetch")
        return None

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}

    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("Failed to fetch weather data")
        return None

    now = datetime.datetime.utcnow()
    truncated = now.replace(minute=0, second=0, microsecond=0)

    db = SessionLocal()
    try:
        existing = (
            db.query(WeatherReading)
            .filter(WeatherReading.timestamp == truncated)
            .first()
        )
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
        db.add(reading)
        db.commit()
        db.refresh(reading)
        logger.info("Stored weather reading for %s", truncated)
        return reading
    except Exception:
        db.rollback()
        logger.exception("Failed to store weather reading")
        return None
    finally:
        db.close()


def get_daily_summary(
    db: Session, date: datetime.date
) -> Optional[WeatherDailySummary]:
    """Compute daily weather aggregates for a given date."""
    readings = (
        db.query(WeatherReading)
        .filter(WeatherReading.date == date)
        .all()
    )

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
    yesterday_readings = (
        db.query(WeatherReading)
        .filter(WeatherReading.date == yesterday)
        .all()
    )
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


async def weather_background_loop() -> None:
    """Run weather fetch every hour in a background task."""
    while True:
        try:
            await asyncio.to_thread(fetch_and_store_weather)
        except Exception:
            logger.exception("Error in weather background loop")
        await asyncio.sleep(3600)
