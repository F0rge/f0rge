from __future__ import annotations

import numpy as np

from app.services.signals.interactions import (
    ESTABLISHED_CO_EXPOSED,
    compute_excess,
    compute_excess_from_masks,
)


def _plant_2x2(
    n_neither: int,
    n_a_only: int,
    n_b_only: int,
    n_both: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = n_neither + n_a_only + n_b_only + n_both
    labels = (
        [0] * n_neither
        + [1] * n_a_only
        + [2] * n_b_only
        + [3] * n_both
    )
    rng.shuffle(labels)
    mask_a = np.zeros(n, dtype=bool)
    mask_b = np.zeros(n, dtype=bool)
    residuals = np.zeros(n)
    for i, lab in enumerate(labels):
        if lab == 0:
            residuals[i] = 0.0
        elif lab == 1:
            mask_a[i] = True
            residuals[i] = -0.58
        elif lab == 2:
            mask_b[i] = True
            residuals[i] = -0.44
        else:
            mask_a[i] = True
            mask_b[i] = True
            residuals[i] = -1.34
    return residuals, mask_a, mask_b


def test_interaction_arithmetic_identity() -> None:
    rng = np.random.default_rng(42)
    residuals, mask_a, mask_b = _plant_2x2(47, 16, 16, 11, rng)
    excess, both_mn, a_mn, b_mn, additive = compute_excess(residuals, mask_a, mask_b)
    assert abs(excess - (-0.32)) < 0.1
    assert abs(additive + excess - both_mn) < 1e-9


def test_interaction_never_established_below_20_coexposed() -> None:
    rng = np.random.default_rng(7)
    residuals, mask_a, mask_b = _plant_2x2(60, 10, 10, 11, rng)
    co = int((mask_a & mask_b).sum())
    assert co < ESTABLISHED_CO_EXPOSED
    result = compute_excess_from_masks(
        residuals, mask_a, mask_b, bootstrap_n=200, rng=rng
    )
    assert result.tier != "established"
    assert result.co_exposed_days < ESTABLISHED_CO_EXPOSED
