from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.services.signals.baseline import WARMUP_DAYS, BaselineResult, compute_baseline_residuals
from app.services.signals.effects import EffectResult, estimate_all_effects
from app.services.signals.interactions import InteractionResult, compute_interactions

ContributionKind = Literal["lever", "context", "interaction"]
DISPLAY_DECIMALS = 1  # §Layer 4 — largest-remainder display precision


@dataclass
class ContributionRow:
    driver_id: str
    label: str
    column: str
    kind: ContributionKind
    category: str
    value: float
    display_value: float


@dataclass
class DayAttribution:
    date: str
    actual: float | None
    baseline: float
    display_baseline: float
    contributions: list[ContributionRow]
    predicted: float
    display_predicted: float
    residual: float | None
    display_residual: float | None


@dataclass
class AttributionContext:
    """Precomputed effect means and masks for attribution."""

    effects: list[EffectResult]
    interactions: list[InteractionResult]
    exposure_means: dict[str, float]
    interaction_both_means: dict[tuple[str, str], float]
    interaction_masks: dict[tuple[str, str], np.ndarray]
    usable_indices: list[int]


def _parse_date(date_val: str | datetime.date) -> datetime.date:
    if isinstance(date_val, datetime.date):
        return date_val
    return datetime.date.fromisoformat(str(date_val))


def _round_1dp(value: float) -> float:
    return round(value, DISPLAY_DECIMALS)


def largest_remainder_round(values: list[float], decimals: int = DISPLAY_DECIMALS) -> list[float]:
    """Round values to ``decimals`` dp; push residual error onto largest-|value| row.

    See ``signals_method.md`` §Layer 4 — largest-remainder rounding.
    """
    if not values:
        return []
    scale = 10**decimals
    floors = [int(np.floor(v * scale + 1e-9)) for v in values]
    target_sum = int(round(sum(values) * scale))
    remainder = target_sum - sum(floors)
    if remainder == 0:
        return [f / scale for f in floors]
    order = sorted(range(len(values)), key=lambda i: abs(values[i]), reverse=True)
    idx = 0
    while remainder > 0:
        floors[order[idx % len(order)]] += 1
        remainder -= 1
        idx += 1
    while remainder < 0:
        floors[order[idx % len(order)]] -= 1
        remainder += 1
        idx += 1
    return [f / scale for f in floors]


def _driver_label(column: str) -> str:
    return column.replace("_", " ")


def _interaction_driver_id(col_a: str, col_b: str) -> str:
    return f"{col_a}_x_{col_b}"


def _usable_indices(baseline: BaselineResult) -> list[int]:
    return list(range(WARMUP_DAYS, len(baseline.dates)))


def build_attribution_context(
    rows: list[dict],
    columns: list[str],
    baseline: BaselineResult | None = None,
    *,
    effects: list[EffectResult] | None = None,
    interactions: list[InteractionResult] | None = None,
) -> AttributionContext:
    """Build masks and training means for attribution."""
    base = baseline if baseline is not None else compute_baseline_residuals(rows, columns)
    effs = effects if effects is not None else estimate_all_effects(rows, columns, base)
    inters = interactions if interactions is not None else compute_interactions(rows, columns, base)
    usable = _usable_indices(base)
    n_usable = len(usable)

    exposure_means: dict[str, float] = {}
    eligible_effects: list[EffectResult] = []
    for effect in effs:
        if effect.tier in ("mirror", "insufficient") or effect.theta_hat is None:
            continue
        if effect.exposed_mask is None or len(effect.exposed_mask) != n_usable:
            continue
        mask = np.asarray(effect.exposed_mask, dtype=float)
        exposure_means[effect.column] = float(np.mean(mask))
        eligible_effects.append(effect)

    interaction_both_means: dict[tuple[str, str], float] = {}
    interaction_masks: dict[tuple[str, str], np.ndarray] = {}
    for inter in inters:
        if inter.excess is None or inter.tier == "insufficient":
            continue
        effect_a = next((e for e in effs if e.column == inter.column_a), None)
        effect_b = next((e for e in effs if e.column == inter.column_b), None)
        if (
            effect_a is None
            or effect_b is None
            or effect_a.exposed_mask is None
            or effect_b.exposed_mask is None
        ):
            continue
        mask_a = np.asarray(effect_a.exposed_mask, dtype=bool)
        mask_b = np.asarray(effect_b.exposed_mask, dtype=bool)
        both = mask_a & mask_b
        key = (inter.column_a, inter.column_b)
        interaction_masks[key] = both
        interaction_both_means[key] = float(np.mean(both.astype(float)))

    return AttributionContext(
        effects=eligible_effects,
        interactions=[i for i in inters if i.excess is not None and i.tier != "insufficient"],
        exposure_means=exposure_means,
        interaction_both_means=interaction_both_means,
        interaction_masks=interaction_masks,
        usable_indices=usable,
    )


