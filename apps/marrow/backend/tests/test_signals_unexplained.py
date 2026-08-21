from __future__ import annotations

import datetime

from app.services.signals.attribution import AttributionContext
from app.services.signals.baseline import WARMUP_DAYS, BaselineResult
from app.services.signals.unexplained import (
    FlaggedDay,
    detect_unexplained,
    has_full_coverage,
    rank_tracker_proposals,
    residual_is_unexplained_bad,
)


def _baseline_stub(n_usable: int, y_hat: float = 3.5) -> BaselineResult:
    n = WARMUP_DAYS + n_usable
    return BaselineResult(
        dates=[
            (datetime.date(2025, 1, 1) + datetime.timedelta(days=i)).isoformat() for i in range(n)
        ],
        overall=[3.5] * n,
        y_hat=[y_hat] * n,
        residuals=[0.0] * n,
        L=[y_hat] * n,
        W=[0.0] * n,
        T=[0.0] * n,
        diagnostics=__import__(
            "app.services.signals.baseline", fromlist=["BaselineDiagnostics"]
        ).BaselineDiagnostics(
            days_total=n,
            days_v4=n,
            days_usable=n_usable,
            warmup_days=WARMUP_DAYS,
        ),
    )


def test_coverage_gate_no_photo_not_unexplained() -> None:
    row_without_photo = {
        "schema_version": 4,
        "overall": 2.0,
        "photo_count": 0,
        "hm_sleep_hours": 7.0,
    }
    assert not has_full_coverage({**row_without_photo, "date": "2025-02-01"})
    n_usable = 30
    baseline = _baseline_stub(n_usable)
    ctx = AttributionContext(
        effects=[],
        interactions=[],
        exposure_means={},
        interaction_both_means={},
        interaction_masks={},
        usable_indices=list(range(WARMUP_DAYS, WARMUP_DAYS + n_usable)),
    )
    rows = []
    for i in range(n_usable):
        d = datetime.date(2025, 1, 1) + datetime.timedelta(days=WARMUP_DAYS + i)
        rows.append(
            {
                "date": d.isoformat(),
                "schema_version": 4,
                "overall": 3.5,
                "photo_count": 1,
                "hm_sleep_hours": 7.0,
            }
        )
    last_date = rows[-1]["date"]
    rows[-1] = {"date": last_date, **row_without_photo}
    baseline.overall[-1] = 2.0
    result = detect_unexplained(
        rows,
        ["date", "schema_version", "overall", "photo_count", "hm_sleep_hours"],
        baseline,
        ctx,
        sigma_resid=0.5,
    )
    assert last_date in result.couldnt_score
    assert not any(last_date in ep.dates for ep in result.unexplained_bad)


def test_episode_clustering() -> None:
    from app.services.signals.unexplained import _cluster_episodes

    days = [
        FlaggedDay("2025-01-01", -2.0, 1.0, 3.0),
        FlaggedDay("2025-01-03", -2.1, 1.0, 3.1),
        FlaggedDay("2025-01-05", -2.2, 1.0, 3.2),
        FlaggedDay("2025-01-15", -2.0, 1.0, 3.0),
        FlaggedDay("2025-01-17", -2.1, 1.0, 3.1),
    ]
    episodes = _cluster_episodes(days, "bad")
    assert len(episodes) == 2
    assert len(episodes[0].dates) == 3
    assert len(episodes[1].dates) == 2


def test_relearning_guard_suppresses_list() -> None:
    n_usable = 28
    baseline = _baseline_stub(n_usable)
    ctx = AttributionContext(
        effects=[],
        interactions=[],
        exposure_means={},
        interaction_both_means={},
        interaction_masks={},
        usable_indices=list(range(WARMUP_DAYS, WARMUP_DAYS + n_usable)),
    )
    rows = []
    for i in range(n_usable):
        d = datetime.date(2025, 1, 1) + datetime.timedelta(days=WARMUP_DAYS + i)
        overall = 2.0 if i >= 10 else 3.5
        rows.append(
            {
                "date": d.isoformat(),
                "schema_version": 4,
                "overall": overall,
                "photo_count": 1,
                "hm_sleep_hours": 7.0,
                "afternoon_meal": False,
                "travel": False,
            }
        )
    for i in range(WARMUP_DAYS + 10, WARMUP_DAYS + n_usable):
        baseline.overall[i] = 2.0
        baseline.y_hat[i] = 3.5

    result = detect_unexplained(
        rows,
        ["date", "schema_version", "overall", "photo_count", "hm_sleep_hours"],
        baseline,
        ctx,
        sigma_resid=0.3,
    )
    assert result.relearning is True
    assert result.unexplained_bad == []
    assert result.unexplained_good == []


def test_tracker_ranking() -> None:
    flagged = [
        FlaggedDay("2025-01-01", -2.0, 1.0, 3.0, missing_inputs=["travel", "exercise"]),
        FlaggedDay("2025-01-02", -2.1, 1.0, 3.1, missing_inputs=["travel"]),
        FlaggedDay("2025-01-03", -2.2, 1.0, 3.2, missing_inputs=["travel", "afternoon_meal"]),
    ]
    proposals = rank_tracker_proposals(flagged)
    assert proposals[0].tracker_id == "travel"
    assert proposals[0].days_covered == 3


def test_residual_polarity_follows_good_direction() -> None:
    assert residual_is_unexplained_bad(-1.0, "up") is True
    assert residual_is_unexplained_bad(1.0, "up") is False
    assert residual_is_unexplained_bad(1.0, "down") is True
    assert residual_is_unexplained_bad(-1.0, "down") is False
    assert residual_is_unexplained_bad(-1.0, None) is True
