from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.mcp.observability import instrument_resource
from app.services.diet_flags import FLAG_VOCAB

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_OVERVIEW_PATH = _BACKEND_ROOT / "docs" / "mcp" / "schema-overview.md"

_ENTRIES_SCHEMA = f"""# Entry table (`entries`)

One row per user per calendar date (`UNIQUE(user_id, date)`). All symptom scores are 0–10 integers unless noted.

## Core columns

| Column | Type | Description |
| --- | --- | --- |
| `id` | int | Primary key |
| `user_id` | uuid | Owner (RLS-scoped) |
| `date` | date | Check-in date |
| `schema_version` | int | Entry shape version (currently 4) |
| `entry_time` | timestamp | Optional time-of-day (naive UTC) |
| `period_of_day` | text | Optional period label |
| `overall` | int | Overall wellbeing 0–10 |
| `bloating` | int | Bloating severity 0–10 |
| `joint_pain` | int | Joint pain 0–10 |
| `neuro` | int | Neurological symptoms 0–10 |
| `sleep_quality` | int | Sleep quality 0–10 |
| `stress` | int | Stress level 0–10 |
| `stool_status` | text | `normal` \\| `abnormal` \\| `none` |
| `bristol_type` | int | Bristol scale 1–7 when recorded |
| `stool_completeness` | text | `complete` \\| `incomplete` |
| `sick` | bool | Felt sick |
| `hot_shower` | bool | Hot shower exposure |
| `alcohol_units` | int | Nullable count |
| `caffeine_servings` | int | Nullable count |
| `diet_risk` | text | Legacy CSV of user-added diet flags (audit trail) |
| `supplements` | text | Free-text supplements taken |
| `medications_json` | jsonb | List of medication intake events |
| `notes` | text | Free-text notes |
| `symptoms_json` | jsonb | Per-symptom severities keyed by catalog key |
| `symptom_events_json` | jsonb | Timed symptom stamps (`key`, `severity`, `time`) |
| `created_at` / `updated_at` | timestamp | Audit timestamps |

## `symptoms_json`

Dynamic symptom scores keyed by `symptom_catalog.key` (e.g. `{{"vss": 6, "tinnitus": 3}}`). Empty object when no extra symptoms logged. Static entry columns (`overall`, `bloating`, etc.) remain the primary daily metrics.

## `symptom_events_json`

List of intra-day stamps, same clock convention as `medications_json`:
`[{{"key": "vss", "severity": 7, "time": "15:20"}}]`. `symptoms_json` is the day's current score; this list is when it was logged.

## Diet flags and `effective_flags`

Photo-confirmed ingredients drive computed flags via `compute_photo_signal(entry)`:
- Aggregates confirmed `photo_ingredients` under the entry's photos
- Applies histamine threshold (score ≥ 2 → `high-histamine`), FODMAP subcategory `high`, `contains_gluten`, `contains_dairy`
- Respects per-meal `gluten_free_confirmed` / `lactose_free_confirmed` overrides on `photo_analyses`

User-added flags come from `parse_diet_risk_csv(entry.diet_risk)` — parses the legacy CSV, drops `normal` / `not-sure`, filters to vocabulary:

`{", ".join(sorted(FLAG_VOCAB))}`

**Effective flags** = sorted union of photo-derived flags and user-added flags. MCP `get_entry` / `list_entries` expose this as `effective_flags`.

## Related resources

- `marrow://schema/photos` — how photos feed photo-derived flags
- `marrow://catalog/dietary-ingredients` — ingredient scoring reference data
"""

_PHOTOS_SCHEMA = """# Photos, analyses, and ingredients

## `photos`

| Column | Type | Description |
| --- | --- | --- |
| `id` | int | Primary key |
| `user_id` | uuid | Owner (RLS-scoped) |
| `entry_id` | int | FK → `entries.id` (cascade delete) |
| `meal_id` | int | FK → `meals.id` — shared meal identity |
| `filename` | text | Stored JPEG name |
| `label` | text | Optional user label |
| `meal_time` | timestamp | Optional per-photo meal time (naive UTC) |
| `source_photo_id` | int | Optional FK for cloned/tagged photos |
| `tagged_by_user_id` | uuid | Social meal-tag attribution |
| `created_at` | timestamp | Upload time |

`Entry.photos` is a one-to-many relationship. Each photo belongs to exactly one entry and one meal.

## `photo_analyses`

One analysis row per meal (`meal_id` UNIQUE). Linked to photos via `meal_id` (not `photo_id` alone).

| Column | Type | Description |
| --- | --- | --- |
| `id` | int | Primary key |
| `meal_id` | int | FK → `meals.id` |
| `photo_id` | int | Optional FK → `photos.id` (legacy pointer) |
| `status` | text | `pending` \\| `confirmed` \\| `failed` |
| `dish_name` / `cuisine` | text | Vision model output |
| `gluten_free_confirmed` | bool | User override — suppresses gluten flag |
| `lactose_free_confirmed` | bool | User override — drops lactose from FODMAP check |
| `ingredients` | relation | One-to-many → `photo_ingredients` |

`Photo.analysis` is a viewonly relationship: `Photo.meal_id == PhotoAnalysis.meal_id`.

## `photo_ingredients`

Per-ingredient rows scored against the dietary catalog.

| Column | Type | Description |
| --- | --- | --- |
| `analysis_id` | int | FK → `photo_analyses.id` |
| `name` | text | Display name from vision or user edit |
| `canonical_name` | text | Resolved catalog name when matched |
| `visible` | bool | Hidden ingredients excluded from diet signal |
| `confidence` | float | Model confidence |
| `histamine_score` | int | 0–3 SIGHI-style score |
| `fodmap_*` | text | Per-axis FODMAP level (`low`/`moderate`/`high`) |
| `contains_gluten` / `contains_dairy` | bool | Allergen flags |

## Relationship summary

```
entries 1──* photos *──1 meals 1──0..1 photo_analyses 1──* photo_ingredients
```

Only `photo_analyses.status = 'confirmed'` ingredients contribute to entry diet flags.
"""


def register_schema_resources(server: FastMCP) -> None:
    @server.resource(
        "marrow://schema/overview",
        name="schema_overview",
        description=(
            "Database overview: RLS tenancy, healthtracker_ro read role, and table groups. "
            "Load first before writing SQL or interpreting cross-table joins."
        ),
        mime_type="text/markdown",
    )
    @instrument_resource("schema_overview")
    async def schema_overview() -> str:
        return _SCHEMA_OVERVIEW_PATH.read_text(encoding="utf-8")

    @server.resource(
        "marrow://schema/entries",
        name="schema_entries",
        description=(
            "Entry column reference, symptoms_json shape, and effective_flags computation "
            "(photo signal + user diet_risk CSV). Load before querying or summarizing entries."
        ),
        mime_type="text/markdown",
    )
    @instrument_resource("schema_entries")
    async def schema_entries() -> str:
        return _ENTRIES_SCHEMA

    @server.resource(
        "marrow://schema/photos",
        name="schema_photos",
        description=(
            "Photos, photo_analyses, and photo_ingredients relationships and key columns. "
            "Load before joining meal photos to food analysis or diet flags."
        ),
        mime_type="text/markdown",
    )
    @instrument_resource("schema_photos")
    async def schema_photos() -> str:
        return _PHOTOS_SCHEMA
