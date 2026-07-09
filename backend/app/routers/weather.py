from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends

from app.dependencies.weather import get_weather_service
from app.middleware.auth import get_current_session
from app.schemas.weather import WeatherDailySummary, WeatherReadingResponse
from app.services.weather import WeatherService, trigger_weather_fetch

router = APIRouter(
    prefix="/api/v1/weather",
    tags=["weather"],
    dependencies=[Depends(get_current_session)],
)


@router.post("/fetch", response_model=WeatherReadingResponse)
async def trigger_weather_fetch_endpoint():
    return await trigger_weather_fetch()


@router.get("/{date}", response_model=WeatherDailySummary)
async def get_weather_summary(
    date: datetime.date,
    service: WeatherService = Depends(get_weather_service),
):
    return await service.get_daily_summary_or_404(date)
