from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.services.signals.baseline import WARMUP_DAYS, BaselineResult, compute_baseline_residuals
from app.services.signals.taxonomy import FeatureClass, FeatureShape, resolve_class, resolve_shape

# Layer 3 constants — see apps/marrow/backend/docs/signals_method.md §Layer 3
BOOTSTRAP_B = 2000  # §Layer 3 — moving-block bootstrap resamples
BLOCK_LENGTH_DAYS = 7  # §Layer 3 — circular block length L
CV_FOLDS = 5  # §Layer 3 — time-blocked K-fold stability
THRESHOLD_PERCENTILES = (20, 25, 33, 50, 67, 75, 80)  # §Layer 3 — in-fold threshold grid
FOLD_AGREEMENT_FRAC = 0.5  # §Layer 3 — |θ̂ₖ| ≥ 0.5·|θ̂_full|
SE_RATIO_FORCE_WATCHING = 1.5  # §Layer 3 — bootstrap/naive SE diagnostic cap
EMERGING_ZERO_MARGIN = 0.10  # §Layer 3 — zero-side bound within 0.10 of 0

MIN_OBSERVED_DAYS = 21  # §Layer 3 — preconditions (softened from 30)
MIN_GROUP_DAYS = 5  # §Layer 3 — exposed/unexposed minimum
MIN_EXPOSED_RUNS = 2  # §Layer 3 — consecutive exposed stretches

ESTABLISHED_F = 5  # raised from 4 after permutation null (signals_null_calibration.md)
ESTABLISHED_X = 15
ESTABLISHED_R = 4
ESTABLISHED_THETA = 0.25  # raised from 0.20 after permutation null (signals_null_calibration.md)

EMERGING_F = 3
EMERGING_X = 10
EMERGING_R = 3
EMERGING_THETA = 0.15

CI_ALPHA = 0.05

EffectTier = Literal["established", "emerging", "watching", "insufficient", "mirror"]

_ACTIVITY_LAG_COLUMNS = frozenset({"hm_steps", "hm_active_minutes"})
_PHYSIOLOGY_LAG_COLUMNS = frozenset(
    {
        "hm_hrv_mean",
        "hm_hrv_std",
        "hm_resting_hr",
        "hm_spo2",
        "hm_wrist_temp_deviation",
    }
)


@dataclass
class EffectResult:
    column: str
    lag: int
    feature_class: FeatureClass
    shape: FeatureShape
    tier: EffectTier
    reason: str
    theta_hat: float | None
    ci_lower: float | None
    ci_upper: float | None
    bootstrap_se: float | None
    naive_se: float | None
    se_ratio: float | None
    fold_count: int
    exposed_days: int
    unexposed_days: int
    exposed_runs: int
    observed_days: int
    threshold_c: float | None = None
    exposed_mask: list[bool] | None = None


def preferred_lag(column: str) -> int:
    """Preferred lag per taxonomy; no max-over-lags search."""
    if column in _ACTIVITY_LAG_COLUMNS or column in _PHYSIOLOGY_LAG_COLUMNS:
        return 1
    if column == "sleep_quality":
        return 1
    return 0


def _parse_date(date_val: str | datetime.date) -> datetime.date:
    if isinstance(date_val, datetime.date):
        return date_val
    return datetime.date.fromisoformat(str(date_val))


def _usable_positions(baseline: BaselineResult) -> list[int]:
    return list(range(WARMUP_DAYS, len(baseline.dates)))


