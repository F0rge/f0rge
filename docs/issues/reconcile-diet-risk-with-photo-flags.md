# Reconcile manual diet_risk with photo-derived flags (photos as floor, manual is additive)

## Problem (Why)

The app currently has two parallel, isolated paths for capturing dietary risk:

- **Manual entry** — `Entry.diet_risk` is a comma-separated string from `{normal, high-histamine, high-fodmap, gluten, not-sure}` entered at check-in, one value per day ([entry.py:35](backend/app/models/entry.py:35), [checkin-form.tsx:28-34](frontend/components/checkin/checkin-form.tsx:28))
- **Photo analysis** — AI vision extracts per-meal ingredients tagged with `histamine_score` (0–3), `fodmap_oligos/fructose/polyols/lactose` (null/moderate/high), `contains_gluten`, `contains_dairy` ([photo_ingredient.py:11-36](backend/app/models/photo_ingredient.py:11))

The two streams never talk to each other:

- No reconciliation logic compares them
- The stats feature matrix treats them as **independent** predictors ([feature_matrix.py:90](backend/app/services/feature_matrix.py:90)) — inflates feature importance because both measure the same underlying thing
- Obsidian export writes both in separate sections ([obsidian.py:302, 367-395](backend/app/services/obsidian.py:302)) — the reader must cross-reference manually
- A user can pick `"normal"` while the photo of dinner contains aged cheese; both happily coexist with no warning

Concrete harms: (1) double-entry friction; (2) noisy diagnostics that double-count signal; (3) ambiguity about which value is canonical when re-reading historical logs months later.

## Goal

Daily diet-risk becomes the **union of photo-derived flags and user-added flags**. Photos are the floor — anything the AI confidently sees is automatically included and cannot be unticked from the diet form. The user can only **add** flags (for unphotographed meals, drinks, supplements). Photos additionally contribute **numeric scores** (cumulative histamine load and per-flag counts) that travel through to the vault and stats — manual additions only contribute to the flag union, not the score. The resulting effective signal is what gets stored, displayed, written to the vault, and consumed by the stats model.

## UI & scoring spec (chosen layout)

The UI follows **Mockup B with photo scores**. Rendered reference: [docs/issues/mockups/diet-risk-final.html](docs/issues/mockups/diet-risk-final.html).

**Layout** (inside the existing "Diet risk" card on the check-in page):

1. **From photos (locked)** row — non-clickable chips, each prefixed with a small camera icon and suffixed with a numeric score badge (e.g. `High-histamine [7]`). Below the chips: a one-line source attribution naming the triggering ingredients. Below that: a 4-tile stats strip (`Hist. load · FODMAP · Gluten · Dairy`) showing the per-flag numeric values, always rendered even when zero.
2. **Horizontal divider.**
3. **Manual additions** row — the existing toggleable chips, score-free. Toggled-on chips use the existing black "user-added" state.

Drop `"not-sure"` and `"normal"` from the manual options — `normal` is now a derived state (empty `effective_flags`). Add `"dairy"` to manual options so the manual vocabulary matches the photo-derived vocabulary.

If photos exist but no analysis has been confirmed yet, show "Photos still analyzing — flags will update" in place of the locked row; the manual row stays interactive.

**Scoring rules** (constants in `app/services/diet_flags.py`):

| Flag | Score formula | Flag-trigger threshold |
|---|---|---|
| `high-histamine` | `Σ histamine_score` across all confirmed ingredients (cumulative load, not a count) | any ingredient with `histamine_score >= 2` |
| `high-fodmap` | count of ingredients where any FODMAP subcategory (`oligos / fructose / polyols / lactose`) is `"high"` | same — count > 0 |
| `gluten` | count of ingredients with `contains_gluten = true` | same — count > 0 |
| `dairy` | count of ingredients with `contains_dairy = true` | same — count > 0 |

Unconfirmed ingredients are excluded from both flag derivation and scoring. Manual additions contribute to the flag union but never to the photo score (scores are *evidence from photos*; manual is *user assertion*). Vault `*-count` fields sum photo count + 1 per manual flag; `histamine-load` stays photo-only (a binary user assertion has no numeric dose).

**Vault frontmatter contract** (new keys, in addition to existing `diet-risk` which now carries `effective_flags`):

