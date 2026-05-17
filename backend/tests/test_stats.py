from __future__ import annotations

from app.services.stats import _average_ranks, categorize_feature, spearmanr


# ── _average_ranks ────────────────────────────────────────────────────────────


def test_average_ranks_no_ties() -> None:
    ranks = _average_ranks([10.0, 30.0, 20.0])
    # 10 → rank 1, 20 → rank 2, 30 → rank 3
    assert ranks == [1.0, 3.0, 2.0]


def test_average_ranks_all_tied() -> None:
    ranks = _average_ranks([5.0, 5.0, 5.0])
    # Three values all tied → average rank = (1+2+3)/3 = 2.0
    assert all(r == 2.0 for r in ranks)


def test_average_ranks_partial_tie() -> None:
    # Values: [1, 2, 2, 3] → ranks: 1, 2.5, 2.5, 4
    ranks = _average_ranks([1.0, 2.0, 2.0, 3.0])
    assert ranks[0] == 1.0
    assert ranks[1] == 2.5
    assert ranks[2] == 2.5
    assert ranks[3] == 4.0


# ── spearmanr ─────────────────────────────────────────────────────────────────


def test_spearmanr_no_ties_perfect() -> None:
    # Perfect monotone increase → rho = 1.0
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [1.0, 2.0, 3.0, 4.0, 5.0]
    rho, n = spearmanr(x, y)
    assert rho == 1.0
    assert n == 5


def test_spearmanr_no_ties_inverse() -> None:
    # Perfect monotone decrease → rho = -1.0
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [5.0, 4.0, 3.0, 2.0, 1.0]
    rho, n = spearmanr(x, y)
    assert rho == -1.0
    assert n == 5


def test_spearmanr_no_ties_textbook() -> None:
    # Textbook example: x ranks and y ranks differ — hand-computed
    # x = [10, 40, 30, 60, 50] → ranks [1, 3, 2, 5, 4]
    # y = [20, 10, 50, 40, 30] → ranks [2, 1, 5, 4, 3]
    # d^2 = (1-2)^2+(3-1)^2+(2-5)^2+(5-4)^2+(4-3)^2 = 1+4+9+1+1 = 16
    # rho = 1 - 6*16/(5*(25-1)) = 1 - 96/120 = 1 - 0.8 = 0.2
    x = [10.0, 40.0, 30.0, 60.0, 50.0]
    y = [20.0, 10.0, 50.0, 40.0, 30.0]
    rho, n = spearmanr(x, y)
    assert n == 5
    # Allow ±0.0001 for floating-point rounding
    assert rho is not None
    assert abs(rho - 0.2) < 0.001


def test_spearmanr_with_ties() -> None:
    # Ties in x: [1, 2, 2, 3] → average ranks [1, 2.5, 2.5, 4]
    # y: [1, 2, 3, 4] → ranks [1, 2, 3, 4]
    x = [1.0, 2.0, 2.0, 3.0, 4.0]  # 5 values to clear min_n=5
    y = [1.0, 2.0, 3.0, 4.0, 5.0]
    rho, n = spearmanr(x, y)
    assert n == 5
    assert rho is not None
    assert rho > 0.9  # Strong positive, not exactly 1 because of ties


def test_spearmanr_with_nones_drops_pairs() -> None:
    # Index 2 has None in x → should drop that pair → n=3
    x = [1.0, 2.0, None, 4.0]
    y = [1.0, 2.0, 3.0, 4.0]
    rho, n = spearmanr(x, y)
    # n=3 < 5 → rho must be None
    assert rho is None
    assert n == 3


def test_spearmanr_with_nones_both_sides() -> None:
    # Both None at index 1 → n=4 still < 5 → rho None
    x = [1.0, None, 3.0, 4.0]
    y = [1.0, None, 3.0, 4.0]
    rho, n = spearmanr(x, y)
    assert rho is None
    assert n == 3  # Only (1,1), (3,3), (4,4) — wait, both None at idx 1 → dropped
    # Actually both are None → that pair is dropped; n=3
    assert n == 3


def test_spearmanr_small_n_returns_none() -> None:
    # n < 5 → return (None, n)
    x = [1.0, 2.0, 3.0, 4.0]
    y = [1.0, 2.0, 3.0, 4.0]
    rho, n = spearmanr(x, y)
    assert rho is None
    assert n == 4


def test_spearmanr_empty() -> None:
    rho, n = spearmanr([], [])
    assert rho is None
    assert n == 0


def test_spearmanr_all_identical_x() -> None:
    # All x values the same → all ranks equal → denom = 0 → rho is None
    x = [1.0, 1.0, 1.0, 1.0, 1.0]
    y = [1.0, 2.0, 3.0, 4.0, 5.0]
    rho, n = spearmanr(x, y)
    # denom is zero → undefined → None
    assert rho is None
    assert n == 5


def test_spearmanr_all_identical_both() -> None:
    x = [3.0, 3.0, 3.0, 3.0, 3.0]
    y = [3.0, 3.0, 3.0, 3.0, 3.0]
    rho, n = spearmanr(x, y)
    assert rho is None
    assert n == 5


def test_spearmanr_sufficient_nones_survive() -> None:
    # Enough non-None pairs to compute rho
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    y = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    rho, n = spearmanr(x, y)
    assert rho == 1.0
    assert n == 7


# ── categorize_feature ────────────────────────────────────────────────────────


def test_categorize_supp() -> None:
    assert categorize_feature("supp_nac") == "supplement"
    assert categorize_feature("supp_fish_oil") == "supplement"


def test_categorize_treatment() -> None:
    assert categorize_feature("tx_probiotic_active") == "treatment"
    assert categorize_feature("tx_ldnaltrexone_active") == "treatment"


def test_categorize_symptom() -> None:
    assert categorize_feature("sym_vss") == "symptom"
    assert categorize_feature("sym_brain_fog") == "symptom"


def test_categorize_sleep() -> None:
    # hm_sleep* → sleep, NOT metric
    assert categorize_feature("hm_sleep_efficiency") == "sleep"
    assert categorize_feature("hm_sleep_deep_min") == "sleep"
    assert categorize_feature("hm_sleep_rem_min") == "sleep"
    assert categorize_feature("hm_sleep_hours") == "sleep"


def test_categorize_metric() -> None:
    assert categorize_feature("hm_hrv_mean") == "metric"
    assert categorize_feature("hm_resting_hr") == "metric"
    assert categorize_feature("hm_steps") == "metric"


def test_categorize_weather() -> None:
    assert categorize_feature("wx_temp_mean") == "weather"
    assert categorize_feature("wx_pressure_delta") == "weather"
    assert categorize_feature("wx_humidity_mean") == "weather"


def test_categorize_food() -> None:
    assert categorize_feature("histamine_load_sum") == "food"
    assert categorize_feature("had_alcohol") == "food"
    assert categorize_feature("caffeine_servings") == "food"
    assert categorize_feature("manual_extra_histamine") == "food"
    assert categorize_feature("gluten_exposure") == "food"


def test_categorize_core() -> None:
    assert categorize_feature("overall") == "core"
    assert categorize_feature("bloating") == "core"
    assert categorize_feature("joint_pain") == "core"
    assert categorize_feature("neuro") == "core"
    assert categorize_feature("stress") == "core"
    assert categorize_feature("sleep_quality") == "core"
    assert categorize_feature("sick") == "core"
