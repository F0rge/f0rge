from __future__ import annotations

import datetime

from app.utils.streak import compute_streak

TODAY = datetime.date(2026, 7, 8)


def _days_before(n: int) -> list[datetime.date]:
    """n consecutive dates ending at TODAY, oldest first."""
    return [TODAY - datetime.timedelta(days=offset) for offset in range(n - 1, -1, -1)]


def test_empty_protocol_is_zero_zero() -> None:
    assert compute_streak([], TODAY) == (0, 0)


def test_clean_five_day_run() -> None:
    days = _days_before(5)
    completions = [(d, 2, 2) for d in days]
    current, best = compute_streak(completions, TODAY)
    assert current == 5
    assert best >= 5


def test_today_partial_does_not_break_streak() -> None:
    d1, d2, d3 = _days_before(3)
    completions = [(d1, 2, 2), (d2, 2, 2), (d3, 2, 1)]  # d3 == TODAY, partial
    current, best = compute_streak(completions, TODAY)
    assert current == 2  # today's partial isn't counted, but doesn't zero the streak
    assert best == 2


def test_missed_day_mid_window_resets_current_streak() -> None:
    d1, d2, d3 = _days_before(3)
    completions = [(d1, 2, 2), (d2, 2, 0), (d3, 2, 2)]  # d2 fully missed, d3 == TODAY complete
    current, best = compute_streak(completions, TODAY)
    assert current == 1  # only today counts; the miss on d2 stops the backward walk
    assert best == 1  # longest complete run is a single day either side of the miss


def test_streak_never_counts_before_protocol_start() -> None:
    """The walk must stop at the earliest date in the window, not run off the end."""
    days = _days_before(3)
    completions = [(d, 2, 2) for d in days]
    current, best = compute_streak(completions, TODAY)
    assert current == len(days) == 3
    assert best == 3


def test_gap_day_with_no_planned_doses_does_not_break_streak() -> None:
    """A day with planned == 0 (no dose-tracked treatment active) is outside
    the protocol window and is skipped, not treated as a miss."""
    d1, d2, d3 = _days_before(3)
    completions = [(d1, 2, 2), (d2, 0, 0), (d3, 2, 2)]  # d2 has nothing planned
    current, best = compute_streak(completions, TODAY)
    assert current == 2
    assert best == 2