```yaml
diet-risk: high-histamine, dairy, gluten          # effective_flags (union, comma-separated)
diet-histamine-load: 7                            # photo-only cumulative score
diet-fodmap-count: 0                              # photo count + manual additions
diet-gluten-count: 1                              # e.g. 0 from photos + 1 manual = 1
diet-dairy-count: 2
diet-risk-provenance:
  - high-histamine: photos
  - dairy: photos
  - gluten: manual
```

## Sub-agent assignments

| Chunk | Agent | Memory dir |
|---|---|---|
| Mapping rules (photo ingredients → flag set), thresholds, `compute_photo_derived_flags` service | `data-engineer` | `.claude/projects/-Users-leo-development-health-tracker/memory/` |
| Schema split, API shape for `effective_flags`, photo-confirm recompute trigger, backfill script | `fastapi-backend` | same |
| Checkin form UI — render photo-derived flags as locked badges, additive checkboxes, drop "not-sure", add "dairy" | `frontend-dev` | same |
| QA gate — live-server walkthrough across 5 scenarios | `qa-engineer` | same |

Each agent reads its memory before starting and writes back what's worth keeping when done.

## Proposed approach

**1. Mapping + scoring** (`data-engineer`)

New service `app/services/diet_flags.py` exposes one function: `compute_photo_signal(entry_id) -> PhotoSignal`, where `PhotoSignal` is a Pydantic model:

```python
class PhotoScores(BaseModel):
    histamine_load: int    # Σ histamine_score across confirmed ingredients
    fodmap_count: int      # count of ingredients with any subcategory == "high"
    gluten_count: int      # count of ingredients with contains_gluten
    dairy_count: int       # count of ingredients with contains_dairy

class PhotoSignal(BaseModel):
    flags: set[str]        # subset of {"high-histamine","high-fodmap","gluten","dairy"}
    scores: PhotoScores
    sources: dict[str, list[str]]   # flag -> [ingredient_name, ...] for the source line in UI
```

Flag-derivation rules (thresholds as module constants, one-line WHY comment each):

