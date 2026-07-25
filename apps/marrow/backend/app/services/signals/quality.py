from __future__ import annotations

import datetime
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from app.services.signals.attribution import (
    AttributionContext,
    build_attribution_context,
    compute_day_attribution,
)
from app.services.signals.baseline import WARMUP_DAYS, BaselineResult, compute_baseline_residuals
from app.services.signals.effects import (
    CV_FOLDS,
    EffectResult,
    _contiguous_folds,
    estimate_all_effects,
)
from app.services.signals.interactions import compute_interactions

MAE_FROM_SD = float(np.sqrt(2.0 / np.pi))  # §The noise floor — noise_floor_mae = σ_noise·√(2/π)
DISAGREE_THRESHOLD = 0.1  # §The noise floor — take larger when estimators disagree
MIN_CELL_DAYS = 3  # §The noise floor — within-cell estimator minimum
R2_BASIS: Literal["variance"] = "variance"  # signals_method.md D1 — R² vs outcome variance


@dataclass
class NoiseFloorEstimate:
    noise_sd: float
    noise_floor_mae: float
    ar1_noise_sd: float
    ar1_noise_floor_mae: float
    within_cell_noise_sd: float
    within_cell_noise_floor_mae: float
    estimator_selected: Literal["ar1", "within_cell", "agree"]


@dataclass
class ModelQuality:
    mae: float
    baseline_mae: float
    noise_floor_mae: float
    noise_sd: float
    skill: float
    holdout_rmse: float
    holdout_r2: float
    r2_basis: Literal["variance"]


def _mae_from_sd(sd: float) -> float:
    return sd * MAE_FROM_SD


def _autocorr(series: np.ndarray, lag: int) -> float:
    n = len(series)
    if lag <= 0 or n <= lag + 1:
        return 0.0
    y0 = series[:-lag]
    y1 = series[lag:]
    if np.std(y0) == 0.0 or np.std(y1) == 0.0:
        return 0.0
    return float(np.corrcoef(y0, y1)[0, 1])


def estimate_noise_floor_ar1(overall: np.ndarray) -> tuple[float, float]:
    """AR(1) + white noise estimator — ``signals_method.md`` §The noise floor."""
    if overall.size < 4:
        return 0.0, 0.0
    sigma_y = float(np.std(overall, ddof=1))
    if sigma_y == 0.0:
        return 0.0, 0.0
    rho1 = _autocorr(overall, 1)
    rho2 = _autocorr(overall, 2)
    if abs(rho2) < 1e-12:
        lambda_hat = 0.0
    else:
        lambda_hat = float(np.clip((rho1**2) / rho2, 0.0, 1.0))
    noise_sd = sigma_y * float(np.sqrt(max(0.0, 1.0 - lambda_hat)))
    return noise_sd, _mae_from_sd(noise_sd)


def _binarise_exposure_vector(
    effects: list[EffectResult],
    local_index: int,
) -> tuple[int, ...]:
    bits: list[int] = []
    for effect in effects:
        if effect.exposed_mask is None or local_index >= len(effect.exposed_mask):
            bits.append(0)
        else:
            bits.append(1 if effect.exposed_mask[local_index] else 0)
    return tuple(bits)


def estimate_noise_floor_within_cell(
    rows: list[dict],
    baseline: BaselineResult,
    effects: list[EffectResult],
) -> tuple[float, float]:
    """Weekday × binarised-exposure within-cell SD — ``signals_method.md`` §The noise floor."""
    date_to_row = {str(r["date"]): r for r in rows}
    usable = list(range(WARMUP_DAYS, len(baseline.dates)))
    cells: dict[tuple[int, tuple[int, ...]], list[float]] = {}
    for idx in usable:
        row = date_to_row.get(baseline.dates[idx])
        if row is None:
            continue
        overall = baseline.overall[idx]
        if overall is None:
            continue
        dow = _parse_date(baseline.dates[idx]).weekday()
        local_i = idx - WARMUP_DAYS
        key = (dow, _binarise_exposure_vector(effects, local_i))
        cells.setdefault(key, []).append(float(overall))

    variances: list[float] = []
    weights: list[float] = []
    for values in cells.values():
        if len(values) < MIN_CELL_DAYS:
            continue
        arr = np.asarray(values, dtype=float)
        variances.append(float(np.var(arr, ddof=1)))
        weights.append(float(len(arr)))

    if not variances:
        return 0.0, 0.0
    pooled_var = float(np.average(variances, weights=weights))
    noise_sd = float(np.sqrt(max(0.0, pooled_var)))
    return noise_sd, _mae_from_sd(noise_sd)


