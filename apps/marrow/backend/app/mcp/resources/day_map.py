from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp.observability import instrument_resource

_CHECK_IN_DAY_MAP = """# Daily check-in (one row per calendar date)

A **day** is the primary unit of logging. One `entries` row per user per date.

## Core scores (0–10, optional until set)
- `overall`, `bloating`, `joint_pain`, `neuro`, `sleep_quality`, `stress`

## Gut
- `stool_status`: `normal` | `abnormal` | `none`
- `bristol_type`: 1–7 when recorded
- `stool_completeness`: `complete` | `incomplete`

## Extra symptoms
- `symptoms_json`: map of catalog keys → severity (e.g. `{"vss": 6}`)
- `symptom_events`: timed flares `[{"key": "vss", "severity": 7, "time": "15:20"}]`

## Notes and lifestyle
- `notes` (free text)
- `sick`, `hot_shower`, `alcohol_units`, `caffeine_servings`, `supplements`

## Meals (separate tools)
Meals attach to the day's entry via photos/meals. Use `get_day` for scores and meal summaries;
`get_meal` for one meal's ingredients, tags, and photo metadata.

## MCP write tools for a day
- `save_day` — upsert scores, symptoms, stool fields, notes
- `log_flare` — append a timed symptom event (and update `symptoms_json` for that key)
"""


def register_day_map_resources(server: FastMCP) -> None:
    @server.resource(
        "marrow://reference/check-in-day-map",
        name="check_in_day_map",
        description=(
            "Short reference for what a daily check-in contains — scores, gut, symptoms, notes. "
            "Not user data."
        ),
        mime_type="text/markdown",
    )
    @instrument_resource("check_in_day_map")
    async def check_in_day_map() -> str:
        return _CHECK_IN_DAY_MAP
