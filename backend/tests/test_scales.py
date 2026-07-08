from __future__ import annotations

from app.utils.scales import SCALE_DIRECTION, normalize_scale


def test_scale_direction_map_matches_documented_polarities() -> None:
    assert SCALE_DIRECTION == {
        "overall": "higher_better",
        "sleep_quality": "higher_better",
        "neuro": "higher_better",
        "bloating": "higher_worse",
        "stress": "higher_worse",
        "joint_pain": "higher_worse",
    }


def test_v3_overall_best_normalizes_to_one() -> None:
    assert normalize_scale("overall", 3, 3) == 1.0


def test_v4_overall_best_normalizes_to_one() -> None:
    assert normalize_scale("overall", 5, 4) == 1.0


def test_v3_bloating_worst_normalizes_to_zero() -> None:
    assert normalize_scale("bloating", 3, 3) == 0.0


def test_v4_bloating_worst_normalizes_to_zero() -> None:
    assert normalize_scale("bloating", 5, 4) == 0.0


def test_neuro_v3_low_normalizes_to_zero() -> None:
    assert normalize_scale("neuro", -1, 3) == 0.0


def test_neuro_v3_high_normalizes_to_one() -> None:
    assert normalize_scale("neuro", 1, 3) == 1.0


def test_higher_worse_field_inverts_with_raw_value() -> None:
    # stress: a higher raw value is a worse outcome, so its normalized score
    # must move the opposite direction from a higher_better field.
    assert normalize_scale("stress", 1, 3) > normalize_scale("stress", 3, 3)


def test_v4_midpoint_is_half() -> None:
    assert normalize_scale("sleep_quality", 3, 4) == 0.5
