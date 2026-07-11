"""Tests for scripts.backfill_photo_analysis status filtering."""

from __future__ import annotations

from scripts.backfill_photo_analysis import SKIP_STATUSES

_TERMINAL_ANALYSIS_STATUSES = frozenset(
    {"complete", "confirmed", "analyzing", "needs_review"},
)


def test_skip_statuses_include_needs_review() -> None:
    """Low-confidence analyses awaiting user review must not be re-backfilled."""
    assert _TERMINAL_ANALYSIS_STATUSES <= SKIP_STATUSES
