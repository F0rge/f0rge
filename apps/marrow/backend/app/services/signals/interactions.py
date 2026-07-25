from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.services.signals.baseline import BaselineResult, compute_baseline_residuals
from app.services.signals.effects import (
    BLOCK_LENGTH_DAYS,
    BOOTSTRAP_B,
    _block_bootstrap_indices,
    _ci_from_bootstrap,
    _count_runs,
    estimate_effect,
    preferred_lag,
)
from app.services.signals.taxonomy import CLASS_BY_COLUMN

InteractionTier = Literal["established", "emerging", "insufficient"]

MAX_INTERACTION_TESTS = 15  # §Layer 3 — interaction search cap
MIN_CO_EXPOSED_DAYS = 8  # §Layer 3 — interaction preconditions
MIN_CO_EXPOSED_RUNS = 2
MIN_EXCESS_POINTS = 0.25  # §Layer 3 — |excess| floor
ESTABLISHED_CO_EXPOSED = 20  # §Layer 3 — interaction established cap

FOOD_AXIS_COLUMNS = frozenset(
    {
        "histamine_load_sum",
        "histamine_load_max",
        "fodmap_oligos_sum",
        "fodmap_fructose_sum",
        "fodmap_polyols_sum",
        "fodmap_lactose_sum",
        "gluten_exposure",
        "dairy_exposure",
        "manual_extra_dairy",
        "manual_extra_fodmap",
        "manual_extra_gluten",
        "manual_extra_histamine",
    }
)

SLEEP_COLUMNS = frozenset({"hm_sleep_hours", "hm_sleep_start", "hm_sleep_end"})
ALCOHOL_COLUMNS = frozenset({"alcohol_units", "had_alcohol"})
WEATHER_COLUMNS = frozenset(col for col in CLASS_BY_COLUMN if col.startswith("wx_"))

LEVER_CATEGORY: dict[str, str] = {}
for col in FOOD_AXIS_COLUMNS:
    LEVER_CATEGORY[col] = "food"
for col in SLEEP_COLUMNS:
    LEVER_CATEGORY[col] = "sleep"
for col in ALCOHOL_COLUMNS:
    LEVER_CATEGORY[col] = "alcohol"
for col in WEATHER_COLUMNS:
    LEVER_CATEGORY[col] = "weather"
for col in ("caffeine_servings", "had_caffeine"):
    LEVER_CATEGORY[col] = "caffeine"
for col in ("hm_steps", "hm_active_minutes"):
    LEVER_CATEGORY[col] = "activity"
for col in ("hot_shower",):
    LEVER_CATEGORY[col] = "lifestyle"


@dataclass
class InteractionResult:
    column_a: str
    column_b: str
    tier: InteractionTier
    reason: str
    excess: float | None
    both_minus_neither: float | None
    a_only_minus_neither: float | None
    b_only_minus_neither: float | None
    additive_expected: float | None
    ci_lower: float | None
    ci_upper: float | None
    co_exposed_days: int
    co_exposed_runs: int


def _lever_category(column: str) -> str | None:
    if column in LEVER_CATEGORY:
        return LEVER_CATEGORY[column]
    if column.startswith("supp_"):
        return "supplement"
    return None


def _is_mechanism_pair(col_a: str, col_b: str) -> bool:
    a_food = col_a in FOOD_AXIS_COLUMNS
    b_food = col_b in FOOD_AXIS_COLUMNS
    a_sleep = col_a in SLEEP_COLUMNS
    b_sleep = col_b in SLEEP_COLUMNS
    a_alcohol = col_a in ALCOHOL_COLUMNS
    b_alcohol = col_b in ALCOHOL_COLUMNS
    a_weather = col_a in WEATHER_COLUMNS
    b_weather = col_b in WEATHER_COLUMNS

    if (a_sleep and b_food) or (b_sleep and a_food):
        return True
    if (a_alcohol and b_food) or (b_alcohol and a_food):
        return True
    if (a_sleep and b_alcohol) or (b_sleep and a_alcohol):
        return True
    if (a_weather and b_sleep) or (b_weather and a_sleep):
        return True

    cat_a = _lever_category(col_a)
    cat_b = _lever_category(col_b)
    if cat_a is not None and cat_a == cat_b:
        return True
    return False


