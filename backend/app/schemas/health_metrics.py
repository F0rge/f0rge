from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class HealthMetricCreate(BaseModel):
    date: datetime.date
    hrv_mean: Optional[float] = None
    hrv_std: Optional[float] = None
    resting_hr: Optional[float] = None
    sleep_hours: Optional[float] = None
    sleep_deep_pct: Optional[float] = None
    sleep_rem_pct: Optional[float] = None
    steps: Optional[int] = None
    active_minutes: Optional[float] = None
    spo2: Optional[float] = None
    wrist_temp_deviation: Optional[float] = None


class HealthMetricResponse(BaseModel):
    id: int
    date: datetime.date
    hrv_mean: Optional[float] = None
    hrv_std: Optional[float] = None
    resting_hr: Optional[float] = None
    sleep_hours: Optional[float] = None
    sleep_deep_pct: Optional[float] = None
    sleep_rem_pct: Optional[float] = None
    steps: Optional[int] = None
    active_minutes: Optional[float] = None
    spo2: Optional[float] = None
    wrist_temp_deviation: Optional[float] = None
    source: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
