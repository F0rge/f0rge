from __future__ import annotations

import datetime
import time

import numpy as np
import pytest

from app.services.signals.baseline import WARMUP_DAYS, compute_baseline_residuals
from app.services.signals.effects import (
    CV_FOLDS,
    _contiguous_folds,
    estimate_all_effects,
    estimate_effect_from_arrays,
    select_threshold_c,
)


def _plant_binary_effect(
    n: int,
    effect: float,
    prevalence: float,
    rng: np.random.Generator,
    *,
    residuals_base: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    if residuals_base is None:
        residuals = rng.normal(0, 0.4, n)
    else:
        residuals = residuals_base.copy()
    n_exposed = max(5, int(round(n * prevalence)))
    exposed = np.zeros(n, dtype=bool)
    step = max(1, n // n_exposed)
    for i in range(0, n, step):
        if exposed.sum() >= n_exposed:
            break
        exposed[i] = True
    residuals[exposed] += effect
    x = exposed.astype(float)
    return residuals, x


def test_recovery_planted_effect() -> None:
    rng = np.random.default_rng(7)
    residuals = rng.normal(0, 0.4, 92)
    exposed = rng.random(92) < 0.30
    residuals[exposed] += 0.6
    x = exposed.astype(float)
    result = estimate_effect_from_arrays(residuals, x, shape="binary", bootstrap_n=400, rng=rng)
    assert result.theta_hat is not None
    assert abs(result.theta_hat - 0.6) < 0.1
    assert result.ci_lower is not None and result.ci_upper is not None
    assert result.ci_lower <= 0.6 <= result.ci_upper


def test_balance_invariance() -> None:
    rng = np.random.default_rng(11)
    base = rng.normal(0, 0.4, 92)
    r9, x9 = _plant_binary_effect(92, effect=0.6, prevalence=0.09, rng=rng, residuals_base=base)
    r45, x45 = _plant_binary_effect(92, effect=0.6, prevalence=0.45, rng=rng, residuals_base=base)
    res9 = estimate_effect_from_arrays(r9, x9, shape="binary", bootstrap_n=200, rng=rng)
    res45 = estimate_effect_from_arrays(r45, x45, shape="binary", bootstrap_n=200, rng=rng)
    assert res9.theta_hat is not None and res45.theta_hat is not None
    assert abs(res9.theta_hat - res45.theta_hat) < 0.1


def test_bootstrap_coverage() -> None:
    """Coverage ~92–98% over synthetic; B=150 in test for speed (production B=2000)."""
    covers = 0
    n_sims = 80
    for i in range(n_sims):
        sim_rng = np.random.default_rng(i + 1000)
        residuals, x = _plant_binary_effect(92, effect=0.5, prevalence=0.35, rng=sim_rng)
        result = estimate_effect_from_arrays(
            residuals, x, shape="binary", bootstrap_n=150, rng=sim_rng
        )
        assert result.ci_lower is not None and result.ci_upper is not None
        if result.ci_lower <= 0.5 <= result.ci_upper:
            covers += 1
    rate = covers / n_sims
    assert 0.85 <= rate <= 0.99, f"coverage rate {rate:.2f} outside tolerance"


def test_bootstrap_wider_than_naive_on_clustered_exposure() -> None:
    rng = np.random.default_rng(9)
    n = 92
    residuals = np.zeros(n)
    residuals[0] = float(rng.normal())
    for i in range(1, n):
        residuals[i] = 0.4 * residuals[i - 1] + float(rng.normal(0, 0.4))
    exposed = np.zeros(n, dtype=bool)
    for i in range(n):
        if i % 7 in (5, 6) and rng.random() < 0.35:
            exposed[i] = True
    residuals[exposed] -= 0.45
    x = exposed.astype(float)
    result = estimate_effect_from_arrays(residuals, x, shape="binary", bootstrap_n=400, rng=rng)
    assert result.bootstrap_se is not None and result.naive_se is not None
    assert result.ci_lower is not None and result.ci_upper is not None
    boot_hw = (result.ci_upper - result.ci_lower) / 2
    naive_hw = 1.96 * result.naive_se
    assert boot_hw > naive_hw * 1.05
    assert result.se_ratio is not None and result.se_ratio > 1.05


def test_in_fold_threshold_isolation() -> None:
    rng = np.random.default_rng(3)
    n = 92
    x = rng.uniform(0, 10, n)
    residuals = rng.normal(0, 0.3, n)
    valid = np.ones(n, dtype=bool)
    folds = _contiguous_folds(n, CV_FOLDS)
    train_mask = folds != 0
    c_before = select_threshold_c(residuals, x, valid, train_mask)
    x_mutated = x.copy()
    x_mutated[folds == 0] = 999.0
    c_after = select_threshold_c(residuals, x_mutated, valid, train_mask)
    assert c_before == c_after


def test_runs_precondition_single_block() -> None:
    rng = np.random.default_rng(5)
    n = 92
    exposed = np.zeros(n, dtype=bool)
    exposed[20:35] = True
    x = exposed.astype(float)
    residuals = rng.normal(0, 0.3, n)
    residuals[exposed] -= 0.5
    result = estimate_effect_from_arrays(residuals, x, shape="binary", bootstrap_n=100, rng=rng)
    assert result.tier == "insufficient"
    assert "runs" in result.reason.lower()


def test_u_shape_threshold_visible() -> None:
    rng = np.random.default_rng(13)
    n = 92
    x = np.full(n, 0.5)
    residuals = np.full(n, -0.15)
    for start in range(0, n, 18):
        x[start : start + 4] = 0.08
        residuals[start : start + 4] = 0.70
        x[start + 9 : start + 13] = 0.92
        residuals[start + 9 : start + 13] = 0.65
    residuals += rng.normal(0, 0.04, n)
    result = estimate_effect_from_arrays(residuals, x, shape="threshold", bootstrap_n=200, rng=rng)
    assert result.theta_hat is not None
    assert abs(result.theta_hat) >= 0.25
    assert result.tier != "insufficient"


def _make_row(date: datetime.date, overall: float, **extra: object) -> dict:
    row: dict = {
        "date": date.isoformat(),
        "schema_version": 4,
        "overall": overall,
        "sick": False,
        "photo_count": 1,
        "ingredient_count": 3,
    }
    row.update(extra)
    return row


def test_perf_full_pass_under_8s() -> None:
    """~8–12 drivers, B=2000, K=5 — report wall-clock (production defaults)."""
    rng = np.random.default_rng(0)
    start = datetime.date(2025, 1, 1)
    n_days = WARMUP_DAYS + 92
    columns = [
        "date",
        "schema_version",
        "overall",
        "sick",
        "photo_count",
        "ingredient_count",
        "had_alcohol",
        "histamine_load_sum",
        "hm_sleep_hours",
        "gluten_exposure",
        "dairy_exposure",
        "hm_steps",
        "wx_temp_mean",
        "caffeine_servings",
        "supp_magnesium",
    ]
    rows = []
    for i in range(n_days):
        d = start + datetime.timedelta(days=i)
        overall = 3.4 + rng.normal(0, 0.4)
        rows.append(
            _make_row(
                d,
                overall,
                had_alcohol=bool(i % 7 == 5),
                histamine_load_sum=float(rng.uniform(0, 5)),
                hm_sleep_hours=float(rng.uniform(5, 9)),
                gluten_exposure=bool(i % 4 == 0),
                dairy_exposure=bool(i % 5 == 0),
                hm_steps=float(rng.integers(1000, 12000)),
                wx_temp_mean=float(rng.uniform(5, 25)),
                caffeine_servings=float(rng.integers(0, 4)),
                supp_magnesium=bool(i % 3 == 0),
            )
        )

    t0 = time.perf_counter()
    baseline = compute_baseline_residuals(rows, columns)
    effects = estimate_all_effects(rows, columns, baseline, bootstrap_n=2000, rng=rng)
    elapsed = time.perf_counter() - t0
    assert len(effects) >= 8
    assert elapsed < 8.0, f"perf {elapsed:.2f}s exceeded 8s budget"
    pytest.perf_seconds = elapsed  # noqa: B018 — for reporting
