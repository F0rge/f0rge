from __future__ import annotations

import datetime
from typing import Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import redis_client
from app.cache.keys import signals_key
from app.config import settings
from app.schemas.insights import TrendsResponse
from app.schemas.signals import (
    DayStripsResponse,
    DoseBinResponse,
    SignalsDriverResponse,
    SignalsMetaResponse,
    SignalsMirrorResponse,
    SignalsModelResponse,
    SignalsResponse,
    SignalsTodayResponse,
    SignalsTrendSeriesResponse,
    SignalsTrendsResponse,
    SignalsUnexplainedResponse,
    TodayCalibrationPointResponse,
    TodayContributionResponse,
    TrackerProposalResponse,
    UnexplainedEpisodeResponse,
)
from app.services.feature_matrix import build_feature_matrix
from app.services.insights import InsightsService
from app.services.signals.attribution import (
    AttributionContext,
    build_attribution_context,
    compute_calibration_series,
    compute_day_attribution,
)
from app.services.signals.baseline import WARMUP_DAYS, BaselineResult, compute_baseline_residuals
from app.services.signals.effects import (
    MIN_OBSERVED_DAYS,
    EffectResult,
    _extract_exposure_series,
    estimate_all_effects,
)
from app.services.signals.interactions import InteractionResult, compute_interactions
from app.services.signals.quality import ModelQuality, compute_model_quality, estimate_noise_floor
from app.services.signals.taxonomy import TaxonomyError, resolve_class
from app.services.signals.unexplained import UnexplainedResult, detect_unexplained
from app.services.stats import spearmanr
from app.utils.scales import SCALE_DIRECTION
from app.utils.dates import local_today
from f0rge_core.exceptions import ValidationError
from f0rge_db.tenant import current_user_id

SIGNALS_SCHEMA_VERSION = 1
CALIBRATION_SERIES_DAYS = 14
BAND_Z_80 = 1.282
BAND_LEVEL = 80
MIRROR_REASON = "Moves with the day rather than ahead of it"

_SKIP_MIRROR_SCAN = frozenset(
    {
        "date",
        "schema_version",
        "period_of_day",
        "overall",
        "sick",
        "photo_count",
        "ingredient_count",
        "stool_status",
        "bristol_type",
    }
)


def _humanize(col: str) -> str:
    label = col
    for prefix in ("sym_", "supp_", "hm_", "wx_"):
        if label.startswith(prefix):
            label = label[len(prefix) :]
            break
    if label.startswith("tx_") and label.endswith("_active"):
        label = label[3:-7]
    elif label.startswith("tx_"):
        label = label[3:]
    return label.replace("_", " ").title()


def _good_direction(feature: str) -> Optional[str]:
    if feature.startswith("sym_"):
        return "down"
    scale_dir = SCALE_DIRECTION.get(feature)
    if scale_dir == "higher_better":
        return "up"
    if scale_dir == "higher_worse":
        return "down"
    return None


def _coerce_numeric(val: object) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, bool):
        return float(val)
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _round_optional(value: Optional[float], places: int = 4) -> Optional[float]:
    if value is None:
        return None
    return round(value, places)


def _mirror_columns(columns: list[str]) -> list[str]:
    mirrors: list[str] = []
    for col in columns:
        if col in _SKIP_MIRROR_SCAN:
            continue
        try:
            if resolve_class(col, lag=0) == "mirror":
                mirrors.append(col)
        except TaxonomyError:
            continue
    return sorted(mirrors)


def _usable_overall_values(
    baseline: BaselineResult,
    rows: list[dict],
    columns: list[str],
    effect: EffectResult,
) -> tuple[list[float], list[float], np.ndarray]:
    lag = effect.lag
    residuals, exposure, valid = _extract_exposure_series(rows, baseline, effect.column, lag)
    exposed_vals: list[float] = []
    unexposed_vals: list[float] = []
    bottom_cut: float | None = None
    if effect.shape == "linear":
        usable_x = [float(exposure[i]) for i in range(len(exposure)) if valid[i]]
        if len(usable_x) >= 6:
            bottom_cut = float(np.percentile(usable_x, 33.33))
    for local_i in range(len(baseline.dates) - WARMUP_DAYS):
        idx = WARMUP_DAYS + local_i
        overall = baseline.overall[idx]
        if overall is None or not valid[local_i]:
            continue
        if effect.exposed_mask is not None and effect.exposed_mask[local_i]:
            exposed_vals.append(float(overall))
        elif effect.shape == "linear":
            if bottom_cut is not None and float(exposure[local_i]) <= bottom_cut:
                unexposed_vals.append(float(overall))
        else:
            unexposed_vals.append(float(overall))
    mask = (
        np.asarray(effect.exposed_mask, dtype=bool)
        if effect.exposed_mask is not None
        else np.zeros(len(baseline.dates) - WARMUP_DAYS, dtype=bool)
    )
    return exposed_vals, unexposed_vals, mask