def _extract_exposure_series(
    rows: list[dict],
    baseline: BaselineResult,
    column: str,
    lag: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (residuals, exposure values, valid mask) aligned to usable days."""
    sorted_rows = sorted(rows, key=lambda r: _parse_date(r["date"]))
    date_to_row = {str(r["date"]): r for r in sorted_rows}
    raw: list[float | None] = []
    for date_str in baseline.dates:
        row = date_to_row.get(date_str)
        if row is None:
            raw.append(None)
            continue
        val = row.get(column)
        if val is None:
            raw.append(None)
        elif isinstance(val, bool):
            raw.append(1.0 if val else 0.0)
        elif isinstance(val, (int, float)):
            raw.append(float(val))
        else:
            raw.append(None)

    if lag > 0:
        lagged: list[float | None] = [None] * len(raw)
        for i in range(lag, len(raw)):
            lagged[i] = raw[i - lag]
        raw = lagged

    usable = _usable_positions(baseline)
    n = len(usable)
    r_out = np.full(n, np.nan)
    x = np.full(n, np.nan)
    valid = np.zeros(n, dtype=bool)

    for local_i, pos in enumerate(usable):
        res = baseline.residuals[pos]
        if res is None:
            continue
        r_out[local_i] = float(res)
        v = raw[pos]
        if v is not None:
            x[local_i] = v
            valid[local_i] = True

    return r_out, x, valid


def _count_runs(exposed: np.ndarray) -> int:
    if exposed.size == 0:
        return 0
    runs = 0
    in_run = False
    for val in exposed:
        if val and not in_run:
            runs += 1
            in_run = True
        elif not val:
            in_run = False
    return runs


def _contrast(residuals: np.ndarray, exposed: np.ndarray) -> float:
    if exposed.sum() == 0 or (~exposed).sum() == 0:
        return 0.0
    return float(np.mean(residuals[exposed]) - np.mean(residuals[~exposed]))


def _naive_se(residuals: np.ndarray, exposed: np.ndarray) -> float:
    n1 = int(exposed.sum())
    n0 = int((~exposed).sum())
    if n1 < 2 or n0 < 2:
        return float("inf")
    sigma_r = float(np.std(residuals, ddof=1))
    if sigma_r == 0.0:
        return 0.0
    return sigma_r * float(np.sqrt(1.0 / n1 + 1.0 / n0))


def _contiguous_folds(n: int, k: int = CV_FOLDS) -> np.ndarray:
    fold_sizes = [n // k] * k
    for i in range(n % k):
        fold_sizes[i] += 1
    assignments: list[int] = []
    for fid, size in enumerate(fold_sizes):
        assignments.extend([fid] * size)
    return np.asarray(assignments, dtype=int)


def _binarise_binary(x: np.ndarray, valid: np.ndarray) -> np.ndarray:
    exposed = np.zeros(len(x), dtype=bool)
    exposed[valid] = x[valid] >= 0.5
    return exposed


def _binarise_linear_masks(
    x: np.ndarray, valid: np.ndarray, train_mask: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Top tertile vs bottom tertile; middle days excluded from both groups."""
    train_x = x[train_mask & valid]
    top = np.zeros(len(x), dtype=bool)
    bottom = np.zeros(len(x), dtype=bool)
    if train_x.size < 3:
        return top, bottom
    p33, p67 = np.percentile(train_x, [33.33, 66.67])
    top = valid & (x >= p67)
    bottom = valid & (x <= p33)
    return top, bottom


def _select_threshold_spec(
    residuals: np.ndarray,
    x: np.ndarray,
    valid: np.ndarray,
    train_mask: np.ndarray,
) -> tuple[float, bool] | None:
    train_x = x[train_mask & valid]
    if train_x.size < MIN_GROUP_DAYS:
        return None
    best_abs_theta = -1.0
    best_spec: tuple[float, bool] | None = None
    for pct in THRESHOLD_PERCENTILES:
        c = float(np.percentile(train_x, pct))
        for ge in (True, False):
            if ge:
                candidate = valid & (x >= c)
            else:
                candidate = valid & (x <= c)
            n1 = int(candidate[train_mask].sum())
            n0 = int((~candidate & valid)[train_mask].sum())
            if n1 < MIN_GROUP_DAYS or n0 < MIN_GROUP_DAYS:
                continue
            theta = _contrast(residuals[train_mask], candidate[train_mask])
            if abs(theta) > best_abs_theta:
                best_abs_theta = abs(theta)
                best_spec = (float(pct), ge)
    return best_spec


def _apply_threshold_spec(
    x: np.ndarray,
    valid: np.ndarray,
    train_mask: np.ndarray,
    spec: tuple[float, bool],
) -> tuple[np.ndarray, float]:
    pct, ge = spec
    train_x = x[train_mask & valid]
    c = float(np.percentile(train_x, pct))
    if ge:
        exposed = valid & (x >= c)
    else:
        exposed = valid & (x <= c)
    return exposed, c


def _binarise_threshold(
    residuals: np.ndarray,
    x: np.ndarray,
    valid: np.ndarray,
    train_mask: np.ndarray,
) -> tuple[np.ndarray, float | None]:
    spec = _select_threshold_spec(residuals, x, valid, train_mask)
    if spec is None:
        return np.zeros(len(x), dtype=bool), None
    exposed, c = _apply_threshold_spec(x, valid, train_mask, spec)
    return exposed, c


def _build_exposure(
    shape: FeatureShape,
    residuals: np.ndarray,
    x: np.ndarray,
    valid: np.ndarray,
    train_mask: np.ndarray,
) -> tuple[np.ndarray, float | None]:
    if shape == "binary":
        return _binarise_binary(x, valid), None
    if shape == "linear":
        top, bottom = _binarise_linear_masks(x, valid, train_mask)
        exposed = top.copy()
        return exposed, None
    if shape == "threshold":
        return _binarise_threshold(residuals, x, valid, train_mask)
    raise ValueError(f"unsupported shape for single-feature effect: {shape}")


def _contrast_linear(residuals: np.ndarray, top: np.ndarray, bottom: np.ndarray) -> float:
    if top.sum() == 0 or bottom.sum() == 0:
        return 0.0
    return float(np.mean(residuals[top]) - np.mean(residuals[bottom]))


def _oof_exposure(
    shape: FeatureShape,
    residuals: np.ndarray,
    x: np.ndarray,
    valid: np.ndarray,
    folds: np.ndarray,
) -> tuple[np.ndarray, float | None]:
    n = len(x)
    if shape == "linear":
        top = np.zeros(n, dtype=bool)
        for fold_id in range(CV_FOLDS):
            train_mask = folds != fold_id
            test_mask = folds == fold_id
            fold_top, _ = _binarise_linear_masks(x, valid, train_mask)
            top[test_mask] = fold_top[test_mask]
        return top, None

    exposed = np.zeros(n, dtype=bool)
    last_c: float | None = None
    for fold_id in range(CV_FOLDS):
        train_mask = folds != fold_id
        test_mask = folds == fold_id
        fold_exposed, c = _build_exposure(shape, residuals, x, valid, train_mask)
        exposed[test_mask] = fold_exposed[test_mask]
        if c is not None:
            last_c = c
    return exposed, last_c


def _fold_theta(
    shape: FeatureShape,
    residuals: np.ndarray,
    x: np.ndarray,
    valid: np.ndarray,
    folds: np.ndarray,
    fold_id: int,
) -> float:
    train_mask = folds != fold_id
    test_mask = folds == fold_id
    if shape == "linear":
        top, bottom = _binarise_linear_masks(x, valid, train_mask)
        return _contrast_linear(residuals[test_mask], top[test_mask], bottom[test_mask])
    exposed, _ = _build_exposure(shape, residuals, x, valid, train_mask)
    return _contrast(residuals[test_mask], exposed[test_mask])


def _block_bootstrap_indices(
    n: int, block_len: int, n_boot: int, rng: np.random.Generator
) -> np.ndarray:
    n_blocks = int(np.ceil(n / block_len))
    out = np.empty((n_boot, n), dtype=int)
    for b in range(n_boot):
        starts = rng.integers(0, n, size=n_blocks)
        idx: list[int] = []
        for start in starts:
            for j in range(block_len):
                idx.append(int((start + j) % n))
        out[b] = np.asarray(idx[:n], dtype=int)
    return out


def _bootstrap_theta(
    shape: FeatureShape,
    residuals: np.ndarray,
    x: np.ndarray,
    valid: np.ndarray,
    folds: np.ndarray,
    n_boot: int,
    rng: np.random.Generator,
    *,
    fixed_exposed: np.ndarray | None = None,
    threshold_spec: tuple[float, bool] | None = None,
) -> np.ndarray:
    n = len(residuals)
    boot_idx = _block_bootstrap_indices(n, BLOCK_LENGTH_DAYS, n_boot, rng)

    if shape == "binary" and fixed_exposed is not None:
        r_boot = residuals[boot_idx]
        e_boot = fixed_exposed[boot_idx]
        n1 = e_boot.sum(axis=1).astype(float)
        n0 = n - n1
        sum_exp = (r_boot * e_boot).sum(axis=1)
        sum_unexp = (r_boot * ~e_boot).sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            return sum_exp / n1 - sum_unexp / n0

    all_train = np.ones(n, dtype=bool)
    thetas = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = boot_idx[b]
        r_b = residuals[idx]
        x_b = x[idx]
        v_b = valid[idx]
        if shape == "linear":
            top, bottom = _binarise_linear_masks(x_b, v_b, all_train)
            thetas[b] = _contrast_linear(r_b, top, bottom)
        elif shape == "threshold" and threshold_spec is not None:
            exposed_b, _ = _apply_threshold_spec(x_b, v_b, all_train, threshold_spec)
            thetas[b] = _contrast(r_b, exposed_b)
        else:
            exposed_b, _ = _build_exposure(shape, r_b, x_b, v_b, all_train)
            thetas[b] = _contrast(r_b, exposed_b)
    return thetas


def _ci_from_bootstrap(samples: np.ndarray) -> tuple[float, float, float]:
    lower = float(np.percentile(samples, 100 * CI_ALPHA / 2))
    upper = float(np.percentile(samples, 100 * (1 - CI_ALPHA / 2)))
    se = float(np.std(samples, ddof=1))
    return lower, upper, se


def _ci_excludes_zero(ci_lower: float, ci_upper: float) -> bool:
    return ci_lower > 0 or ci_upper < 0


def _zero_side_near_zero(ci_lower: float, ci_upper: float) -> bool:
    if ci_lower <= 0 <= ci_upper:
        return min(abs(ci_lower), abs(ci_upper)) <= EMERGING_ZERO_MARGIN
    return False


def _assign_tier(
    *,
    feature_class: FeatureClass,
    theta_hat: float,
    ci_lower: float | None,
    ci_upper: float | None,
    fold_count: int,
    exposed_days: int,
    unexposed_days: int,
    exposed_runs: int,
    observed_days: int,
    se_ratio: float | None,
    confounded: bool,
    preconditions_met: bool,
    precondition_reason: str,
) -> tuple[EffectTier, str]:
    if feature_class == "mirror":
        return "mirror", "mirror — same-day self-report excluded from drivers"

    if not preconditions_met:
        return "insufficient", precondition_reason

    if se_ratio is not None and se_ratio > SE_RATIO_FORCE_WATCHING:
        return "watching", "exposure too clustered (bootstrap/naive SE ratio > 1.5)"

    abs_theta = abs(theta_hat)
    ci_lo = ci_lower if ci_lower is not None else 0.0
    ci_hi = ci_upper if ci_upper is not None else 0.0
    ci_clear = _ci_excludes_zero(ci_lo, ci_hi)
    ci_near = _zero_side_near_zero(ci_lo, ci_hi)

    if (
        fold_count >= ESTABLISHED_F
        and ci_clear
        and exposed_days >= ESTABLISHED_X
        and exposed_runs >= ESTABLISHED_R
        and abs_theta >= ESTABLISHED_THETA
        and (se_ratio is None or se_ratio <= SE_RATIO_FORCE_WATCHING)
    ):
        return "established", ""

    if (
        fold_count >= EMERGING_F
        and exposed_days >= EMERGING_X
        and exposed_runs >= EMERGING_R
        and (ci_clear or ci_near)
        and abs_theta >= EMERGING_THETA
    ):
        return "emerging", ""

    if exposed_days < EMERGING_X:
        return "watching", "not enough exposed days per time block"
    if fold_count < EMERGING_F:
        return "watching", "effect unstable across time blocks"
    return "watching", "below tier thresholds"


def _check_preconditions(
    feature_class: FeatureClass,
    observed_days: int,
    exposed_days: int,
    unexposed_days: int,
    exposed_runs: int,
    confounded: bool,
) -> tuple[bool, str]:
    if feature_class == "mirror":
        return False, "mirror — same-day self-report excluded from drivers"
    if observed_days < MIN_OBSERVED_DAYS:
        return False, f"observed on {observed_days} usable days (< {MIN_OBSERVED_DAYS})"
    if exposed_days < MIN_GROUP_DAYS:
        return False, f"exposed days {exposed_days} < {MIN_GROUP_DAYS}"
    if unexposed_days < MIN_GROUP_DAYS:
        return False, f"unexposed days {unexposed_days} < {MIN_GROUP_DAYS}"
    if exposed_runs < MIN_EXPOSED_RUNS:
        return False, f"exposed runs {exposed_runs} < {MIN_EXPOSED_RUNS}"
    if confounded:
        return False, "confounded-with-trend"
    return True, ""


def select_threshold_c(
    residuals: np.ndarray,
    x: np.ndarray,
    valid: np.ndarray,
    train_mask: np.ndarray,
) -> float | None:
    """Return threshold c chosen from train_mask only (for in-fold isolation tests)."""
    _, c = _binarise_threshold(residuals, x, valid, train_mask)
    return c


def estimate_effect(
    column: str,
    rows: list[dict],
    baseline: BaselineResult,
    columns: list[str],
    *,
    lag: int | None = None,
    bootstrap_n: int = BOOTSTRAP_B,
    rng: np.random.Generator | None = None,
) -> EffectResult:
    """Estimate contrast effect with block bootstrap CI and fold-stability tier."""
    _ = columns
    use_lag = preferred_lag(column) if lag is None else lag
    feature_class = resolve_class(column, use_lag)
    shape = resolve_shape(column)
    confounded = column in baseline.confounded_with_trend

    residuals, x, valid = _extract_exposure_series(rows, baseline, column, use_lag)
    observed_days = int(valid.sum())

    if feature_class == "mirror":
        return EffectResult(
            column=column,
            lag=use_lag,
            feature_class=feature_class,
            shape=shape,
            tier="mirror",
            reason="mirror — same-day self-report excluded from drivers",
            theta_hat=None,
            ci_lower=None,
            ci_upper=None,
            bootstrap_se=None,
            naive_se=None,
            se_ratio=None,
            fold_count=0,
            exposed_days=0,
            unexposed_days=0,
            exposed_runs=0,
            observed_days=observed_days,
        )

    n = len(residuals)
    folds = _contiguous_folds(n, CV_FOLDS)
    exposed, threshold_c = _oof_exposure(shape, residuals, x, valid, folds)

    if shape == "linear":
        p33 = float(np.percentile(x[valid], 33.33)) if valid.any() else 0.0
        bottom = valid & (x <= p33)
        exposed_days = int(exposed.sum())
        unexposed_days = int(bottom.sum())
        theta_hat = _contrast_linear(residuals, exposed, bottom)
        naive_exposed = exposed
    else:
        exposed_days = int(exposed[valid].sum())
        unexposed_days = int((~exposed & valid).sum())
        theta_hat = _contrast(residuals, exposed)
        naive_exposed = exposed

    exposed_runs = _count_runs(exposed)
    pre_ok, pre_reason = _check_preconditions(
        feature_class,
        observed_days,
        exposed_days,
        unexposed_days,
        exposed_runs,
        confounded,
    )

    fold_thetas = [_fold_theta(shape, residuals, x, valid, folds, k) for k in range(CV_FOLDS)]
    if abs(theta_hat) < 1e-12:
        fold_count = sum(1 for ft in fold_thetas if abs(ft) < 1e-12)
    else:
        fold_count = sum(
            1
            for ft in fold_thetas
            if np.sign(ft) == np.sign(theta_hat) and abs(ft) >= FOLD_AGREEMENT_FRAC * abs(theta_hat)
        )

    gen = rng if rng is not None else np.random.default_rng()
    fixed_exposed = exposed if shape == "binary" else None
    threshold_spec = (
        _select_threshold_spec(residuals, x, valid, np.ones(n, dtype=bool))
        if shape == "threshold"
        else None
    )
    boot_samples = _bootstrap_theta(
        shape,
        residuals,
        x,
        valid,
        folds,
        bootstrap_n,
        gen,
        fixed_exposed=fixed_exposed,
        threshold_spec=threshold_spec,
    )
    ci_lower, ci_upper, bootstrap_se = _ci_from_bootstrap(boot_samples)
    naive_se = _naive_se(residuals, naive_exposed)
    se_ratio = bootstrap_se / naive_se if naive_se > 0 and np.isfinite(naive_se) else None

    tier, reason = _assign_tier(
        feature_class=feature_class,
        theta_hat=theta_hat,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        fold_count=fold_count,
        exposed_days=exposed_days,
        unexposed_days=unexposed_days,
        exposed_runs=exposed_runs,
        observed_days=observed_days,
        se_ratio=se_ratio,
        confounded=confounded,
        preconditions_met=pre_ok,
        precondition_reason=pre_reason,
    )

    return EffectResult(
        column=column,
        lag=use_lag,
        feature_class=feature_class,
        shape=shape,
        tier=tier,
        reason=reason,
        theta_hat=theta_hat,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        bootstrap_se=bootstrap_se,
        naive_se=naive_se,
        se_ratio=se_ratio,
        fold_count=fold_count,
        exposed_days=exposed_days,
        unexposed_days=unexposed_days,
        exposed_runs=exposed_runs,
        observed_days=observed_days,
        threshold_c=threshold_c,
        exposed_mask=exposed.tolist(),
    )


def _candidate_driver_columns(columns: list[str]) -> list[str]:
    skip = {
        "date",
        "schema_version",
        "period_of_day",
        "overall",
        "sick",
        "photo_count",
        "ingredient_count",
    }
    drivers: list[str] = []
    for col in columns:
        if col in skip:
            continue
        if col.startswith("tx_") and col.endswith("_active"):
            continue
        lag = preferred_lag(col)
        try:
            cls = resolve_class(col, lag)
        except Exception:
            continue
        if cls in ("mirror", "not-a-feature"):
            continue
        drivers.append(col)
    return drivers


def estimate_all_effects(
    rows: list[dict],
    columns: list[str],
    baseline: BaselineResult | None = None,
    *,
    bootstrap_n: int = BOOTSTRAP_B,
    rng: np.random.Generator | None = None,
) -> list[EffectResult]:
    """Estimate effects for all eligible driver columns."""
    base = baseline if baseline is not None else compute_baseline_residuals(rows, columns)
    gen = rng if rng is not None else np.random.default_rng()
    results: list[EffectResult] = []
    for col in _candidate_driver_columns(columns):
        results.append(
            estimate_effect(
                col,
                rows,
                base,
                columns,
                bootstrap_n=bootstrap_n,
                rng=gen,
            )
        )
    return results


def estimate_effect_from_arrays(
    residuals: np.ndarray,
    x: np.ndarray,
    *,
    shape: FeatureShape = "binary",
    bootstrap_n: int = BOOTSTRAP_B,
    rng: np.random.Generator | None = None,
    feature_class: FeatureClass = "lever",
    confounded: bool = False,
) -> EffectResult:
    """Test helper: estimate directly from residual/exposure arrays (all valid)."""
    valid = np.ones(len(residuals), dtype=bool)
    n = len(residuals)
    folds = _contiguous_folds(n, CV_FOLDS)
    exposed, threshold_c = _oof_exposure(shape, residuals, x, valid, folds)

    if shape == "linear":
        p33 = float(np.percentile(x, 33.33))
        bottom = valid & (x <= p33)
        exposed_days = int(exposed.sum())
        unexposed_days = int(bottom.sum())
        theta_hat = _contrast_linear(residuals, exposed, bottom)
        naive_exposed = exposed
    else:
        exposed_days = int(exposed.sum())
        unexposed_days = int((~exposed).sum())
        theta_hat = _contrast(residuals, exposed)
        naive_exposed = exposed

    exposed_runs = _count_runs(exposed)
    observed_days = n
    pre_ok, pre_reason = _check_preconditions(
        feature_class,
        observed_days,
        exposed_days,
        unexposed_days,
        exposed_runs,
        confounded,
    )

    fold_thetas = [_fold_theta(shape, residuals, x, valid, folds, k) for k in range(CV_FOLDS)]
    if abs(theta_hat) < 1e-12:
        fold_count = sum(1 for ft in fold_thetas if abs(ft) < 1e-12)
    else:
        fold_count = sum(
            1
            for ft in fold_thetas
            if np.sign(ft) == np.sign(theta_hat) and abs(ft) >= FOLD_AGREEMENT_FRAC * abs(theta_hat)
        )

    gen = rng if rng is not None else np.random.default_rng()
    fixed_exposed = exposed if shape == "binary" else None
    threshold_spec = (
        _select_threshold_spec(residuals, x, valid, np.ones(n, dtype=bool))
        if shape == "threshold"
        else None
    )
    boot_samples = _bootstrap_theta(
        shape,
        residuals,
        x,
        valid,
        folds,
        bootstrap_n,
        gen,
        fixed_exposed=fixed_exposed,
        threshold_spec=threshold_spec,
    )
    ci_lower, ci_upper, bootstrap_se = _ci_from_bootstrap(boot_samples)
    naive_se = _naive_se(residuals, naive_exposed)
    se_ratio = bootstrap_se / naive_se if naive_se > 0 and np.isfinite(naive_se) else None

    tier, reason = _assign_tier(
        feature_class=feature_class,
        theta_hat=theta_hat,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        fold_count=fold_count,
        exposed_days=exposed_days,
        unexposed_days=unexposed_days,
        exposed_runs=exposed_runs,
        observed_days=observed_days,
        se_ratio=se_ratio,
        confounded=confounded,
        preconditions_met=pre_ok,
        precondition_reason=pre_reason,
    )

    return EffectResult(
        column="_synthetic",
        lag=0,
        feature_class=feature_class,
        shape=shape,
        tier=tier,
        reason=reason,
        theta_hat=theta_hat,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        bootstrap_se=bootstrap_se,
        naive_se=naive_se,
        se_ratio=se_ratio,
        fold_count=fold_count,
        exposed_days=exposed_days,
        unexposed_days=unexposed_days,
        exposed_runs=exposed_runs,
        observed_days=observed_days,
        threshold_c=threshold_c,
        exposed_mask=exposed.tolist(),
    )
