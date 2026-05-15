from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class TrendPoint(BaseModel):
    date: str
    value: Optional[float]
    rolling_avg_7: Optional[float]


class TrendSeries(BaseModel):
    key: str
    label: str
    category: str
    points: list[TrendPoint]
    current: Optional[float]
    rolling_avg_7: Optional[float]
    delta_30d: Optional[float]


class TrendsResponse(BaseModel):
    series: list[TrendSeries]


class CorrelateRow(BaseModel):
    feature: str
    label: str
    category: str
    rho: float
    n: int
    best_lag: int


class CorrelatesResponse(BaseModel):
    outcome: str
    positive: list[CorrelateRow]
    negative: list[CorrelateRow]


class TreatmentResponseRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    treatment_id: int
    name: str
    type: str
    start_date: str
    end_date: Optional[str]
    baseline_mean: Optional[float]
    during_mean: Optional[float]
    after_mean: Optional[float]
    baseline_n: int
    during_n: int
    after_n: int
    delta_during_vs_baseline: Optional[float]


class TreatmentResponseList(BaseModel):
    outcome: str
    rows: list[TreatmentResponseRow]


class SleepNextDayPoint(BaseModel):
    date: str
    sleep_value: float
    next_day_outcome: float


class SleepNextDayResponse(BaseModel):
    outcome: str
    metric: str
    points: list[SleepNextDayPoint]
    rho: Optional[float]
    n: int
