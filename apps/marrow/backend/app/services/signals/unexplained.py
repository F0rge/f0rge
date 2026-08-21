from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.services.signals.attribution import (
    AttributionContext,
    DayAttribution,
    build_attribution_context,
    compute_day_attribution,
)
from app.services.signals.baseline import BaselineResult, compute_baseline_residuals

UNEXPLAINED_SIGMA_MULT = 2.0  # §Layer 4 — |r| > 2·σ_resid
EPISODE_WINDOW_DAYS = 7  # §Layer 4 — cluster flagged days within 7 days
RELEARNING_WINDOW_DAYS = 14  # §Layer 4 — re-learning guard window
RELEARNING_FLAG_FRACTION = 0.15  # §Layer 4 — >15% flagged triggers re-learning

SLEEP_COLUMN = "hm_sleep_hours"

TRACKER_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("afternoon_meal", "Afternoon meal logged"),
    ("travel", "Travel day"),
    ("exercise", "Exercise logged"),
    ("meditation", "Meditation logged"),
    ("hydration", "Water intake logged"),
)


@dataclass
class FlaggedDay:
    date: str
    residual: float
    actual: float
    predicted: float
    missing_inputs: list[str] = field(default_factory=list)


@dataclass
class UnexplainedEpisode:
    dates: list[str]
    start_date: str
    end_date: str
    direction: str
    max_abs_residual: float


@dataclass
class TrackerProposal:
    tracker_id: str
    label: str
    days_covered: int


@dataclass
class UnexplainedResult:
    unexplained_bad: list[UnexplainedEpisode]
    unexplained_good: list[UnexplainedEpisode]
    couldnt_score: list[str]
    relearning: bool
    relearning_message: str
    tracker_proposals: list[TrackerProposal]
    sigma_resid: float


def _parse_date(date_val: str | datetime.date) -> datetime.date:
    if isinstance(date_val, datetime.date):
        return date_val
    return datetime.date.fromisoformat(str(date_val))


def has_sleep_data(row: dict) -> bool:
    return row.get(SLEEP_COLUMN) is not None


def has_confirmed_photo(row: dict) -> bool:
    photo_count = row.get("photo_count")
    if photo_count is None:
        return False
    return int(photo_count) >= 1


def is_checkin_complete(row: dict) -> bool:
    return row.get("overall") is not None and int(row.get("schema_version", 0)) >= 4


def has_full_coverage(row: dict) -> bool:
    """Full input coverage — ``signals_method.md`` §Layer 4 unexplained gate."""
    return has_sleep_data(row) and has_confirmed_photo(row) and is_checkin_complete(row)


def missing_tracker_inputs(row: dict) -> list[str]:
    """Tracker ids absent or falsy on this row."""
    missing: list[str] = []
    for tracker_id, _ in TRACKER_CANDIDATES:
        val = row.get(tracker_id)
        if val is None or val is False or val == 0:
            missing.append(tracker_id)
    return missing


def _sigma_resid(residuals: list[float]) -> float:
    if not residuals:
        return 0.0
    arr = np.asarray(residuals, dtype=float)
    return float(np.sqrt(np.mean(arr**2)))


def _cluster_episodes(flagged: list[FlaggedDay], direction: str) -> list[UnexplainedEpisode]:
    if not flagged:
        return []
    sorted_days = sorted(flagged, key=lambda d: d.date)
    episodes: list[UnexplainedEpisode] = []
    cluster: list[FlaggedDay] = [sorted_days[0]]
    for day in sorted_days[1:]:
        prev = _parse_date(cluster[-1].date)
        cur = _parse_date(day.date)
        if (cur - prev).days <= EPISODE_WINDOW_DAYS:
            cluster.append(day)
        else:
            episodes.append(_episode_from_cluster(cluster, direction))
            cluster = [day]
    episodes.append(_episode_from_cluster(cluster, direction))
    return episodes


def _episode_from_cluster(cluster: list[FlaggedDay], direction: str) -> UnexplainedEpisode:
    dates = [d.date for d in cluster]
    max_abs = max(abs(d.residual) for d in cluster)
    return UnexplainedEpisode(
        dates=dates,
        start_date=dates[0],
        end_date=dates[-1],
        direction=direction,
        max_abs_residual=max_abs,
    )


