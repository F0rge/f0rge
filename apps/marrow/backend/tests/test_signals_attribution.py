from __future__ import annotations

import datetime

import numpy as np
import pytest

from app.services.signals.attribution import (
    AttributionContext,
    build_attribution_context,
    compute_day_attribution,
    largest_remainder_round,
)
from app.services.signals.baseline import WARMUP_DAYS, BaselineResult, compute_baseline_residuals
from app.services.signals.effects import EffectResult
from app.services.signals.interactions import InteractionResult


def _make_row(
    date: datetime.date,
    overall: float,
    *,
    schema_version: int = 4,
    photo_count: int = 1,
    hm_sleep_hours: float = 7.0,
    **extra: object,
) -> dict:
    row: dict = {
        "date": date.isoformat(),
        "schema_version": schema_version,
        "overall": overall,
        "sick": False,
        "photo_count": photo_count,
        "ingredient_count": 3,
        "hm_sleep_hours": hm_sleep_hours,
    }
    row.update(extra)
    return row


def _synthetic_rows(n_days: int, start: datetime.date | None = None) -> list[dict]:
    start = start or datetime.date(2025, 1, 1)
    rng = np.random.default_rng(99)
    rows: list[dict] = []
    for i in range(n_days):
        d = start + datetime.timedelta(days=i)
        overall = 3.4 + rng.normal(0, 0.3)
        rows.append(
            _make_row(
                d,
                float(np.clip(overall, 1.0, 5.0)),
                alcohol_units=rng.integers(0, 3),
                hm_steps=float(rng.integers(2000, 12000)),
            )
        )
    return rows


def _minimal_columns() -> list[str]:
    return [
        "date",
        "schema_version",
        "overall",
        "sick",
        "photo_count",
        "ingredient_count",
        "hm_sleep_hours",
        "alcohol_units",
        "hm_steps",
    ]


def test_largest_remainder_closes_total() -> None:
    raw = [-0.410, -0.301, -0.282, -0.297, 0.172]
    display = largest_remainder_round(raw)
    assert sum(display) == pytest.approx(round(sum(raw), 1))
    assert display[0] == -0.4


def test_largest_remainder_pushes_to_largest_abs() -> None:
    values = [0.34, -0.11, 0.05]
    display = largest_remainder_round(values)
    naive = [round(v, 1) for v in values]
    assert sum(display) == pytest.approx(round(sum(values), 1))
    assert display != naive
    largest_idx = max(range(len(values)), key=lambda i: abs(values[i]))
    assert display[largest_idx] != naive[largest_idx]


def test_centring_all_exposures_at_mean() -> None:
    n_usable = 64
    mask = np.zeros(n_usable, dtype=bool)
    effect = EffectResult(
        column="test_feat",
        lag=0,
        feature_class="lever",
        shape="binary",
        tier="established",
        reason="",
        theta_hat=-0.5,
        ci_lower=-0.8,
        ci_upper=-0.2,
        bootstrap_se=0.1,
        naive_se=0.1,
        se_ratio=1.0,
        fold_count=5,
        exposed_days=0,
        unexposed_days=n_usable,
        exposed_runs=4,
        observed_days=n_usable,
        exposed_mask=mask.tolist(),
    )
    baseline = BaselineResult(
        dates=[f"2025-01-{i + 1:02d}" for i in range(WARMUP_DAYS + n_usable)],
        overall=[3.5] * (WARMUP_DAYS + n_usable),
        y_hat=[3.5] * (WARMUP_DAYS + n_usable),
        residuals=[0.0] * (WARMUP_DAYS + n_usable),
        L=[3.5] * (WARMUP_DAYS + n_usable),
        W=[0.0] * (WARMUP_DAYS + n_usable),
        T=[0.0] * (WARMUP_DAYS + n_usable),
        diagnostics=__import__(
            "app.services.signals.baseline", fromlist=["BaselineDiagnostics"]
        ).BaselineDiagnostics(
            days_total=WARMUP_DAYS + n_usable,
            days_v4=WARMUP_DAYS + n_usable,
            days_usable=n_usable,
            warmup_days=WARMUP_DAYS,
        ),
    )
    ctx = AttributionContext(
        effects=[effect],
        interactions=[],
        exposure_means={"test_feat": 0.0},
        interaction_both_means={},
        interaction_masks={},
        usable_indices=list(range(WARMUP_DAYS, WARMUP_DAYS + n_usable)),
    )
    day_idx = WARMUP_DAYS + 10
    day = compute_day_attribution(day_idx, baseline, ctx)
    for contrib in day.contributions:
        assert contrib.value == pytest.approx(0.0, abs=1e-9)
    assert day.predicted == pytest.approx(day.baseline, abs=1e-9)


