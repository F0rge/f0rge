from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.insights import TrendPoint


class SignalsMetaResponse(BaseModel):
    days_total: int
    days_usable: int
    warmup: int
    drop_reasons: dict[str, int]
    insufficient_data: bool
    insufficient_reason: Optional[str] = None
    outcome: str
    start: Optional[str] = None
    end: Optional[str] = None


class SignalsModelResponse(BaseModel):
    mae: Optional[float] = None
    baseline_mae: Optional[float] = None
    noise_floor_mae: Optional[float] = None
    noise_sd: Optional[float] = None
    skill: Optional[float] = None
    holdout_rmse: Optional[float] = None
    holdout_r2: Optional[float] = None
    r2_basis: Optional[str] = None
    relearning: bool = False
    relearning_message: Optional[str] = None


class TodayContributionResponse(BaseModel):
    label: str
    detail: Optional[str] = None
    display_value: float
    driver_id: str


class TodayCalibrationPointResponse(BaseModel):
    date: str
    predicted: float
    actual: Optional[float]


class SignalsTodayResponse(BaseModel):
    baseline: Optional[float] = None
    contributions: list[TodayContributionResponse] = Field(default_factory=list)
    predicted: Optional[float] = None
    band_low: Optional[float] = None
    band_high: Optional[float] = None
    band_level: Optional[int] = None
    actual: Optional[float] = None
    residual: Optional[float] = None
    calibration_series: list[TodayCalibrationPointResponse] = Field(default_factory=list)


class DoseBinResponse(BaseModel):
    label: str
    n: int
    mean: Optional[float]


class DayStripsResponse(BaseModel):
    exposed: list[Optional[float]]
    unexposed: list[Optional[float]]


class SignalsDriverResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    feature: str
    label: str
    feature_class: str = Field(alias="class")
    shape: str
    theta_hat: Optional[float]
    ci_low: Optional[float]
    ci_high: Optional[float]
    tier: str
    reason: str
    exposed_days: int
    unexposed_days: int
    exposed_runs: int
    dose_table: list[DoseBinResponse]
    day_strips: DayStripsResponse
    good_direction: Optional[str]
    se_ratio: Optional[float]


class SignalsMirrorResponse(BaseModel):
    feature: str
    label: str
    rho: Optional[float]
    n: int
    reason: str


class UnexplainedEpisodeResponse(BaseModel):
    dates: list[str]
    start_date: str
    end_date: str
    direction: str
    max_abs_residual: float


class TrackerProposalResponse(BaseModel):
    tracker_id: str
    label: str
    days_covered: int


class SignalsUnexplainedResponse(BaseModel):
    unexplained_bad: list[UnexplainedEpisodeResponse]
    unexplained_good: list[UnexplainedEpisodeResponse]
    couldnt_score: list[str]
    relearning: bool
    relearning_message: str
    tracker_proposals: list[TrackerProposalResponse]


class SignalsTrendSeriesResponse(BaseModel):
    key: str
    label: str
    category: str
    points: list[TrendPoint]
    current: Optional[float]
    rolling_avg_7: Optional[float]
    delta_30d: Optional[float]
    good_direction: Optional[str]


class SignalsTrendsResponse(BaseModel):
    series: list[SignalsTrendSeriesResponse]


class SignalsResponse(BaseModel):
    meta: SignalsMetaResponse
    model: SignalsModelResponse
    today: SignalsTodayResponse
    drivers: list[SignalsDriverResponse]
    mirrors: list[SignalsMirrorResponse]
    unexplained: SignalsUnexplainedResponse
    trends: SignalsTrendsResponse
