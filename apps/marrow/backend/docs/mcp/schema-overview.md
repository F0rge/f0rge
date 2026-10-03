# Marrow MCP — Overview and Data Model

Reference for agents using Leo's health tracker through the Marrow MCP server
(`app/mcp/`, FastMCP name `marrow`, endpoint `https://mcp.marrow-health.com/mcp`, Bearer token auth).

The MCP server exposes **typed tools, reference resources and one prompt**. There is no raw SQL
tool and no schema-dump resources. The registered surface is pinned by
`tests/test_mcp_surface.py::test_registered_tool_names`; update that test, this file, and the
day-map resource (`app/mcp/resources/day_map.py`) together when a tool is added or removed.

## Tools (22)

| Area | Tool | Kind | Notes |
| --- | --- | --- | --- |
| Days | `get_day(date)` | read | One check-in: scores, symptoms, supplements (list of keys), notes, meal summaries |
| Days | `list_days(start_date, end_date)` | read | Inclusive range, max 200; short summaries incl. `supplements` |
| Days | `save_day(date, overall?, bloating?, joint_pain?, neuro?, sleep_quality?, stress?, stool_status?, bristol_type?, stool_completeness?, notes?, symptoms_json?)` | write | Create or partially update a check-in |
| Days | `log_flare(date, key, severity, time?)` | write | Timed symptom event (+ `symptoms_json`) |
| Supplements | `list_supplements(include_archived=False)` | read | Per-user supplement catalog (keys for `set_supplements`) |
| Supplements | `set_supplements(keys, date?, mode='replace')` | write | `replace` / `add` / `remove` the day's supplement keys |
| Meals | `get_meal(photo_id)` | read | Ingredients, tags, photo metadata |
| Meals | `log_meal(date, name, meal_time?, ingredients?, photo_base64?)` | write | No background vision; `ingredients` = decomposed, catalogue-named list; returns per-ingredient match status (see below) |
| Meals | `edit_meal(photo_id, name?, meal_time?)` | write | Name/time only; ingredients via `set_ingredients` |
| Meals | `search_ingredients(query, limit=10)` | read | Ranked lookup in the caller's active catalogue: canonical name, match type, score, flags |
| Meals | `set_ingredients(photo_id, ingredients)` | write | Atomically replaces the ingredient list (all or nothing); returns per-ingredient match status |
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

## Resources

| URI | Scope | When to load |
| --- | --- | --- |
| `marrow://catalog/lab-markers` | Global reference | Canonical lab marker names and units |
| `marrow://catalog/dietary-ingredients` | **Per user** (RLS) | Before `log_meal` / `set_ingredients`: the caller's active ingredient catalogue (canonical name, aliases, FODMAP / histamine / gluten / dairy flags). Archived entries are omitted; capped at 500 entries (`truncated: true` when cut) |
| `marrow://reference/check-in-day-map` | Static | What a daily check-in contains and which tools write it |
| `marrow://reference/meal-logging-guide` | Static | How to log meals and ingredients (decompose composite foods, naming, catalogue matching) |

## Prompts and server instructions

- Server `instructions` (sent on `initialize`) carry the meal-logging rules. Some clients inject
  them into the system prompt, others ignore them — tool descriptions carry the same core
  guidance.
- Prompt `log_meal_guide(meal_description="")` renders the meal-logging guide as a user message.
- The shared rule text lives in `app/prompts/ingredient_rules.py` (import-free; intended to be
  shared later with the photo classifier prompt / Airflow DAG, not wired up yet).

## Logging meals and ingredients

`search_ingredients`, `log_meal` and `set_ingredients` match ingredient **names** against the
caller's own *active* catalogue (`dietary_ingredients` + `ingredient_aliases`, RLS-scoped; archived
entries count as unmatched). Matching is done in Python by one shared resolver
(`app/services/ingredient_resolver.py`, `ingredient_matching.py`); the UI/Airflow
`IngredientLookupService` is unchanged. **Catalogue entries are never created automatically**, and
there is no server-side LLM splitting - the client decomposes products.

Per-ingredient `match.status`:

| status | meaning | flags stored? |
| --- | --- | --- |
| `exact` | name equals a canonical name | yes |
| `alias` | name equals an alias | yes |
| `normalised` | equal after plural/singular, case, accent, quantity (`(40 g)`) normalisation | yes |
| `approximate` | close but not the same ingredient (token subset such as "gluten-free rolled oats", or a typo) | **no** - suggestions returned |
| `unmatched` | nothing close, archived, or a quantified/branded product string | **no** - suggestions + composite hint |

`search_ingredients` additionally reports `token_subset`, `fuzzy`, `partial` and `prefix`
candidates. Both writers return `ingredient_count`, `matched_count`, `unmatched`, `approximate`,
`composite_suspected`, `duplicates_dropped`, `ingredients[]` (each with `match`, `flags`) and a
`next_step` hint. `set_ingredients` runs in a single transaction. Limits: 40 ingredients per call,
case-insensitive de-duplication.

Clients should:

1. Put brand, pack size and quantity in the meal `name`, not in ingredient names.
2. Decompose packaged or composite foods (muesli, bread, ready meals) into constituent
   ingredients, from the pack's ingredient list or photo.
3. Call `search_ingredients` per ingredient and use the catalogue's exact `canonical_name`.
4. Not invent ingredients; say which were inferred.

Catalogue rows are per user and copied from the reference user at signup
(`copy_user_catalog_from_reference`); gap-fill rows added later reach existing users through an
Alembic data migration (e.g. `056`: muesli, flour, bread, pasta, cocoa).

## Date and time conventions

- `entries.date` — `DATE`, one row per day; tool `date` arguments are calendar dates (`YYYY-MM-DD`), no timezone conversion. `set_supplements` defaults to today in `app_timezone` (Europe/Luxembourg).
- `entries.entry_time`, `photos.meal_time` — `TIMESTAMP WITHOUT TIME ZONE` (naive UTC)
- Symptom severities in `symptoms_json` are integers keyed by catalog `key` (e.g. `"vss": 6`)

## Supplements

`entries.supplements` is a comma-separated list of `supplement_catalog.key` values (`""` = none) with no FK, so historical keys survive archiving. The catalog is per user; `list_supplements` returns `id, key, label, archived, sort_order, first_used_at, last_used_at`. `set_supplements` validates keys against the caller's catalog and writes through `EntryOrchestrator.update_entry` so `first_used_at` / `last_used_at` and tracker sync stay correct. A web check-in tab open on the same date autosaves the whole entry and can overwrite an MCP change.

## Diet flags (entries)

`entries.diet_risk` is a legacy CSV of user-added flags. **Effective diet flags** for an entry combine photo-derived flags (`compute_photo_signal`) with user-added flags (`parse_diet_risk_csv`). Vocabulary: `high-histamine`, `high-fodmap`, `gluten`, `dairy`. `get_day` returns them as `effective_flags`.
