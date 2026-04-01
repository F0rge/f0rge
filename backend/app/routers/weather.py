from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.weather import WeatherDailySummary, WeatherReadingResponse
from app.services.weather import fetch_and_store_weather, get_daily_summary

router = APIRouter(
    prefix="/api/v1/weather",
    tags=["weather"],
    dependencies=[Depends(get_current_session)],
)


@router.post("/fetch", response_model=WeatherReadingResponse)
def trigger_weather_fetch():
    reading = fetch_and_store_weather()
    if reading is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch weather data",
        )
    return reading


@router.get("/{date}", response_model=WeatherDailySummary)
def get_weather_summary(date: datetime.date, db: Session = Depends(get_db)):
    summary = get_daily_summary(db, date)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No weather data for {date}",
        )
    return summary
