from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthMetricSample(BaseModel):
    model_config = ConfigDict(extra="allow")

    qty: Optional[float] = None
    date: Optional[str] = None


class HealthAutoExportMetric(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    units: Optional[str] = None
    data: list[dict[str, Any]] = Field(default_factory=list)


class HealthAutoExportData(BaseModel):
    metrics: list[HealthAutoExportMetric] = Field(default_factory=list)


class HealthAutoExportPayload(BaseModel):
    """Validated body for POST /health-metrics/import (Health Auto Export JSON)."""

    data: HealthAutoExportData = Field(default_factory=HealthAutoExportData)


class HealthImportResponse(BaseModel):
    status: str
    dates_upserted: int


class HealthMetricCreate(BaseModel):
    date: datetime.date
    hrv_mean: Optional[float] = None
    hrv_std: Optional[float] = None
    resting_hr: Optional[float] = None
    sleep_hours: Optional[float] = None
    sleep_deep_min: Optional[float] = None
    sleep_rem_min: Optional[float] = None
    sleep_core_min: Optional[float] = None
    sleep_awake_min: Optional[float] = None
    sleep_deep_pct: Optional[float] = None
    sleep_rem_pct: Optional[float] = None
    sleep_efficiency: Optional[float] = None
    sleep_start: Optional[str] = None
    sleep_end: Optional[str] = None
    steps: Optional[int] = None
    active_minutes: Optional[float] = None
    spo2: Optional[float] = None
    wrist_temp_deviation: Optional[float] = None


class HealthSamplesPayload(BaseModel):
    """Validated body for POST /health-metrics/samples (iOS HealthKit sync)."""

    samples: list[HealthMetricCreate] = Field(min_length=1)


class HealthMetricResponse(BaseModel):
    id: int
    date: datetime.date
    hrv_mean: Optional[float] = None
    hrv_std: Optional[float] = None
    resting_hr: Optional[float] = None
    sleep_hours: Optional[float] = None
    sleep_deep_min: Optional[float] = None
    sleep_rem_min: Optional[float] = None
    sleep_core_min: Optional[float] = None
    sleep_awake_min: Optional[float] = None
    sleep_deep_pct: Optional[float] = None
    sleep_rem_pct: Optional[float] = None
    sleep_efficiency: Optional[float] = None
    sleep_start: Optional[str] = None
    sleep_end: Optional[str] = None
    steps: Optional[int] = None
    active_minutes: Optional[float] = None
    spo2: Optional[float] = None
    wrist_temp_deviation: Optional[float] = None
    source: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