def _parse_date(date_val: str) -> datetime.date:
    return datetime.date.fromisoformat(str(date_val))


def estimate_noise_floor(
    rows: list[dict],
    columns: list[str],
    baseline: BaselineResult | None = None,
    effects: list[EffectResult] | None = None,
) -> NoiseFloorEstimate:
    """Combine AR(1) and within-cell estimators; report the larger when they disagree."""
    base = baseline if baseline is not None else compute_baseline_residuals(rows, columns)
    usable = list(range(WARMUP_DAYS, len(base.dates)))
    overall = np.asarray(
        [float(base.overall[i]) for i in usable if base.overall[i] is not None],
        dtype=float,
    )
    ar1_sd, ar1_mae = estimate_noise_floor_ar1(overall)

    from app.services.signals.effects import estimate_all_effects

    effs = effects if effects is not None else estimate_all_effects(rows, columns, base)
    eligible = [
        e for e in effs if e.tier not in ("mirror", "insufficient") and e.exposed_mask is not None
    ]
    cell_sd, cell_mae = estimate_noise_floor_within_cell(rows, base, eligible)

    if abs(ar1_sd - cell_sd) > DISAGREE_THRESHOLD:
        if ar1_sd >= cell_sd:
            selected: Literal["ar1", "within_cell", "agree"] = "ar1"
            noise_sd, noise_mae = ar1_sd, ar1_mae
        else:
            selected = "within_cell"
            noise_sd, noise_mae = cell_sd, cell_mae
    else:
        selected = "agree"
        noise_sd, noise_mae = ar1_sd, ar1_mae

    return NoiseFloorEstimate(
        noise_sd=noise_sd,
        noise_floor_mae=noise_mae,
        ar1_noise_sd=ar1_sd,
        ar1_noise_floor_mae=ar1_mae,
        within_cell_noise_sd=cell_sd,
        within_cell_noise_floor_mae=cell_mae,
        estimator_selected=selected,
    )


def _masked_baseline(baseline: BaselineResult, masked_positions: set[int]) -> BaselineResult:
    residuals = list(baseline.residuals)
    for pos in masked_positions:
        residuals[pos] = None
    return replace(baseline, residuals=residuals)


def _train_only_context(
    ctx: AttributionContext,
    train_local: np.ndarray,
) -> AttributionContext:
    exposure_means: dict[str, float] = {}
    for effect in ctx.effects:
        if effect.exposed_mask is None:
            continue
        mask = np.asarray(effect.exposed_mask, dtype=float)
        train_vals = mask[train_local]
        exposure_means[effect.column] = float(np.mean(train_vals)) if train_vals.size else 0.0

    interaction_both_means: dict[tuple[str, str], float] = {}
    for key, mask in ctx.interaction_masks.items():
        train_vals = mask[train_local].astype(float)
        interaction_both_means[key] = float(np.mean(train_vals)) if train_vals.size else 0.0

    return replace(
        ctx,
        exposure_means=exposure_means,
        interaction_both_means=interaction_both_means,
    )