- Any *confirmed* `PhotoIngredient` with `histamine_score >= 2` → `"high-histamine"`
- Any confirmed ingredient with any of `fodmap_oligos/fructose/polyols/lactose == "high"` → `"high-fodmap"`
- Any confirmed ingredient with `contains_gluten` → `"gluten"`
- Any confirmed ingredient with `contains_dairy` → `"dairy"` (NEW flag — vision already detects it, manual UI doesn't expose it today)

Unconfirmed ingredients are ignored from both flags and scores — confirmation is the user's contract with the AI.

A second function `compute_effective_counts(entry) -> dict[str, int]` returns per-flag counts that include manual additions (photo_count + 1 per manual flag), used by the vault writer.

**2. Storage model** (`fastapi-backend`)

Two viable shapes; agent picks the simpler one after reading the codebase:

- **(a) Compute on read** — rename `Entry.diet_risk` semantically to "user-added flags only" (column name stays for now). Expose `entry.effective_flags` as a computed property that joins photo ingredients at query time.
- **(b) Cache + recompute** — add `Entry.photo_derived_flags` column. Recompute when `PhotoAnalysis.status` → `"confirmed"` or `PhotoIngredient.user_edited` is set.

Default to **(a)** unless query performance is a problem (joins are tiny — it won't be).

**3. UI** (`frontend-dev`)

In [checkin-form.tsx](frontend/components/checkin/checkin-form.tsx), `DIET_OPTIONS` becomes additive checkboxes layered over photo-derived state:

- Add `"dairy"` to options
- Remove `"not-sure"` — replaced by "no manual flags added" (effective flags fall back to whatever photos saw, or nothing)
- `"normal"` disappears as a manual selection — `"normal"` is now a *derived* state meaning `effective_flags is empty`
- Each chip has three states:
  - **Locked-on** (photo-derived) — non-clickable badge with a small camera icon + tooltip naming the triggering ingredient ("from aged cheese in Pad Thai")
  - **User-added** — normal selected checkbox the user toggled
  - **Available** — unchecked, click to add

If photos are still `pending|analyzing`, show "Photos still analyzing — flags will update" and don't lock anything yet.

**4. Recompute trigger** (`fastapi-backend`)

With approach (a) reads always recompute — automatic. With (b) wire into `confirm_analysis` in `food_analysis.py`.

**5. Vault export** ([obsidian.py:302, 343](backend/app/services/obsidian.py:302))

Write `effective_flags` (not raw `diet_risk`) into both the frontmatter and the daily table. When both sources contributed, add a one-line provenance split: `Diet risk: high-histamine, gluten (high-histamine from photos; gluten added manually)`.

**6. Stats / feature matrix** ([feature_matrix.py:90](backend/app/services/feature_matrix.py:90))

Drop the separate ordinal encoding of `diet_risk`. The `histamine_load_sum` / `fodmap_*_sum` / `gluten_exposure` / `dairy_exposure` columns already capture the photo-derived signal. Add columns derived from `user_added_flags` only (e.g., `manual_extra_histamine: bool`) so we can later analyse whether manual additions are diagnostically informative.

**7. Backfill** (`data-engineer`)

`backend/scripts/backfill_effective_flags.py`. For every existing entry:

- Compute `photo_derived_flags` from confirmed photo ingredients
- Diff against the legacy `diet_risk` string — detect (a) flags photos found that the user didn't pick (now auto-locked), (b) flags the user picked that photos didn't detect (kept as manual addition)
- Emit `backfill_report.csv` for review before committing
- Idempotent — safe to re-run

## Files

**Existing modified:**

- [backend/app/models/entry.py:35](backend/app/models/entry.py:35) — add `effective_flags` property; rename concept (column name unchanged this round)
- [backend/app/schemas/entry.py:33-34](backend/app/schemas/entry.py:33) — expose `effective_flags`, `photo_derived_flags`, `user_added_flags`, and `photo_signal: PhotoSignal` in `EntryRead`
- [backend/app/services/food_analysis.py:302-319](backend/app/services/food_analysis.py:302) — call `diet_flags.compute_photo_derived_flags` on confirm (only if approach b)
- [backend/app/services/feature_matrix.py:90](backend/app/services/feature_matrix.py:90) — drop ordinal `diet_risk` feature, add `manual_extra_*` columns
- [backend/app/services/obsidian.py:302,343,367-395](backend/app/services/obsidian.py:302) — emit `effective_flags`, new `diet-histamine-load`/`diet-fodmap-count`/`diet-gluten-count`/`diet-dairy-count` keys, and `diet-risk-provenance` map per the frontmatter contract above
- [frontend/components/checkin/checkin-form.tsx:28-34, 123-139](frontend/components/checkin/checkin-form.tsx:28) — replace the current 3-column `DIET_OPTIONS` grid with the two-row split from the mockup: locked photo chips with score badges + source attribution line + 4-tile stats strip, divider, manual chips below. Drop `"not-sure"` and `"normal"` from manual options; add `"dairy"`.
- [frontend/lib/api/types.ts](frontend/lib/api/types.ts) — extend `Entry` with `effective_flags`, `photo_derived_flags`, `user_added_flags` arrays and a `photo_signal: { flags, scores: {histamine_load, fodmap_count, gluten_count, dairy_count}, sources }` object

**New:**

- `backend/app/services/diet_flags.py` — mapping logic, thresholds, union computation
- `backend/scripts/backfill_effective_flags.py` — one-off backfill with CSV report
- `backend/tests/test_diet_flags.py` — mapping rules, threshold edge cases, empty/null handling

## Out of scope (non-goals)

- Do not move to per-meal granularity — stays per-day; per-meal photos roll up via max severity
- Do not change the photo analysis prompt or vision model — derivation reads existing `PhotoIngredient` columns as-is
- Do not introduce new dietary categories beyond `{high-histamine, high-fodmap, gluten, dairy}` — oxalate/salicylate/etc. are a separate effort
- Do not redesign other feature-matrix inputs (sleep, stress, treatments) — only diet_risk encoding changes
- Do not change how photo ingredients are confirmed or edited — that flow stays; it is the user's escape hatch when the AI hallucinates
- Do not delete the legacy `diet_risk` column in this issue — keep it for one release as audit/safety net

## Boundaries

**Always (no approval needed):**
- Add `app/services/diet_flags.py` with mapping + tests
- Modify `Entry`, `EntryCreate`, `EntryRead` schemas
- Update checkin form UI
- Update Obsidian export
- Write the backfill script (do not run it on prod data without approval)

**Ask first:**
- Running the backfill script against the live Postgres DB
- Schema migration that drops or renames `diet_risk`
- Changing histamine threshold from `>=2`
- Adding categories beyond the four named

**Never:**
- Force-push, `--no-verify`, skipping hooks
- Mocking the database in tests for this feature (per `feedback_no_mocks_at_seam_under_test.md`)
- Putting business logic in routers (per `feedback_thin_routers.md`)
- Auto-deleting old `diet_risk` values without backfill CSV review

## Acceptance criteria / Definition of done

**Code-level:**

- `pytest backend/tests/test_diet_flags.py` passes; covers histamine threshold boundaries (0,1,2,3), each FODMAP subcategory at high/moderate/null, gluten/dairy true/false, empty ingredient list, mix of confirmed + unconfirmed ingredients (unconfirmed are ignored)
- **Scoring tests:** `histamine_load` is the sum (e.g. three ingredients with scores 3,2,2 → 7); `fodmap_count` counts each ingredient once even when multiple subcategories are `high`; `gluten_count` and `dairy_count` are simple ingredient counts; unconfirmed ingredients contribute zero to all scores
- **Effective-count tests:** `compute_effective_counts` returns photo_count + 1 per manual flag (e.g. photo gluten_count=0 + manual gluten → effective `diet-gluten-count: 1`); `histamine-load` is unchanged by manual additions (manual has no numeric dose)
- `ruff check backend/` clean
- `npm run typecheck && npm run lint && npm run build` clean
- `GET /api/v1/entries/{id}` returns `effective_flags`, `photo_derived_flags`, `user_added_flags` as three distinct arrays plus a `photo_signal` object with `flags`, `scores: {histamine_load, fodmap_count, gluten_count, dairy_count}`, and `sources` (flag → list of ingredient names for the UI source line)

**Live-server walkthrough** (per `feedback_qa_e2e_live_server.md` — pytest passing is not the gate):

Spin up `./start.sh`. Drive each scenario in a browser, screenshot end state:

1. **No photo, manual selection** — create entry, pick `high-fodmap` manually, save. `effective_flags = ["high-fodmap"]`. No "From photos" row rendered (empty-state hint shown instead). Stats strip not rendered. Vault: `diet-risk: high-fodmap`, `diet-fodmap-count: 1`, `diet-histamine-load: 0`, `diet-risk-provenance: [high-fodmap: manual]`.
2. **Photo dominates** — upload photo with aged cheese (histamine_score=3), prosciutto (histamine_score=3), tomato (histamine_score=1), plus parmesan + butter (both `contains_dairy=true`); confirm analysis. The locked row shows `High-histamine [7]` and `Dairy [2]` chips with the camera icon. Source attribution line names the ingredients. Stats strip reads `Hist. load: 7 · FODMAP: 0 · Gluten: 0 · Dairy: 2`. Vault: `diet-risk: high-histamine, dairy`, `diet-histamine-load: 7`, `diet-dairy-count: 2`.
3. **Photo + manual addition** — as in (2), then user clicks `gluten` in the manual row. `effective_flags = ["high-histamine", "dairy", "gluten"]`. Manual chip renders in black "user-added" state. Vault: `diet-risk: high-histamine, dairy, gluten`, `diet-gluten-count: 1`, `diet-histamine-load: 7` (unchanged by manual addition), `diet-risk-provenance: [high-histamine: photos, dairy: photos, gluten: manual]`.
4. **Analyzing state** — upload photo; before analysis completes try to save. "Photos still analyzing" placeholder in the locked row; manual row stays interactive. After analysis completes and is confirmed, the locked chips + scores + stats strip appear on next entry read.
5. **AI miss correction** — user disagrees with a photo-derived flag (LLM hallucinated `contains_gluten` on the parmesan). User edits the photo ingredient to remove `contains_gluten`. On re-read, `effective_flags` excludes `gluten`, `gluten_count` returns to 0, vault `diet-risk-provenance` no longer lists `gluten`. Escape hatch confirmed.

**Diagnostic / vault:**

- Backfill against a copy of the Postgres DB; inspect CSV report; no entries lose information vs. their original `diet_risk` string (manual additions preserved as `user_added_flags`)
- Stats endpoint after change: ordinal `diet_risk` column no longer appears in the feature matrix

## Dependencies

- **Blocked by:** none
- **Blocks:** future per-meal logging redesign; oxalate/salicylate category expansion (would extend the mapping rules)
- **Required env / secrets:** none new

## Rollback

This change writes new fields and reshapes how `effective_flags` is computed but **does not drop** the legacy `diet_risk` column. If a regression surfaces:

1. Revert `feature_matrix.py` so the legacy ordinal feature is restored
2. Revert Obsidian export to read `entry.diet_risk` directly
3. Frontend revert to standalone `DIET_OPTIONS` checkboxes
4. Leave new `diet_flags.py` and any cached column in place — inert until read paths consult them again

No data loss because the legacy column is preserved through this issue.
