# Marrow MCP — Overview and Data Model

Reference for agents using Leo's health tracker through the Marrow MCP server
(`app/mcp/`, FastMCP name `marrow`, endpoint `https://mcp.marrow-health.com/mcp`, Bearer token auth).

The MCP server exposes **typed tools and two reference resources only**. There is no raw SQL
tool, no schema-dump resources, and no prompts. The registered surface is pinned by
`tests/test_mcp_surface.py::test_registered_tool_names`; update that test, this file, and the
day-map resource (`app/mcp/resources/day_map.py`) together when a tool is added or removed.

## Tools (21)

| Area | Tool | Kind | Notes |
| --- | --- | --- | --- |
| Days | `get_day(date)` | read | One check-in: scores, symptoms, supplements (list of keys), notes, meal summaries |
| Days | `list_days(start_date, end_date)` | read | Inclusive range, max 200; short summaries incl. `supplements` |
| Days | `save_day(date, overall?, bloating?, joint_pain?, neuro?, sleep_quality?, stress?, stool_status?, bristol_type?, stool_completeness?, notes?, symptoms_json?)` | write | Create or partially update a check-in |
| Days | `log_flare(date, key, severity, time?)` | write | Timed symptom event (+ `symptoms_json`) |
| Supplements | `list_supplements(include_archived=False)` | read | Per-user supplement catalog (keys for `set_supplements`) |
| Supplements | `set_supplements(keys, date?, mode='replace')` | write | `replace` / `add` / `remove` the day's supplement keys |
| Meals | `get_meal(photo_id)` | read | Ingredients, tags, photo metadata |
| Meals | `log_meal(date, name, meal_time?, ingredients?, photo_base64?)` | write | No background vision |
| Meals | `edit_meal(photo_id, name?, meal_time?)` | write | |
| Meals | `set_ingredients(photo_id, ingredients)` | write | Replaces the confirmed ingredient list |
| Meals | `tag_meal(photo_id, handles)` | write | Tag accepted connections |
| Meals | `delete_meal(photo_id)` | write | |
| People | `list_people()` | read | Accepted connections who can be tagged |
| Labs | `get_lab(lab_id)` | read | All markers of one lab upload |
| Labs | `get_lab_history(marker_canonical_name)` | read | Values over time for one marker |
| Treatments | `treatments(on_date?, recent_days?)` | read | Active protocol plus recent dose logs |
| Treatments | `log_dose(treatment_id, date, doses_taken)` | write | |
| Trackers | `log_tracker(tracker_id, date, value)` | write | Upsert one tracker value for a day |
| Hypotheses | `hypotheses(status?)` | read | Hypothesis scoreboard |
| Hypotheses | `update_hypothesis(hypothesis_id? / slug?, …)` | write | Unspecified fields unchanged; no create/delete |
| Search | `search(query, k?)` | read | Semantic (vector) search over notes, meals, symptoms |

Resources: `marrow://catalog/lab-markers` (canonical lab marker names/units) and
`marrow://reference/check-in-day-map` (what a daily check-in contains and which tools write it).

## Tenancy and RLS

Every user-owned table has a `user_id` column (UUID FK to `users`). **Row Level Security (RLS)** is enabled with `FORCE ROW LEVEL SECURITY`. The `tenant_isolation` policy restricts rows to `user_id = current_setting('app.user_id')::uuid`.

Every tool opens a scoped session (`app/mcp/database.py`) that sets `app.user_id` from the Bearer token before any query. Cross-tenant reads and writes are impossible under normal roles.

## Database roles

- Read tools use `scoped_ro_session` → the `healthtracker_ro` role (`MCP_READONLY_DATABASE_URL`, `SELECT` only; falls back to `DATABASE_URL` when unset) with a 10 s statement timeout.
- Write tools use `scoped_main_session` → the app role (`DATABASE_URL`). Some read tools (e.g. `hypotheses`) also use the app role deliberately.
- Tool payloads are built from ORM rows *after* the session context exits; cleanup expunges rows before rollback (`_rollback_keep_rows`) so they stay readable. Build or copy data inside the session, and cover new tools with the real-session tests in `tests/test_mcp_database.py`.
- The MCP service currently has no `REDIS_URL`, so MCP writes cannot invalidate API-side Redis caches (entry 300 s, feature matrix 600 s, signals 1800 s TTLs apply) — see `railway_env.md`.

## Core table groups

| Group | Tables | Notes |
| --- | --- | --- |
| Daily check-in | `entries` | One row per user per calendar date; symptoms in `symptoms_json`; supplements as a CSV of catalog keys |
| Meals & photos | `meals`, `photos`, `photo_analyses`, `photo_ingredients` | Photos link to entries via `entry_id`; analysis is per `meal_id` |
| Labs | `labs`, `lab_markers`, `lab_marker_catalog`, `lab_marker_aliases` | Marker values reference per-user catalog rows |
| Treatments | `treatments`, `treatment_log` | Protocol items and their dose logs (distinct from daily supplement toggles) |
| Hypotheses | `hypotheses`, `n_of_1_slots` | Ranked questions, kill-tests |
| Catalogs | `supplement_catalog`, `symptom_catalog`, `medication_catalog`, `dietary_ingredients`, `ingredient_aliases`, … | Per-user; seeded from reference user on signup |
| Embeddings | `embedding_queue`, `embedding` | Async worker; powers `search` |

## Date and time conventions

- `entries.date` — `DATE`, one row per day; tool `date` arguments are calendar dates (`YYYY-MM-DD`), no timezone conversion. `set_supplements` defaults to today in `app_timezone` (Europe/Luxembourg).
- `entries.entry_time`, `photos.meal_time` — `TIMESTAMP WITHOUT TIME ZONE` (naive UTC)
- Symptom severities in `symptoms_json` are integers keyed by catalog `key` (e.g. `"vss": 6`)

## Supplements

`entries.supplements` is a comma-separated list of `supplement_catalog.key` values (`""` = none) with no FK, so historical keys survive archiving. The catalog is per user; `list_supplements` returns `id, key, label, archived, sort_order, first_used_at, last_used_at`. `set_supplements` validates keys against the caller's catalog and writes through `EntryOrchestrator.update_entry` so `first_used_at` / `last_used_at` and tracker sync stay correct. A web check-in tab open on the same date autosaves the whole entry and can overwrite an MCP change.

## Diet flags (entries)

`entries.diet_risk` is a legacy CSV of user-added flags. **Effective diet flags** for an entry combine photo-derived flags (`compute_photo_signal`) with user-added flags (`parse_diet_risk_csv`). Vocabulary: `high-histamine`, `high-fodmap`, `gluten`, `dairy`. `get_day` returns them as `effective_flags`.