def _model_predictions(
    rows: list[dict],
    columns: list[str],
    baseline: BaselineResult,
    ctx: AttributionContext,
) -> tuple[np.ndarray, np.ndarray]:
    """Out-of-fold full-model predictions for holdout RMSE/R²."""
    usable = ctx.usable_indices
    n_usable = len(usable)
    if n_usable == 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    folds = _contiguous_folds(n_usable, CV_FOLDS)
    actuals: list[float] = []
    predicted: list[float] = []

    for fold_id in range(CV_FOLDS):
        test_local = folds == fold_id
        train_local = ~test_local
        test_global = [usable[i] for i in range(n_usable) if test_local[i]]
        train_base = _masked_baseline(baseline, set(test_global))

        effects = estimate_all_effects(rows, columns, train_base)
        eligible = [e.column for e in effects if e.tier in ("established", "emerging")]
        interactions = compute_interactions(
            rows,
            columns,
            train_base,
            eligible_columns=eligible or None,
        )
        fold_ctx = build_attribution_context(
            rows,
            columns,
            train_base,
            effects=effects,
            interactions=interactions,
        )
        fold_ctx = _train_only_context(fold_ctx, train_local)

        for global_idx in test_global:
            day = compute_day_attribution(global_idx, baseline, fold_ctx)
            if day.actual is None:
                continue
            actuals.append(float(day.actual))
            predicted.append(day.predicted)

    return np.asarray(actuals, dtype=float), np.asarray(predicted, dtype=float)


def _in_sample_predictions(
    baseline: BaselineResult,
    ctx: AttributionContext,
) -> tuple[np.ndarray, np.ndarray]:
    actuals: list[float] = []
    predicted: list[float] = []
    for idx in ctx.usable_indices:
        day = compute_day_attribution(idx, baseline, ctx)
        if day.actual is None:
            continue
        actuals.append(float(day.actual))
        predicted.append(day.predicted)
    return np.asarray(actuals, dtype=float), np.asarray(predicted, dtype=float)


def compute_model_quality(
    rows: list[dict],
    columns: list[str],
    baseline: BaselineResult | None = None,
    ctx: AttributionContext | None = None,
    noise: NoiseFloorEstimate | None = None,
    effects: list[EffectResult] | None = None,
) -> ModelQuality:
    """Model-quality block — MAE, skill, holdout RMSE/R² with explicit ``r2_basis``."""
    base = baseline if baseline is not None else compute_baseline_residuals(rows, columns)
    context = ctx if ctx is not None else build_attribution_context(rows, columns, base)
    floor = noise if noise is not None else estimate_noise_floor(rows, columns, base, effects)

    actuals, predicted = _in_sample_predictions(base, context)
    errors = actuals - predicted
    mae = float(np.mean(np.abs(errors))) if errors.size else 0.0

    holdout_actuals, holdout_predicted = _model_predictions(rows, columns, base, context)
    holdout_errors = holdout_actuals - holdout_predicted
    holdout_rmse = float(np.sqrt(np.mean(holdout_errors**2))) if holdout_errors.size else 0.0

    usable_residuals = [
        float(base.residuals[i]) for i in context.usable_indices if base.residuals[i] is not None
    ]
    baseline_mae = float(np.mean(np.abs(usable_residuals))) if usable_residuals else 0.0

    var_y = float(np.var(holdout_actuals, ddof=1)) if holdout_actuals.size > 1 else 0.0
    if var_y > 0.0:
        holdout_r2 = float(1.0 - np.mean(holdout_errors**2) / var_y)
    else:
        holdout_r2 = 0.0

    denom = baseline_mae - floor.noise_floor_mae
    if abs(denom) < 1e-12:
        skill = 0.0
    else:
        skill = float((baseline_mae - mae) / denom)

    return ModelQuality(
        mae=mae,
        baseline_mae=baseline_mae,
        noise_floor_mae=floor.noise_floor_mae,
        noise_sd=floor.noise_sd,
        skill=skill,
        holdout_rmse=holdout_rmse,
        holdout_r2=holdout_r2,
        r2_basis=R2_BASIS,
    )
