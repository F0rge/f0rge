from __future__ import annotations

import datetime

import numpy as np

from app.services.signals.baseline import (
    TREND_CAP_POINTS_PER_DAY,
    WARMUP_DAYS,
    compute_baseline_residuals,
    weekday_shrinkage_factor,
)


def _make_row(
    date: datetime.date,
    overall: float,
    schema_version: int = 4,
    sick: bool = False,
    **extra: object,
) -> dict:
    row: dict = {
        "date": date.isoformat(),
        "schema_version": schema_version,
        "overall": overall,
        "sick": sick,
        "photo_count": 1,
        "ingredient_count": 3,
    }
    row.update(extra)
    return row


def _synthetic_weekday_drift(n_days: int, start: datetime.date) -> list[dict]:
    """Weekday cycle + slow linear drift for baseline vs constant test."""
    rows: list[dict] = []
    for i in range(n_days):
        d = start + datetime.timedelta(days=i)
        dow = d.weekday()
        weekday_effect = {0: -0.2, 1: 0.0, 2: 0.1, 3: 0.0, 4: -0.1, 5: 0.4, 6: 0.3}[dow]
        drift = 0.003 * i
        overall = 3.4 + weekday_effect + drift + np.random.default_rng(i).normal(0, 0.05)
        rows.append(_make_row(d, overall))
    return rows


def _baseline_mae(result_rows: list[dict], columns: list[str]) -> float:
    res = compute_baseline_residuals(result_rows, columns)
    usable = res.residuals[WARMUP_DAYS:]
    return float(np.mean(np.abs([r for r in usable if r is not None])))


def _constant_mae(result_rows: list[dict]) -> float:
    overalls = [float(r["overall"]) for r in result_rows if r.get("schema_version", 0) >= 4]
    usable = overalls[WARMUP_DAYS:]
    mean_y = float(np.mean(overalls[:WARMUP_DAYS]))
    return float(np.mean(np.abs(np.asarray(usable) - mean_y)))


def test_no_leakage_append_days() -> None:
    start = datetime.date(2025, 1, 1)
    n_initial = WARMUP_DAYS + 40
    columns = ["date", "schema_version", "overall", "sick", "photo_count", "ingredient_count"]

    initial_rows = _synthetic_weekday_drift(n_initial, start)
    result_initial = compute_baseline_residuals(initial_rows, columns)
    residuals_initial = list(result_initial.residuals)

    extended_rows = list(initial_rows)
    for i in range(30):
        d = start + datetime.timedelta(days=n_initial + i)
        overall = 3.5 + 0.01 * (n_initial + i)
        extended_rows.append(_make_row(d, overall))

    result_extended = compute_baseline_residuals(extended_rows, columns)
    residuals_extended_prefix = result_extended.residuals[: len(residuals_initial)]

    for a, b in zip(residuals_initial, residuals_extended_prefix):
        assert a == b


def test_baseline_beats_constant_on_weekday_drift() -> None:
    start = datetime.date(2025, 3, 1)
    n_days = WARMUP_DAYS + 60
    columns = ["date", "schema_version", "overall", "sick", "photo_count", "ingredient_count"]
    rows = _synthetic_weekday_drift(n_days, start)

    baseline_mae = _baseline_mae(rows, columns)
    constant_mae = _constant_mae(rows)
    assert baseline_mae < constant_mae


def test_weekday_shrinkage() -> None:
    assert weekday_shrinkage_factor(0) == 0.0
    expected = 13 / (13 + 10)
    assert abs(weekday_shrinkage_factor(13) - expected) < 0.01
    assert abs(weekday_shrinkage_factor(13) - 0.565) < 0.01


def test_trend_cap() -> None:
    """0.1 pts/day ramp → |T| capped at TREND_CAP (signals_method.md §Layer 1)."""
    start = datetime.date(2025, 6, 1)
    columns = ["date", "schema_version", "overall", "sick", "photo_count", "ingredient_count"]
    rows: list[dict] = []
    n_days = WARMUP_DAYS + 70
    for i in range(n_days):
        d = start + datetime.timedelta(days=i)
        overall = 2.0 + 0.1 * i
        rows.append(_make_row(d, overall))

    result = compute_baseline_residuals(rows, columns)
    t_after_warmup = [t for t in result.T[WARMUP_DAYS:] if t is not None]
    assert t_after_warmup
    assert max(abs(t) for t in t_after_warmup) <= TREND_CAP_POINTS_PER_DAY + 1e-9
    assert any(abs(t) >= TREND_CAP_POINTS_PER_DAY - 1e-6 for t in t_after_warmup)


def test_confounded_with_trend_step_aligned_not_alternating() -> None:
    """Step exposure aligned with drift is confounded; alternating step is not."""
    start = datetime.date(2025, 7, 1)
    drift_start = 50
    n_days = WARMUP_DAYS + 80
    columns = [
        "date",
        "schema_version",
        "overall",
        "sick",
        "photo_count",
        "ingredient_count",
        "exposure_step",
    ]

    aligned_rows: list[dict] = []
    alternating_rows: list[dict] = []
    for i in range(n_days):
        d = start + datetime.timedelta(days=i)
        if i < drift_start:
            overall = 3.0
            step_on = 0
        else:
            overall = 3.0 + 0.12 * (i - drift_start)
            step_on = 1
        aligned_rows.append(_make_row(d, overall, exposure_step=step_on))
        alternating_rows.append(_make_row(d, overall, exposure_step=i % 2))

    aligned = compute_baseline_residuals(aligned_rows, columns)
    alternating = compute_baseline_residuals(alternating_rows, columns)

    assert "exposure_step" in aligned.confounded_with_trend
    assert "exposure_step" not in alternating.confounded_with_trend