def _cell_means(
    residuals: np.ndarray,
    mask_a: np.ndarray,
    mask_b: np.ndarray,
) -> tuple[float, float, float, float]:
    neither = ~mask_a & ~mask_b
    a_only = mask_a & ~mask_b
    b_only = ~mask_a & mask_b
    both = mask_a & mask_b
    return (
        float(np.mean(residuals[both])) if both.any() else 0.0,
        float(np.mean(residuals[neither])) if neither.any() else 0.0,
        float(np.mean(residuals[a_only])) if a_only.any() else 0.0,
        float(np.mean(residuals[b_only])) if b_only.any() else 0.0,
    )


def compute_excess(
    residuals: np.ndarray,
    mask_a: np.ndarray,
    mask_b: np.ndarray,
) -> tuple[float, float, float, float, float]:
    """Return (excess, both-neither, a_only-neither, b_only-neither, additive_expected)."""
    both_m, neither_m, a_only_m, b_only_m = _cell_means(residuals, mask_a, mask_b)
    both_minus_neither = both_m - neither_m
    a_only_minus_neither = a_only_m - neither_m
    b_only_minus_neither = b_only_m - neither_m
    additive_expected = a_only_minus_neither + b_only_minus_neither
    excess = both_minus_neither - a_only_minus_neither - b_only_minus_neither
    return excess, both_minus_neither, a_only_minus_neither, b_only_minus_neither, additive_expected


def _bootstrap_excess(
    residuals: np.ndarray,
    mask_a: np.ndarray,
    mask_b: np.ndarray,
    n_boot: int,
    rng: np.random.Generator,
) -> np.ndarray:
    n = len(residuals)
    boot_idx = _block_bootstrap_indices(n, BLOCK_LENGTH_DAYS, n_boot, rng)
    samples = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = boot_idx[b]
        excess, _, _, _, _ = compute_excess(residuals[idx], mask_a[idx], mask_b[idx])
        samples[b] = excess
    return samples


def _exposure_mask_from_effect(
    rows: list[dict],
    baseline: BaselineResult,
    columns: list[str],
    column: str,
    lag: int,
) -> np.ndarray | None:
    effect = estimate_effect(column, rows, baseline, columns, lag=lag, bootstrap_n=50)
    if effect.exposed_mask is None:
        return None
    return np.asarray(effect.exposed_mask, dtype=bool)


