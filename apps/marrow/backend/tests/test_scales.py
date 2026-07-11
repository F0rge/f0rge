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
    # bloating never widened to 5-point -- it's 0..3 in every schema version,
    # so its worst stored value is still 3 at v4, not 5.
    assert normalize_scale("bloating", 3, 4) == 0.0


def test_bloating_domain_identical_across_schema_versions() -> None:
    for value in range(4):
        assert normalize_scale("bloating", value, 3) == normalize_scale("bloating", value, 4)


def test_joint_pain_domain_identical_across_schema_versions() -> None:
    for value in range(4):
        assert normalize_scale("joint_pain", value, 3) == normalize_scale("joint_pain", value, 4)


def test_v4_joint_pain_worst_normalizes_to_zero() -> None:
    assert normalize_scale("joint_pain", 3, 4) == 0.0


def test_neuro_v3_low_normalizes_to_zero() -> None:
    assert normalize_scale("neuro", -1, 3) == 0.0


def test_neuro_v3_high_normalizes_to_one() -> None:
    assert normalize_scale("neuro", 1, 3) == 1.0


def test_neuro_v4_low_normalizes_to_zero() -> None:
    assert normalize_scale("neuro", 1, 4) == 0.0


def test_neuro_v4_high_normalizes_to_one() -> None:
    assert normalize_scale("neuro", 5, 4) == 1.0


def test_higher_worse_field_inverts_with_raw_value() -> None:
    # stress: a higher raw value is a worse outcome, so its normalized score
    # must move the opposite direction from a higher_better field.
    assert normalize_scale("stress", 1, 3) > normalize_scale("stress", 3, 3)


def test_v4_stress_worst_normalizes_to_zero() -> None:
    assert normalize_scale("stress", 5, 4) == 0.0


def test_v4_midpoint_is_half() -> None:
    assert normalize_scale("sleep_quality", 3, 4) == 0.5
