from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.schemas.entry import EntryResponse
from app.schemas.health_metrics import HealthMetricResponse
from app.schemas.weather import WeatherDailySummary


class EnrichedDayResponse(BaseModel):
    entry: Optional[EntryResponse] = None
    weather: Optional[WeatherDailySummary] = None
    health_metrics: Optional[HealthMetricResponse] = None