def compute_interactions(
    rows: list[dict],
    columns: list[str],
    baseline: BaselineResult | None = None,
    *,
    eligible_columns: list[str] | None = None,
    bootstrap_n: int = BOOTSTRAP_B,
    rng: np.random.Generator | None = None,
) -> list[InteractionResult]:
    """Restricted interaction search over established/emerging features."""
    from app.services.signals.effects import _extract_exposure_series

    base = baseline if baseline is not None else compute_baseline_residuals(rows, columns)
    gen = rng if rng is not None else np.random.default_rng()

    if eligible_columns is None:
        from app.services.signals.effects import _candidate_driver_columns, estimate_all_effects

        effects = estimate_all_effects(rows, columns, base, bootstrap_n=50, rng=gen)
        eligible = [e.column for e in effects if e.tier in ("established", "emerging")]
        if not eligible:
            eligible = _candidate_driver_columns(columns)[:8]
    else:
        eligible = list(eligible_columns)

    pairs: list[tuple[str, str]] = []
    for i, col_a in enumerate(eligible):
        for col_b in eligible[i + 1 :]:
            if _is_mechanism_pair(col_a, col_b):
                pairs.append((col_a, col_b))
    pairs = pairs[:MAX_INTERACTION_TESTS]

    results: list[InteractionResult] = []
    for col_a, col_b in pairs:
        lag_a = preferred_lag(col_a)
        lag_b = preferred_lag(col_b)
        residuals_a, _, valid_a = _extract_exposure_series(rows, base, col_a, lag_a)
        residuals_b, _, valid_b = _extract_exposure_series(rows, base, col_b, lag_b)
        valid = valid_a & valid_b
        if valid.sum() < MIN_CO_EXPOSED_DAYS:
            results.append(
                InteractionResult(
                    column_a=col_a,
                    column_b=col_b,
                    tier="insufficient",
                    reason="insufficient co-valid days",
                    excess=None,
                    both_minus_neither=None,
                    a_only_minus_neither=None,
                    b_only_minus_neither=None,
                    additive_expected=None,
                    ci_lower=None,
                    ci_upper=None,
                    co_exposed_days=0,
                    co_exposed_runs=0,
                )
            )
            continue

        residuals = residuals_a
        mask_a = _exposure_mask_from_effect(rows, base, columns, col_a, lag_a)
        mask_b = _exposure_mask_from_effect(rows, base, columns, col_b, lag_b)
        if mask_a is None or mask_b is None:
            continue
        mask_a = mask_a & valid
        mask_b = mask_b & valid

        co_exposed = mask_a & mask_b
        co_exposed_days = int(co_exposed.sum())
        co_exposed_runs = _count_runs(co_exposed)

        if co_exposed_days < MIN_CO_EXPOSED_DAYS or co_exposed_runs < MIN_CO_EXPOSED_RUNS:
            results.append(
                InteractionResult(
                    column_a=col_a,
                    column_b=col_b,
                    tier="insufficient",
                    reason=(
                        f"co-exposed days {co_exposed_days} < {MIN_CO_EXPOSED_DAYS} "
                        f"or runs {co_exposed_runs} < {MIN_CO_EXPOSED_RUNS}"
                    ),
                    excess=None,
                    both_minus_neither=None,
                    a_only_minus_neither=None,
                    b_only_minus_neither=None,
                    additive_expected=None,
                    ci_lower=None,
                    ci_upper=None,
                    co_exposed_days=co_exposed_days,
                    co_exposed_runs=co_exposed_runs,
                )
            )
            continue

        excess, both_mn, a_mn, b_mn, additive = compute_excess(residuals, mask_a, mask_b)
        boot = _bootstrap_excess(residuals, mask_a, mask_b, bootstrap_n, gen)
        ci_lower, ci_upper, _ = _ci_from_bootstrap(boot)

        if abs(excess) < MIN_EXCESS_POINTS:
            tier: InteractionTier = "insufficient"
            reason = f"|excess| {abs(excess):.3f} < {MIN_EXCESS_POINTS}"
        elif co_exposed_days < ESTABLISHED_CO_EXPOSED or not (ci_lower > 0 or ci_upper < 0):
            tier = "emerging"
            reason = "capped at emerging until co-exposed ≥ 20 and excess CI excludes 0"
        else:
            tier = "established"
            reason = ""

        results.append(
            InteractionResult(
                column_a=col_a,
                column_b=col_b,
                tier=tier,
                reason=reason,
                excess=excess,
                both_minus_neither=both_mn,
                a_only_minus_neither=a_mn,
                b_only_minus_neither=b_mn,
                additive_expected=additive,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                co_exposed_days=co_exposed_days,
                co_exposed_runs=co_exposed_runs,
            )
        )

    return results


def compute_excess_from_masks(
    residuals: np.ndarray,
    mask_a: np.ndarray,
    mask_b: np.ndarray,
    *,
    co_exposed_days: int | None = None,
    bootstrap_n: int = BOOTSTRAP_B,
    rng: np.random.Generator | None = None,
) -> InteractionResult:
    """Test helper for planted 2×2 interaction arithmetic."""
    gen = rng if rng is not None else np.random.default_rng()
    co = int((mask_a & mask_b).sum()) if co_exposed_days is None else co_exposed_days
    co_runs = _count_runs(mask_a & mask_b)
    excess, both_mn, a_mn, b_mn, additive = compute_excess(residuals, mask_a, mask_b)
    boot = _bootstrap_excess(residuals, mask_a, mask_b, bootstrap_n, gen)
    ci_lower, ci_upper, _ = _ci_from_bootstrap(boot)

    if co < MIN_CO_EXPOSED_DAYS:
        tier: InteractionTier = "insufficient"
        reason = f"co-exposed days {co} < {MIN_CO_EXPOSED_DAYS}"
    elif abs(excess) < MIN_EXCESS_POINTS:
        tier = "insufficient"
        reason = f"|excess| < {MIN_EXCESS_POINTS}"
    elif co < ESTABLISHED_CO_EXPOSED or not (ci_lower > 0 or ci_upper < 0):
        tier = "emerging"
        reason = "capped at emerging"
    else:
        tier = "established"
        reason = ""

    return InteractionResult(
        column_a="a",
        column_b="b",
        tier=tier,
        reason=reason,
        excess=excess,
        both_minus_neither=both_mn,
        a_only_minus_neither=a_mn,
        b_only_minus_neither=b_mn,
        additive_expected=additive,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        co_exposed_days=co,
        co_exposed_runs=co_runs,
    )
