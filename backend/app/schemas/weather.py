from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WeatherReadingResponse(BaseModel):
    id: int
    timestamp: datetime.datetime
    date: datetime.date
    temperature_c: float
    humidity_pct: float
    pressure_hpa: float
    weather_main: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WeatherDailySummary(BaseModel):
    date: datetime.date
    pressure_mean: Optional[float] = None
    pressure_min: Optional[float] = None
    pressure_max: Optional[float] = None
    pressure_delta_24h: Optional[float] = None
    temp_mean: Optional[float] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    humidity_mean: Optional[float] = None
    reading_count: int = 0
