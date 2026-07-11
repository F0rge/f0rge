from __future__ import annotations

from typing import Optional


def _average_ranks(values: list[float]) -> list[float]:
    """Return average ranks (1-based) with tie handling.

    Tied values all receive the arithmetic mean of the ranks they would
    occupy, which is the standard tie-correction used in Spearman.
    """
    n = len(values)
    # Build a sorted index: list of (value, original_index)
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])

    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        # Advance j to the last element with the same value
        while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        # Average rank for this group (ranks are 1-based)
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg
        i = j + 1

    return ranks


def spearmanr(
    x: list[Optional[float]],
    y: list[Optional[float]],
) -> tuple[Optional[float], int]:
    """Compute Spearman rank correlation with pairwise-complete handling.

    Indices where either x[i] or y[i] is None are dropped before ranking.
    Returns (rho, n) where rho is None if n < 5 or if variance is zero.
    rho is rounded to 4 decimal places.
    """
    # Pairwise-complete: keep only indices where both values are present
    pairs = [(xi, yi) for xi, yi in zip(x, y) if xi is not None and yi is not None]
    n = len(pairs)

    if n < 5:
        return None, n

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    rx = _average_ranks(xs)
    ry = _average_ranks(ys)

    # Pearson correlation on the ranks (equivalent to tie-corrected Spearman)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n

    num = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    denom_x = sum((r - mean_rx) ** 2 for r in rx)
    denom_y = sum((r - mean_ry) ** 2 for r in ry)

    denom = (denom_x * denom_y) ** 0.5

    if denom == 0.0:
        # All ranks identical in at least one series (constant values) — undefined
        return None, n

    rho = num / denom
    return round(rho, 4), n


def categorize_feature(col: str) -> str:
    """Map a feature-matrix column name to a high-level category string."""
    _FOOD_COLS = {
        "histamine_load_sum",
        "histamine_load_max",
        "fodmap_oligos_sum",
        "fodmap_fructose_sum",
        "fodmap_polyols_sum",
        "fodmap_lactose_sum",
        "gluten_exposure",
        "dairy_exposure",
        "alcohol_units",
        "caffeine_servings",
        "had_alcohol",
        "had_caffeine",
        "photo_count",
        "ingredient_count",
        "manual_extra_dairy",
        "manual_extra_fodmap",
        "manual_extra_gluten",
        "manual_extra_histamine",
    }

    if col.startswith("supp_"):
        return "supplement"
    if col.startswith("tx_"):
        return "treatment"
    if col.startswith("sym_"):
        return "symptom"
    if col.startswith("hm_sleep"):
        return "sleep"
    if col.startswith("hm_"):
        return "metric"
    if col.startswith("wx_"):
        return "weather"
    if col in _FOOD_COLS:
        return "food"
    return "core"
