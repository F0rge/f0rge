from __future__ import annotations

import datetime
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings
from app.utils.dates import local_today

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# Luxembourg City — fallback when geocoding the configured city fails.
_DEFAULT_LAT = 49.6116
_DEFAULT_LON = 6.1319
_HOURLY = "temperature_2m,relative_humidity_2m,surface_pressure,weather_code"
_ARCHIVE_AFTER_DAYS = 4

_WMO_RANGES: tuple[tuple[int, int, str], ...] = (
    (0, 1, "Clear"),
    (2, 3, "Clouds"),
    (45, 48, "Fog"),
    (51, 67, "Rain"),
    (71, 77, "Snow"),
    (80, 82, "Rain"),
    (85, 86, "Snow"),
    (95, 99, "Thunderstorm"),
)


@dataclass(frozen=True)
class OpenMeteoDay:
    temp_mean: float
    temp_min: float
    temp_max: float
    humidity_mean: float
    pressure_mean: float
    weather_main: Optional[str]


_geo_cache: Optional[tuple[str, float, float]] = None


def weather_main_from_code(code: Optional[int]) -> Optional[str]:
    if code is None:
        return None
    for low, high, name in _WMO_RANGES:
        if low <= code <= high:
            return name
    return "Clouds"


async def resolve_coordinates() -> tuple[float, float]:
    global _geo_cache
    city = (settings.openweathermap_city or "Luxembourg").strip() or "Luxembourg"
    if _geo_cache is not None and _geo_cache[0] == city:
        return _geo_cache[1], _geo_cache[2]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(GEOCODE_URL, params={"name": city, "count": 1})
            resp.raise_for_status()
            results = resp.json().get("results") or []
            if results:
                lat = float(results[0]["latitude"])
                lon = float(results[0]["longitude"])
                _geo_cache = (city, lat, lon)
                return lat, lon
    except Exception:
        logger.exception("Open-Meteo geocode failed for %s", city)
    return _DEFAULT_LAT, _DEFAULT_LON


async def fetch_open_meteo_day(date: datetime.date) -> Optional[OpenMeteoDay]:
    """Return daily aggregates for ``date``, or None if the provider has no data."""
    lat, lon = await resolve_coordinates()
    use_archive = date < local_today() - datetime.timedelta(days=_ARCHIVE_AFTER_DAYS)
    payload = await _get_hourly(ARCHIVE_URL if use_archive else FORECAST_URL, lat, lon, date)
    if payload is None and not use_archive:
        payload = await _get_hourly(ARCHIVE_URL, lat, lon, date)
    if payload is None:
        return None
    return aggregate_hourly(payload)


async def _get_hourly(url: str, lat: float, lon: float, date: datetime.date) -> Optional[dict]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date.isoformat(),
        "end_date": date.isoformat(),
        "hourly": _HOURLY,
        "timezone": settings.app_timezone,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("Open-Meteo request failed (%s)", url)
        return None
    hourly = data.get("hourly") or {}
    temps = hourly.get("temperature_2m") or []
    if not any(value is not None for value in temps):
        return None
    return hourly


def aggregate_hourly(hourly: dict) -> Optional[OpenMeteoDay]:
    temps = [v for v in hourly.get("temperature_2m") or [] if v is not None]
    humidities = [v for v in hourly.get("relative_humidity_2m") or [] if v is not None]
    pressures = [v for v in hourly.get("surface_pressure") or [] if v is not None]
    codes = [int(v) for v in hourly.get("weather_code") or [] if v is not None]
    if not temps or not pressures:
        return None
    humidity = sum(humidities) / len(humidities) if humidities else 0.0
    weather_main = None
    if codes:
        weather_main = weather_main_from_code(Counter(codes).most_common(1)[0][0])
    return OpenMeteoDay(
        temp_mean=sum(temps) / len(temps),
        temp_min=min(temps),
        temp_max=max(temps),
        humidity_mean=humidity,
        pressure_mean=sum(pressures) / len(pressures),
        weather_main=weather_main,
    )
