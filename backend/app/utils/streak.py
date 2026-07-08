from __future__ import annotations

import datetime
from typing import Sequence, Tuple

DayCompletion = Tuple[datetime.date, int, int]  # (date, planned, taken)


def _is_complete(planned: int, taken: int) -> bool:
    return planned > 0 and taken >= planned


def compute_streak(
    day_completions: Sequence[DayCompletion],
    today: datetime.date,
) -> Tuple[int, int]:
    """Current + best adherence streak over a protocol window.

    ``day_completions`` covers every protocol day from the earliest
    dose-tracked treatment's start_date through ``today``. A day is
    "complete" iff planned > 0 and taken >= planned. Days with planned == 0
    (no dose-tracked treatment active that day) are outside the protocol
    window and are skipped without breaking either streak.

    current_streak walks backward from today: today itself doesn't break the
    streak when incomplete (it's simply not counted, so it stays "in
    progress"), but the first incomplete planned-day *before* today stops the
    walk.
    """
    lookup = {day: (planned, taken) for day, planned, taken in day_completions}
    if not lookup:
        return 0, 0
    earliest = min(lookup)

    current = 0
    day = today
    one_day = datetime.timedelta(days=1)
    while day >= earliest:
        planned, taken = lookup.get(day, (0, 0))
        if planned == 0:
            day -= one_day
            continue
        if _is_complete(planned, taken):
            current += 1
            day -= one_day
            continue
        if day == today:
            day -= one_day
            continue
        break

    best = 0
    run = 0
    for d in sorted(lookup):
        planned, taken = lookup[d]
        if planned == 0:
            continue
        if _is_complete(planned, taken):
            run += 1
            best = max(best, run)
        else:
            run = 0

    return current, best
