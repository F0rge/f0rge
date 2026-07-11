from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.weather import WeatherService


def get_weather_service(db: AsyncSession = Depends(get_db)) -> WeatherService:
    return WeatherService(db)