def test_interaction_three_rows_on_coexposed_day() -> None:
    n_usable = 92
    mask_a = np.zeros(n_usable, dtype=bool)
    mask_b = np.zeros(n_usable, dtype=bool)
    mask_a[5] = True
    mask_b[5] = True
    mask_a[10:25] = True
    mask_b[20:35] = True
    both = mask_a & mask_b

    effect_a = EffectResult(
        column="sleep_short",
        lag=0,
        feature_class="lever",
        shape="threshold",
        tier="established",
        reason="",
        theta_hat=-0.58,
        ci_lower=-1.0,
        ci_upper=-0.2,
        bootstrap_se=0.1,
        naive_se=0.1,
        se_ratio=1.0,
        fold_count=5,
        exposed_days=int(mask_a.sum()),
        unexposed_days=int((~mask_a).sum()),
        exposed_runs=3,
        observed_days=n_usable,
        exposed_mask=mask_a.tolist(),
    )
    effect_b = EffectResult(
        column="histamine_high",
        lag=0,
        feature_class="lever",
        shape="threshold",
        tier="established",
        reason="",
        theta_hat=-0.44,
        ci_lower=-0.8,
        ci_upper=-0.1,
        bootstrap_se=0.1,
        naive_se=0.1,
        se_ratio=1.0,
        fold_count=5,
        exposed_days=int(mask_b.sum()),
        unexposed_days=int((~mask_b).sum()),
        exposed_runs=3,
        observed_days=n_usable,
        exposed_mask=mask_b.tolist(),
    )
    inter = InteractionResult(
        column_a="sleep_short",
        column_b="histamine_high",
        tier="emerging",
        reason="",
        excess=-0.32,
        both_minus_neither=-1.34,
        a_only_minus_neither=-0.58,
        b_only_minus_neither=-0.44,
        additive_expected=-1.02,
        ci_lower=-1.5,
        ci_upper=-0.1,
        co_exposed_days=int(both.sum()),
        co_exposed_runs=2,
    )
    baseline = BaselineResult(
        dates=[f"2025-01-{i + 1:02d}" for i in range(WARMUP_DAYS + n_usable)],
        overall=[3.5] * (WARMUP_DAYS + n_usable),
        y_hat=[3.5] * (WARMUP_DAYS + n_usable),
        residuals=[0.0] * (WARMUP_DAYS + n_usable),
        L=[3.5] * (WARMUP_DAYS + n_usable),
        W=[0.0] * (WARMUP_DAYS + n_usable),
        T=[0.0] * (WARMUP_DAYS + n_usable),
        diagnostics=__import__(
            "app.services.signals.baseline", fromlist=["BaselineDiagnostics"]
        ).BaselineDiagnostics(
            days_total=WARMUP_DAYS + n_usable,
            days_v4=WARMUP_DAYS + n_usable,
            days_usable=n_usable,
            warmup_days=WARMUP_DAYS,
        ),
    )
    ctx = AttributionContext(
        effects=[effect_a, effect_b],
        interactions=[inter],
        exposure_means={
            "sleep_short": float(np.mean(mask_a)),
            "histamine_high": float(np.mean(mask_b)),
        },
        interaction_both_means={("sleep_short", "histamine_high"): float(np.mean(both))},
        interaction_masks={("sleep_short", "histamine_high"): both},
        usable_indices=list(range(WARMUP_DAYS, WARMUP_DAYS + n_usable)),
    )
    day_idx = WARMUP_DAYS + 5
    day = compute_day_attribution(day_idx, baseline, ctx)
    interaction_rows = [c for c in day.contributions if c.kind == "interaction"]
    main_rows = [c for c in day.contributions if c.kind != "interaction"]
    assert len(main_rows) == 2
    assert len(interaction_rows) == 1

    without_excess = [c for c in day.contributions if c.kind != "interaction"]
    predicted_without = day.baseline + sum(c.value for c in without_excess)
    assert predicted_without != pytest.approx(day.predicted, abs=0.05)


def test_additivity_property_random_days() -> None:
    rows = _synthetic_rows(120)
    columns = _minimal_columns()
    baseline = compute_baseline_residuals(rows, columns)
    ctx = build_attribution_context(rows, columns, baseline)
    rng = np.random.default_rng(42)
    indices = rng.choice(ctx.usable_indices, size=500, replace=True)
    for idx in indices:
        day = compute_day_attribution(int(idx), baseline, ctx)
        raw_sum = day.baseline + sum(c.value for c in day.contributions)
        assert raw_sum == pytest.approx(day.predicted, abs=1e-9)
        display_sum = day.display_baseline + sum(c.display_value for c in day.contributions)
        assert display_sum == pytest.approx(day.display_predicted, abs=1e-9)
