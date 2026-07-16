from __future__ import annotations

import datetime

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import UserMessage

from app.mcp.tools._common import _validate_date


def _validate_date_range(start: datetime.date, end: datetime.date) -> None:
    if start > end:
        raise ValueError(f"start_date ({start}) must be on or before end_date ({end})")


def _require_non_empty(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field} is required and cannot be empty")
    return stripped


def register_workflow_prompts(server: FastMCP) -> None:
    @server.prompt(
        name="symptom_diet_correlation",
        description=(
            "Observational workflow: correlate symptom scores with diet flags "
            "from meal photos over a date range (research notes only — not diagnosis)."
        ),
    )
    def symptom_diet_correlation(start_date: str, end_date: str) -> list[UserMessage]:
        """Correlate symptoms with photo-derived diet flags over a date range."""
        start = _validate_date(start_date, "start_date")
        end = _validate_date(end_date, "end_date")
        _validate_date_range(start, end)

        return [
            UserMessage(
                f"You are reviewing Leo's health log for observational research notes "
                f"from {start} through {end}. Do not diagnose or prescribe — describe "
                f"patterns and correlations only."
            ),
            UserMessage(
                "Step 1 — understand the entry schema.\n"
                "Read resource `marrow://schema/entries` to learn symptom columns, "
                "`symptoms_json`, and how `effective_flags` merges photo-derived and "
                "user-added diet flags."
            ),
            UserMessage(
                "Step 2 — load entries in range.\n"
                f"Call tool `list_entries` with start_date={start!s} and "
                f"end_date={end!s}. Review core scores (overall, bloating, joint_pain, "
                "neuro, sleep_quality, stress) plus `symptoms_json` and `effective_flags` "
                "for each day."
            ),
            UserMessage(
                "Step 3 — deepen diet context on symptomatic days.\n"
                "For days with elevated symptom scores (your judgment from Step 2), call "
                "`list_photos_for_entry` for that date, then `get_photo_analysis` for each "
                "photo that has an analysis. Note dish names, confirmed ingredients, and "
                "diet-related flags."
            ),
            UserMessage(
                "Step 4 — summarize correlations.\n"
                "Compare `effective_flags` and ingredient-level signals against symptom "
                "scores across the range. Call out same-day and lagged patterns where "
                "data supports them. Flag gaps (missing entries, unanalyzed photos). "
                "Use tenant-scoped tools only — do not use `read_sql` or attempt to "
                "bypass row-level security."
            ),
        ]

    @server.prompt(
        name="lab_marker_review",
        description=(
            "Observational workflow: summarize lab marker history, units, and flags "
            "for research notes (not clinical interpretation)."
        ),
    )
    def lab_marker_review(marker_canonical_name: str) -> list[UserMessage]:
        """Summarize lab marker trend from catalog context and history."""
        marker = _require_non_empty(marker_canonical_name, "marker_canonical_name")

        return [
            UserMessage(
                f"You are reviewing lab marker {marker!r} for observational research "
                "notes. Do not diagnose or prescribe — describe trends and flag changes "
                "only."
            ),
            UserMessage(
                "Step 1 — load marker reference.\n"
                "Read resource `marrow://catalog/lab-markers` to confirm display name, "
                f"canonical name, and common units for {marker!r}."
            ),
            UserMessage(
                "Step 2 — load history.\n"
                f"Call tool `get_lab_history` with marker_canonical_name={marker!r}. "
                "Results are newest-first, capped at 200 rows."
            ),
            UserMessage(
                "Step 3 — summarize for research notes.\n"
                "Report value trend over time, units used, reference-range flags "
                "(normal/high/low/etc.), and any gaps in testing frequency. Note when "
                "units change between draws. Use tenant-scoped tools only — do not use "
                "`read_sql` or attempt to bypass row-level security."
            ),
        ]

    @server.prompt(
        name="daily_checkin_summary",
        description=(
            "Observational workflow: structured daily narrative from entry, weather, "
            "and meal photos (research notes only)."
        ),
    )
    def daily_checkin_summary(date: str) -> list[UserMessage]:
        """Build a structured daily check-in narrative for one date."""
        day = _validate_date(date, "date")

        return [
            UserMessage(
                f"You are summarizing the health check-in for {day} as observational "
                "research notes. Do not diagnose or prescribe."
            ),
            UserMessage(
                "Step 1 — load the entry.\n"
                f"Call tool `get_entry` with date={day!s}. If null, note that no entry "
                "exists and stop — do not invent data."
            ),
            UserMessage(
                "Step 2 — add environmental context.\n"
                f"Call tool `get_weather_for_entry` with date={day!s}. Include "
                "pressure, temperature, and humidity summaries when present."
            ),
            UserMessage(
                "Step 3 — add meal context.\n"
                f"Call tool `list_photos_for_entry` with date={day!s}. For photos with "
                "analyses, call `get_photo_analysis` and weave dish names, ingredients, "
                "and `effective_flags` into the narrative."
            ),
            UserMessage(
                "Step 4 — write the daily narrative.\n"
                "Produce a structured summary: symptom scores (including "
                "`symptoms_json`), lifestyle factors (sleep, stress, supplements, sick, "
                "alcohol/caffeine), diet flags, weather, and meals. Highlight notable "
                "same-day juxtapositions without causal claims. Use tenant-scoped tools "
                "only — do not use `read_sql` or attempt to bypass row-level security."
            ),
        ]