def _contribution(
    *,
    driver_id: str,
    label: str,
    column: str,
    kind: ContributionKind,
    category: str,
    theta: float,
    exposed: bool,
    exposure_mean: float,
) -> ContributionRow:
    raw = theta * (float(exposed) - exposure_mean)
    return ContributionRow(
        driver_id=driver_id,
        label=label,
        column=column,
        kind=kind,
        category=category,
        value=raw,
        display_value=raw,
    )


def compute_day_attribution(
    day_index: int,
    baseline: BaselineResult,
    ctx: AttributionContext,
) -> DayAttribution:
    """Compute exact additive attribution for one day (``signals_method.md`` §Layer 4)."""
    b_raw = float(baseline.y_hat[day_index])
    actual = baseline.overall[day_index]
    local_i = day_index - WARMUP_DAYS
    contributions: list[ContributionRow] = []

    for effect in ctx.effects:
        if effect.exposed_mask is None or local_i < 0 or local_i >= len(effect.exposed_mask):
            continue
        exposed = bool(effect.exposed_mask[local_i])
        e_mean = ctx.exposure_means[effect.column]
        contributions.append(
            _contribution(
                driver_id=effect.column,
                label=_driver_label(effect.column),
                column=effect.column,
                kind="lever" if effect.feature_class == "lever" else "context",
                category=effect.shape,
                theta=float(effect.theta_hat),
                exposed=exposed,
                exposure_mean=e_mean,
            )
        )

    for inter in ctx.interactions:
        key = (inter.column_a, inter.column_b)
        both_mask = ctx.interaction_masks.get(key)
        e_mean_both = ctx.interaction_both_means.get(key)
        if both_mask is None or e_mean_both is None or local_i < 0:
            continue
        both_exposed = bool(both_mask[local_i])
        contributions.append(
            _contribution(
                driver_id=_interaction_driver_id(inter.column_a, inter.column_b),
                label=f"{_driver_label(inter.column_a)} × {_driver_label(inter.column_b)}",
                column=_interaction_driver_id(inter.column_a, inter.column_b),
                kind="interaction",
                category="interaction",
                theta=float(inter.excess),
                exposed=both_exposed,
                exposure_mean=e_mean_both,
            )
        )

    raw_sum = sum(c.value for c in contributions)
    predicted = b_raw + raw_sum
    residual = (float(actual) - predicted) if actual is not None else None

    raw_values = [c.value for c in contributions]
    display_values = largest_remainder_round(raw_values, DISPLAY_DECIMALS)
    for contrib, disp in zip(contributions, display_values):
        contrib.display_value = disp

    display_baseline = _round_1dp(b_raw)
    display_predicted = _round_1dp(display_baseline + sum(c.display_value for c in contributions))
    display_residual = _round_1dp(residual) if residual is not None else None

    return DayAttribution(
        date=baseline.dates[day_index],
        actual=actual,
        baseline=b_raw,
        display_baseline=display_baseline,
        contributions=contributions,
        predicted=predicted,
        display_predicted=display_predicted,
        residual=residual,
        display_residual=display_residual,
    )


def compute_calibration_series(
    rows: list[dict],
    columns: list[str],
    baseline: BaselineResult | None = None,
    ctx: AttributionContext | None = None,
) -> list[DayAttribution]:
    """Per-day attribution for all post-warmup usable days."""
    base = baseline if baseline is not None else compute_baseline_residuals(rows, columns)
    context = ctx if ctx is not None else build_attribution_context(rows, columns, base)
    return [compute_day_attribution(idx, base, context) for idx in context.usable_indices]
