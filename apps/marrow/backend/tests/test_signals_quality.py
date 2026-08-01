from __future__ import annotations

import datetime

import numpy as np
import pytest

from app.services.signals.quality import (
    MAE_FROM_SD,
    compute_model_quality,
    estimate_noise_floor,
    estimate_noise_floor_ar1,
)
from app.services.signals.baseline import WARMUP_DAYS


def test_ar1_recovers_planted_noise_sd() -> None:
    rng = np.random.default_rng(123)
    planted_sd = 0.63
    phi = 0.4
    state_sd = 0.2
    n = 300
    state = 0.0
    series: list[float] = []
    for _ in range(n):
        state = phi * state + rng.normal(0, state_sd)
        series.append(state + rng.normal(0, planted_sd))
    est_sd, _ = estimate_noise_floor_ar1(np.asarray(series))
    assert abs(est_sd - planted_sd) < 0.1


def test_noise_floor_mae_sd_units() -> None:
    rng = np.random.default_rng(1)
    series = rng.normal(3.4, 0.2, 100)
    est_sd, est_mae = estimate_noise_floor_ar1(series)
    assert est_mae == pytest.approx(est_sd * MAE_FROM_SD, rel=1e-6)


def test_take_larger_when_estimators_disagree(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.signals.quality as quality_mod

    monkeypatch.setattr(quality_mod, "estimate_noise_floor_ar1", lambda overall: (0.40, 0.32))
    monkeypatch.setattr(
        quality_mod,
        "estimate_noise_floor_within_cell",
        lambda rows, baseline, effects: (0.70, 0.56),
    )
    rows = [{"date": "2025-01-01", "schema_version": 4, "overall": 3.5}]
    result = estimate_noise_floor(rows, ["date", "schema_version", "overall"])
    assert result.noise_sd == pytest.approx(0.70)
    assert result.estimator_selected == "within_cell"


def test_skill_arithmetic() -> None:
    from app.services.signals.quality import ModelQuality

    baseline_mae = 0.78
    mae = 0.61
    noise_floor_mae = 0.50
    skill = (baseline_mae - mae) / (baseline_mae - noise_floor_mae)
    assert skill == pytest.approx(0.61, abs=0.01)

    quality = ModelQuality(
        mae=mae,
        baseline_mae=baseline_mae,
        noise_floor_mae=noise_floor_mae,
        noise_sd=0.63,
        skill=skill,
        holdout_rmse=0.77,
        holdout_r2=0.34,
        r2_basis="variance",
    )
    assert quality.r2_basis == "variance"


def test_r2_basis_populated_on_compute() -> None:
    n = WARMUP_DAYS + 64
    rows = []
    start = datetime.date(2025, 1, 1)
    for i in range(n):
        d = start + datetime.timedelta(days=i)
        rows.append(
            {
                "date": d.isoformat(),
                "schema_version": 4,
                "overall": 3.4 + 0.01 * i,
                "sick": False,
                "photo_count": 1,
                "ingredient_count": 2,
                "hm_sleep_hours": 7.0,
            }
        )
    columns = [
        "date",
        "schema_version",
        "overall",
        "sick",
        "photo_count",
        "ingredient_count",
        "hm_sleep_hours",
    ]
    quality = compute_model_quality(rows, columns)
    assert quality.r2_basis == "variance"
    assert quality.noise_floor_mae == pytest.approx(quality.noise_sd * MAE_FROM_SD, rel=0.05)