def _relearning_triggered(flagged_dates: list[str], all_dates: list[str]) -> bool:
    if not flagged_dates or not all_dates:
        return False
    flagged_set = set(flagged_dates)
    parsed_all = [_parse_date(d) for d in all_dates]
    min_date = min(parsed_all)
    max_date = max(parsed_all)
    cur = min_date
    while cur <= max_date:
        window_end = cur + datetime.timedelta(days=RELEARNING_WINDOW_DAYS - 1)
        window_dates = [d for d in all_dates if cur <= _parse_date(d) <= window_end]
        if len(window_dates) >= RELEARNING_WINDOW_DAYS:
            flagged_in_window = sum(1 for d in window_dates if d in flagged_set)
            if flagged_in_window / len(window_dates) > RELEARNING_FLAG_FRACTION:
                return True
        cur += datetime.timedelta(days=1)
    return False


def rank_tracker_proposals(flagged_days: list[FlaggedDay]) -> list[TrackerProposal]:
    """Rank trackers by how many flagged days they would cover if logged."""
    counts: dict[str, int] = {tid: 0 for tid, _ in TRACKER_CANDIDATES}
    for day in flagged_days:
        for tid in day.missing_inputs:
            if tid in counts:
                counts[tid] += 1
    proposals = [
        TrackerProposal(tracker_id=tid, label=label, days_covered=counts[tid])
        for tid, label in TRACKER_CANDIDATES
        if counts[tid] > 0
    ]
    proposals.sort(key=lambda p: (-p.days_covered, p.tracker_id))
    return proposals


def residual_is_unexplained_bad(residual: float, good_direction: Optional[str]) -> bool:
    """Whether a large residual is worse than expected for this outcome."""
    if good_direction == "down":
        return residual > 0
    return residual < 0


def detect_unexplained(
    rows: list[dict],
    columns: list[str],
    baseline: BaselineResult | None = None,
    ctx: AttributionContext | None = None,
    *,
    sigma_resid: float | None = None,
    good_direction: Optional[str] = None,
) -> UnexplainedResult:
    """Flag unexplained days, cluster episodes, apply re-learning guard."""
    base = baseline if baseline is not None else compute_baseline_residuals(rows, columns)
    context = ctx if ctx is not None else build_attribution_context(rows, columns, base)
    date_to_row = {str(r["date"]): r for r in rows}

    model_residuals: list[float] = []
    flagged_candidates: list[FlaggedDay] = []
    couldnt_score: list[str] = []
    day_attrs: list[tuple[str, DayAttribution, dict]] = []

    for idx in context.usable_indices:
        day_attr = compute_day_attribution(idx, base, context)
        if day_attr.residual is None or day_attr.actual is None:
            continue
        model_residuals.append(day_attr.residual)
        row = date_to_row.get(day_attr.date, {})
        day_attrs.append((day_attr.date, day_attr, row))

    sigma = sigma_resid if sigma_resid is not None else _sigma_resid(model_residuals)
    threshold = UNEXPLAINED_SIGMA_MULT * sigma

    flagged_bad: list[FlaggedDay] = []
    flagged_good: list[FlaggedDay] = []
    for _date, day_attr, row in day_attrs:
        if not has_full_coverage(row):
            if abs(day_attr.residual) > threshold:
                couldnt_score.append(day_attr.date)
            continue
        if abs(day_attr.residual) <= threshold:
            continue
        flagged_candidates.append(
            FlaggedDay(
                date=day_attr.date,
                residual=day_attr.residual,
                actual=float(day_attr.actual),
                predicted=day_attr.predicted,
                missing_inputs=missing_tracker_inputs(row),
            )
        )

    for day in flagged_candidates:
        if residual_is_unexplained_bad(day.residual, good_direction):
            flagged_bad.append(day)
        else:
            flagged_good.append(day)

    all_flagged_dates = [d.date for d in flagged_bad + flagged_good]
    all_usable_dates = [base.dates[i] for i in context.usable_indices]
    relearning = _relearning_triggered(all_flagged_dates, all_usable_dates)

    if relearning:
        return UnexplainedResult(
            unexplained_bad=[],
            unexplained_good=[],
            couldnt_score=sorted(couldnt_score),
            relearning=True,
            relearning_message="The model is re-learning your baseline",
            tracker_proposals=[],
            sigma_resid=sigma,
        )

    bad_episodes = _cluster_episodes(flagged_bad, "bad")
    good_episodes = _cluster_episodes(flagged_good, "good")
    proposals = rank_tracker_proposals(flagged_bad + flagged_good)

    return UnexplainedResult(
        unexplained_bad=bad_episodes,
        unexplained_good=good_episodes,
        couldnt_score=sorted(couldnt_score),
        relearning=False,
        relearning_message="",
        tracker_proposals=proposals,
        sigma_resid=sigma,
    )