def _mean_or_none(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _build_dose_table(
    effect: EffectResult,
    baseline: BaselineResult,
    rows: list[dict],
    columns: list[str],
) -> list[DoseBinResponse]:
    exposed_vals, unexposed_vals, _ = _usable_overall_values(baseline, rows, columns, effect)
    if effect.shape == "linear":
        lag = effect.lag
        _, exposure, valid = _extract_exposure_series(rows, baseline, effect.column, lag)
        usable_x = [float(exposure[i]) for i in range(len(exposure)) if valid[i]]
        if len(usable_x) < 6:
            return [
                DoseBinResponse(
                    label="exposed", n=len(exposed_vals), mean=_mean_or_none(exposed_vals)
                ),
                DoseBinResponse(
                    label="unexposed", n=len(unexposed_vals), mean=_mean_or_none(unexposed_vals)
                ),
            ]
        p33, p67 = float(np.percentile(usable_x, 33.33)), float(np.percentile(usable_x, 66.67))
        bins: dict[str, list[float]] = {"bottom third": [], "middle third": [], "top third": []}
        for local_i in range(len(baseline.dates) - WARMUP_DAYS):
            idx = WARMUP_DAYS + local_i
            overall = baseline.overall[idx]
            if overall is None or not valid[local_i]:
                continue
            x_val = float(exposure[local_i])
            if x_val <= p33:
                bins["bottom third"].append(float(overall))
            elif x_val <= p67:
                bins["middle third"].append(float(overall))
            else:
                bins["top third"].append(float(overall))
        return [
            DoseBinResponse(label=label, n=len(vals), mean=_mean_or_none(vals))
            for label, vals in bins.items()
        ]

    if effect.shape == "threshold" and effect.threshold_c is not None:
        return [
            DoseBinResponse(
                label=f"at/above {effect.threshold_c:.2g}",
                n=len(exposed_vals),
                mean=_mean_or_none(exposed_vals),
            ),
            DoseBinResponse(
                label=f"below {effect.threshold_c:.2g}",
                n=len(unexposed_vals),
                mean=_mean_or_none(unexposed_vals),
            ),
        ]

    return [
        DoseBinResponse(label="exposed", n=len(exposed_vals), mean=_mean_or_none(exposed_vals)),
        DoseBinResponse(
            label="unexposed", n=len(unexposed_vals), mean=_mean_or_none(unexposed_vals)
        ),
    ]


def _build_day_strips(
    effect: EffectResult,
    baseline: BaselineResult,
    rows: list[dict],
    columns: list[str],
) -> DayStripsResponse:
    exposed_vals, unexposed_vals, _ = _usable_overall_values(baseline, rows, columns, effect)
    return DayStripsResponse(exposed=exposed_vals, unexposed=unexposed_vals)


def _driver_from_effect(
    effect: EffectResult,
    baseline: BaselineResult,
    rows: list[dict],
    columns: list[str],
) -> SignalsDriverResponse:
    return SignalsDriverResponse(
        feature=effect.column,
        label=_humanize(effect.column),
        feature_class=effect.feature_class,
        shape=effect.shape,
        theta_hat=_round_optional(effect.theta_hat),
        ci_low=_round_optional(effect.ci_lower),
        ci_high=_round_optional(effect.ci_upper),
        tier=effect.tier,
        reason=effect.reason,
        exposed_days=effect.exposed_days,
        unexposed_days=effect.unexposed_days,
        exposed_runs=effect.exposed_runs,
        dose_table=_build_dose_table(effect, baseline, rows, columns),
        day_strips=_build_day_strips(effect, baseline, rows, columns),
        good_direction=_good_direction(effect.column),
        se_ratio=_round_optional(effect.se_ratio),
    )


def _interaction_masks(
    inter: InteractionResult,
    effects: list[EffectResult],
    n_usable: int,
) -> tuple[np.ndarray, np.ndarray] | None:
    effect_a = next((e for e in effects if e.column == inter.column_a), None)
    effect_b = next((e for e in effects if e.column == inter.column_b), None)
    if (
        effect_a is None
        or effect_b is None
        or effect_a.exposed_mask is None
        or effect_b.exposed_mask is None
    ):
        return None
    if len(effect_a.exposed_mask) != n_usable or len(effect_b.exposed_mask) != n_usable:
        return None
    mask_a = np.asarray(effect_a.exposed_mask, dtype=bool)
    mask_b = np.asarray(effect_b.exposed_mask, dtype=bool)
    return mask_a, mask_b


def _interaction_dose_table(
    inter: InteractionResult,
    baseline: BaselineResult,
    mask_a: np.ndarray,
    mask_b: np.ndarray,
) -> list[DoseBinResponse]:
    neither: list[float] = []
    a_only: list[float] = []
    b_only: list[float] = []
    both: list[float] = []
    for local_i in range(len(baseline.dates) - WARMUP_DAYS):
        idx = WARMUP_DAYS + local_i
        overall = baseline.overall[idx]
        if overall is None:
            continue
        val = float(overall)
        if mask_a[local_i] and mask_b[local_i]:
            both.append(val)
        elif mask_a[local_i]:
            a_only.append(val)
        elif mask_b[local_i]:
            b_only.append(val)
        else:
            neither.append(val)
    return [
        DoseBinResponse(label="Neither", n=len(neither), mean=_mean_or_none(neither)),
        DoseBinResponse(label="A only", n=len(a_only), mean=_mean_or_none(a_only)),
        DoseBinResponse(label="B only", n=len(b_only), mean=_mean_or_none(b_only)),
        DoseBinResponse(label="Both", n=len(both), mean=_mean_or_none(both)),
    ]


def _interaction_day_strips(
    baseline: BaselineResult,
    mask_a: np.ndarray,
    mask_b: np.ndarray,
) -> DayStripsResponse:
    exposed: list[float] = []
    unexposed: list[float] = []
    for local_i in range(len(baseline.dates) - WARMUP_DAYS):
        idx = WARMUP_DAYS + local_i
        overall = baseline.overall[idx]
        if overall is None:
            continue
        val = float(overall)
        if mask_a[local_i] and mask_b[local_i]:
            exposed.append(val)
        elif not mask_a[local_i] and not mask_b[local_i]:
            unexposed.append(val)
    return DayStripsResponse(exposed=exposed, unexposed=unexposed)


def _driver_from_interaction(
    inter: InteractionResult,
    baseline: BaselineResult,
    effects: list[EffectResult],
) -> Optional[SignalsDriverResponse]:
    feature = f"{inter.column_a}_x_{inter.column_b}"
    n_usable = len(baseline.dates) - WARMUP_DAYS
    masks = _interaction_masks(inter, effects, n_usable)
    if masks is None:
        return None
    mask_a, mask_b = masks
    co_exposed = int((mask_a & mask_b).sum())
    unexposed_days = int((~mask_a & ~mask_b).sum())
    return SignalsDriverResponse(
        feature=feature,
        label=f"{_humanize(inter.column_a)} × {_humanize(inter.column_b)}",
        feature_class="lever",
        shape="interaction",
        theta_hat=_round_optional(inter.excess),
        ci_low=_round_optional(inter.ci_lower),
        ci_high=_round_optional(inter.ci_upper),
        tier=inter.tier,
        reason=inter.reason,
        exposed_days=co_exposed,
        unexposed_days=unexposed_days,
        exposed_runs=inter.co_exposed_runs,
        dose_table=_interaction_dose_table(inter, baseline, mask_a, mask_b),
        day_strips=_interaction_day_strips(baseline, mask_a, mask_b),
        good_direction=None,
        se_ratio=None,
    )


def _build_mirrors(
    rows: list[dict],
    columns: list[str],
    baseline: BaselineResult,
    outcome: str,
) -> list[SignalsMirrorResponse]:
    date_to_row = {str(r["date"]): r for r in rows}
    y_vals: list[Optional[float]] = []
    x_by_col: dict[str, list[Optional[float]]] = {col: [] for col in _mirror_columns(columns)}
    for date_str in baseline.dates[WARMUP_DAYS:]:
        row = date_to_row.get(date_str, {})
        y_vals.append(_coerce_numeric(row.get(outcome)))
        for col in x_by_col:
            x_by_col[col].append(_coerce_numeric(row.get(col)))

    mirrors: list[SignalsMirrorResponse] = []
    for col, x_vals in x_by_col.items():
        rho, n = spearmanr(x_vals, y_vals)
        mirrors.append(
            SignalsMirrorResponse(
                feature=col,
                label=_humanize(col),
                rho=rho,
                n=n,
                reason=MIRROR_REASON,
            )
        )
    mirrors.sort(key=lambda m: (-(abs(m.rho) if m.rho is not None else -1.0), m.feature))
    return mirrors


def _model_block(
    quality: Optional[ModelQuality],
    unexplained: UnexplainedResult,
) -> SignalsModelResponse:
    if quality is None:
        return SignalsModelResponse(
            relearning=unexplained.relearning,
            relearning_message=unexplained.relearning_message or None,
        )
    return SignalsModelResponse(
        mae=_round_optional(quality.mae),
        baseline_mae=_round_optional(quality.baseline_mae),
        noise_floor_mae=_round_optional(quality.noise_floor_mae),
        noise_sd=_round_optional(quality.noise_sd),
        skill=_round_optional(quality.skill),
        holdout_rmse=_round_optional(quality.holdout_rmse),
        holdout_r2=_round_optional(quality.holdout_r2),
        r2_basis=quality.r2_basis,
        relearning=unexplained.relearning,
        relearning_message=unexplained.relearning_message or None,
    )


def _today_block(
    rows: list[dict],
    columns: list[str],
    baseline: BaselineResult,
    ctx: AttributionContext,
    quality: Optional[ModelQuality],
) -> SignalsTodayResponse:
    if not baseline.dates:
        return SignalsTodayResponse()
    if baseline.dates[-1] != local_today().isoformat():
        return SignalsTodayResponse()
    day_index = len(baseline.dates) - 1
    day = compute_day_attribution(day_index, baseline, ctx)
    holdout_rmse = quality.holdout_rmse if quality is not None else 0.77
    band_half = BAND_Z_80 * holdout_rmse
    predicted_display = day.display_predicted
    calibration = compute_calibration_series(rows, columns, baseline, ctx)
    if not calibration:
        cal_points: list[TodayCalibrationPointResponse] = []
    else:
        tail = calibration[-CALIBRATION_SERIES_DAYS:]
        cal_points = [
            TodayCalibrationPointResponse(
                date=point.date,
                predicted=point.display_predicted,
                actual=point.actual,
            )
            for point in tail
        ]
    contributions = [
        TodayContributionResponse(
            label=row.label,
            detail=row.category,
            display_value=row.display_value,
            driver_id=row.driver_id,
        )
        for row in day.contributions
    ]
    return SignalsTodayResponse(
        baseline=day.display_baseline,
        contributions=contributions,
        predicted=predicted_display,
        band_low=_round_optional(predicted_display - band_half, 1),
        band_high=_round_optional(predicted_display + band_half, 1),
        band_level=BAND_LEVEL,
        actual=day.actual,
        residual=day.display_residual,
        calibration_series=cal_points,
    )


def _unexplained_block(result: UnexplainedResult) -> SignalsUnexplainedResponse:
    return SignalsUnexplainedResponse(
        unexplained_bad=[
            UnexplainedEpisodeResponse(
                dates=ep.dates,
                start_date=ep.start_date,
                end_date=ep.end_date,
                direction=ep.direction,
                max_abs_residual=ep.max_abs_residual,
            )
            for ep in result.unexplained_bad
        ],
        unexplained_good=[
            UnexplainedEpisodeResponse(
                dates=ep.dates,
                start_date=ep.start_date,
                end_date=ep.end_date,
                direction=ep.direction,
                max_abs_residual=ep.max_abs_residual,
            )
            for ep in result.unexplained_good
        ],
        couldnt_score=result.couldnt_score,
        relearning=result.relearning,
        relearning_message=result.relearning_message,
        tracker_proposals=[
            TrackerProposalResponse(
                tracker_id=p.tracker_id,
                label=p.label,
                days_covered=p.days_covered,
            )
            for p in result.tracker_proposals
        ],
    )


def _trends_block(trends: TrendsResponse) -> SignalsTrendsResponse:
    return SignalsTrendsResponse(
        series=[
            SignalsTrendSeriesResponse(
                key=series.key,
                label=series.label,
                category=series.category,
                points=series.points,
                current=series.current,
                rolling_avg_7=series.rolling_avg_7,
                delta_30d=series.delta_30d,
                good_direction=_good_direction(series.key),
            )
            for series in trends.series
        ]
    )


def _empty_unexplained() -> UnexplainedResult:
    return UnexplainedResult(
        unexplained_bad=[],
        unexplained_good=[],
        couldnt_score=[],
        relearning=False,
        relearning_message="",
        tracker_proposals=[],
        sigma_resid=0.0,
    )


class SignalsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.insights = InsightsService(db)

    async def _validate_outcome(self, outcome: str, columns: list[str]) -> None:
        allowed = await self.insights._allowed_outcomes(columns)
        if outcome not in allowed:
            raise ValidationError(f"unknown outcome: {outcome!r}")

    def _insufficient_reason(self, days_usable: int) -> str:
        return (
            f"Need at least {MIN_OBSERVED_DAYS} usable days after the "
            f"{WARMUP_DAYS}-day warm-up; have {days_usable}."
        )

    async def _build_payload(
        self,
        outcome: str,
        start: Optional[datetime.date],
        end: Optional[datetime.date],
    ) -> SignalsResponse:
        rows, columns = await build_feature_matrix(self.db, start, end)
        await self._validate_outcome(outcome, columns)

        baseline = compute_baseline_residuals(rows, columns, outcome=outcome)
        diag = baseline.diagnostics
        insufficient = diag.days_usable < MIN_OBSERVED_DAYS
        start_str = start.isoformat() if start is not None else None
        end_str = end.isoformat() if end is not None else None

        meta = SignalsMetaResponse(
            days_total=diag.days_total,
            days_usable=diag.days_usable,
            warmup=diag.warmup_days,
            drop_reasons=dict(diag.drop_reasons),
            insufficient_data=insufficient,
            insufficient_reason=self._insufficient_reason(diag.days_usable)
            if insufficient
            else None,
            outcome=outcome,
            start=start_str,
            end=end_str,
        )

        trends = _trends_block(await self.insights.compute_trends(start, end))
        mirrors = _build_mirrors(rows, columns, baseline, outcome)

        if insufficient:
            unexplained = _empty_unexplained()
            return SignalsResponse(
                meta=meta,
                model=SignalsModelResponse(),
                today=SignalsTodayResponse(),
                drivers=[],
                mirrors=mirrors,
                unexplained=_unexplained_block(unexplained),
                trends=trends,
            )

        effects = estimate_all_effects(rows, columns, baseline)
        eligible = [e.column for e in effects if e.tier in ("established", "emerging")]
        interactions = compute_interactions(
            rows,
            columns,
            baseline,
            eligible_columns=eligible or None,
        )
        ctx = build_attribution_context(
            rows, columns, baseline, effects=effects, interactions=interactions
        )
        noise = estimate_noise_floor(rows, columns, baseline, effects)
        quality = compute_model_quality(rows, columns, baseline, ctx, noise, effects)
        unexplained = detect_unexplained(rows, columns, baseline, ctx)

        drivers: list[SignalsDriverResponse] = []
        for effect in effects:
            if effect.feature_class == "mirror" or effect.tier == "mirror":
                continue
            if effect.column.startswith("sym_"):
                continue
            try:
                if resolve_class(effect.column, lag=0) == "mirror":
                    continue
            except TaxonomyError:
                continue
            drivers.append(_driver_from_effect(effect, baseline, rows, columns))
        for inter in interactions:
            if inter.tier == "insufficient" or inter.excess is None:
                continue
            driver = _driver_from_interaction(inter, baseline, effects)
            if driver is not None:
                drivers.append(driver)

        drivers.sort(
            key=lambda d: (-(abs(d.theta_hat) if d.theta_hat is not None else -1.0), d.feature)
        )

        return SignalsResponse(
            meta=meta,
            model=_model_block(quality, unexplained),
            today=_today_block(rows, columns, baseline, ctx, quality),
            drivers=drivers,
            mirrors=mirrors,
            unexplained=_unexplained_block(unexplained),
            trends=trends,
        )

    async def compute(
        self,
        outcome: str,
        start: Optional[datetime.date] = None,
        end: Optional[datetime.date] = None,
    ) -> SignalsResponse:
        user_id = current_user_id()
        cache_key = signals_key(user_id, outcome, start, end)
        cached = await redis_client.get(cache_key)
        if cached is not None:
            return SignalsResponse.model_validate(redis_client.loads_json(cached))

        payload = await self._build_payload(outcome, start, end)
        await redis_client.set(
            cache_key,
            redis_client.dumps_json(payload.model_dump(mode="json", by_alias=True)),
            settings.cache_ttl_signals_seconds,
        )
        return payload
