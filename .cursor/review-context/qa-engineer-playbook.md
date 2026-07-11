# QA Review Playbook (committed copy)

## What this is

Review checklist distilled from the qa-engineer's accumulated memory at `~/.claude/projects/-Users-leo-development-health-tracker/memory/` as of 2026-05-25. Loaded by the GitHub Actions PR-review bot (`anthropics/claude-code-action@v1`) on every PR. A fresh Claude reads this and the diff — that's the review.

The bot **cannot** run servers, click UIs, ssh to the Pi, or talk to OpenRouter. Anything that requires those goes into the "Verification ticket for the human" section as a checklist for the qa-engineer locally.

---

## Hard rules — instant block findings

Cite the originating memory file in every block-level comment so future-Leo can trace the rule.

- **`platform:` tag on new projects** — any new `project.json` must carry `platform:py` or `platform:ts` tag or CI silently ignores it. Block on new projects missing tags.
- **Lib test coverage** — changes to `libs/**` must include or update tests in the lib's `tests/` directory. Block on lib changes with no test updates when behavior changes.
- **Re-implementation grep** — when reviewing app code, grep diff for local copies of lib-owned helpers (`DomainError`, `BaseCRUD`, `unit_of_work`, `ApiError`, shadcn primitives). Block on re-implementations.
- **Thin routers** — any new or modified route in `apps/marrow/backend/app/routers/` must be ≤ 3 lines (signature + delegation + return). Block on presence of `if`, `try:`, `raise HTTPException`, `db.query(`, `db.add(`, `db.commit(`, `setattr(`, or any inline helper. Pre-existing fat routers (`entries.py`, `food_analysis.py`, `photos.upload_photo`) are *not* this PR's problem — only flag NEW violations. See `feedback_thin_routers.md`.
- **No mocks at the seam under test** — block when a test under `apps/marrow/backend/tests/test_<svc>*.py` calls `monkeypatch.setattr` on a target inside `app.services.<svc>.*` or on a sibling collaborator the service imports (`render_and_write_daily_file`, `write_daily_file`, `save_photo`, `delete_photo`). Mocks belong at outbound HTTP / SDK / clock / randomness boundaries only. See `feedback_no_mocks_at_seam_under_test.md` (root-cause: 2026-05-16 prod `FileExistsError` regression that the suite missed).
- **Datetime tz-strip at the schema boundary** — any new `Mapped[datetime]` or `Mapped[Optional[datetime]]` column without `timezone=True` must have a `@field_validator(..., mode="after")` that subtracts the UTC offset then drops tzinfo on every input path that can carry tz-aware values. Block on `.replace(tzinfo=None)` without prior subtraction (silent 2-hour corruption). Block on a new schema accepting a frontend datetime without a stripper. See `project_datetime_tz_convention.md`.
- **Class-of-bug audit missing** — when a fix names a pattern (tz-aware bind, `scalar_one_or_none` on non-unique WHERE, `field || undefined` + `exclude_unset`, etc.), the PR must either fix every sibling occurrence in the same diff or open a tracked follow-up issue. Block if neither. See `feedback_audit_class_of_bug.md` (root-cause: 2026-05-17 two prod outages from missing sibling audit on `photos.meal_time`).
- **`.env.example` not updated for new required env vars** — block on any new entry in `apps/marrow/backend/app/config.py` (e.g. `HEALTHTRACKER_RO_PASSWORD`, `SETTINGS_ENCRYPTION_KEY`, `MCP_READONLY_DATABASE_URL`) that isn't mirrored in `apps/marrow/backend/.env.example`. Redeploys silently break without it. See `mcp_server_issue_49_findings.md`.
- **`ruff format` regression** — if a touched file used to pass `ruff format --check` and no longer does, block. Note: `ruff format --check` is currently OFF in CI (see "What NOT to flag" below), but format regressions are still review-blocking because they leak into the formatting backlog.
- **Migration without Fly release_command path** — PRs adding files under `apps/marrow/backend/migrations/versions/` must leave `[deploy] release_command` in `fly.toml` / `fly.prod.toml` running alembic via `MIGRATION_DATABASE_URL`. See `.cursor/rules/infra.mdc`.
- **pgvector extension order** — block any new test fixture or context that calls `Base.metadata.create_all` on a fresh Postgres without first executing `CREATE EXTENSION IF NOT EXISTS vector`. The `embedding.embedding VECTOR(1024)` column will crash `create_all`. See `project_byok_pgvector.md`.
- **BYOK key resolution missed** — block any new AI/LLM call site that imports `settings.openrouter_api_key` directly instead of calling `resolve_llm_credentials(db)`. Lab extraction has this as an open follow-up; new code must not repeat it. See `project_byok_pgvector_gate.md`.
- **Embedding vector dim != 1024** — block any new embedding column, request, or response that uses a dim other than 1024. The column is locked. See `project_ai_seams.md`.
- **`asyncpg.Connection.add_listener` not awaited** — block on any new use of `raw_conn.add_listener(...)` without `await`. It's a coroutine; a sync call is a silent `RuntimeWarning` that kills LISTEN/NOTIFY. See `mcp_server_issue_49_findings.md` blocker 3.
- **DDL with parameter markers** — block on `ALTER ROLE ... PASSWORD $1` or `DO $$ ... $$` blocks using bound parameters. Use SQL-escape + f-string (own-controlled values only) or `format()` + `%I` inside the DO block. `GRANT CONNECT ON DATABASE current_database()` is invalid SQL — wrap in DO + `EXECUTE format('... %I ...', current_database())`. See `project_mcp_migrations.md`.

---

## Class-of-bug audit checklist

When a PR fixes one of these patterns, the reviewer should mentally run the grep and request the sibling audit in the PR description. If sibling occurrences exist and aren't either fixed or follow-up-ticketed, the audit is incomplete.

| Pattern fixed | Grep to run | Sibling miss that hit prod |
|---|---|---|
| tz-aware → tz-naive column | `grep -rn 'Mapped\[datetime\|Mapped\[Optional\[datetime' apps/marrow/backend/app/models/` then cross-ref every input path (schema + Form + query) | `entries.entry_time` fix shipped; `photos.meal_time` missed → second outage same day (2026-05-17) |
| `.scalar_one_or_none()` on non-unique WHERE | `grep -rn 'scalar_one_or_none' apps/marrow/backend/app/services/` then check uniqueness of each WHERE | `IngredientLookupService.lookup()` ilike fallback (single occurrence at the time) |
| `field \|\| undefined` + Pydantic `exclude_unset=True` | `grep -rn '\|\| undefined' apps/marrow/frontend/components/` cross-ref with backend UPDATE routes | `notes` clear-not-saving — nearly shipped without audit |
| Unstable `useEffect` dep including a `useCallback` over `useMutation`s | `grep -rn 'useEffect.*\[.*,\s*\(fire\|mutate\|callback\)' apps/marrow/frontend/lib/hooks/` | `useAutosaveEntry` duplicate-fire (every save fired twice — see `autosave_gate_findings.md`) |
| `'use client'` page reading localStorage in `useState(initializer)` | `grep -rn '"use client"' apps/marrow/frontend/app/customize/` then check for `useState(load*)` or `useState(() => load*())` | `/customize/reorder` SSR hydration mismatch (Phase 1 Customize Hub, see `issue_phase1_customize_hub_findings.md`) |

Cite `feedback_audit_class_of_bug.md` when asking the PR author to extend the fix.

---

## Live-server gate — verification ticket for the human

The bot can't run `./start.sh`, drive Playwright, or ssh to the Pi. Instead, when the review concludes, append a **Verification ticket** to the top-level summary listing the manual checks the human qa-engineer must perform locally before merge. Base the ticket on the diff:

**Always include (every PR):**
- [ ] Spin up local dev (`./start.sh` or `uv run uvicorn` + `npm run dev`); poll `/api/v1/health` to ready.
- [ ] Drive every NEW user-facing path on the branch — every route, every form, every workflow that wasn't there on `develop`. Identify them from the diff.
- [ ] After running, tail backend container logs for the test window — a 500 hidden behind a frontend toast is the most common slipped bug (see `MEMORY.md` → "Tail backend logs FIRST when UI reports an error").
- [ ] Confirm `git status` is clean and any temp servers/worktrees are torn down (per global post-merge hygiene rule).

**Add when diff includes:**
- Migration files → after Fly deploy on develop, verify `alembic_version` via API health + exercise changed paths on `app-dev.marrow-health.com`.
- Any `Mapped[datetime]` schema change → verify against Postgres dev (`app-dev.marrow-health.com`), not local SQLite.
- MCP / embedding / OpenRouter changes → run dev-env gate against `api-dev.marrow-health.com` / `app-dev.marrow-health.com`.
- dnd-kit changes → use real `page.mouse` not synthetic events; mobile path requires real-device verify (CDP `Input.dispatchTouchEvent` does NOT activate dnd-kit `TouchSensor`). See `qa-engineer/issue_78_findings.md`.
- New `Dialog` / overlay / fixed-position UI → `elementsFromPoint(cx, cy)` z-index audit. The capsule lives at z:40, Dialog at z:50, bottom nav at z:50. Pattern in `qa-engineer/issue_pr100_findings.md`.
- New env var → confirm Fly secrets on `marrow-dev` and `marrow` API apps.

For Playwright auth bypass: insert directly into `auth_sessions` then `addCookies({httpOnly:true})` — `document.cookie = ...` from `browser_evaluate` does not stick. Recipe in `MEMORY.md` § "Auth bypass for Playwright/UI smoke tests".

---

## Datetime / timezone conventions

Per `project_datetime_tz_convention.md`:
- All `DateTime` columns are `TIMESTAMP WITHOUT TIME ZONE` (no `timezone=True`). Stored values are tz-naive UTC.
- Frontend sends `new Date().toISOString()` → Pydantic parses to `datetime(..., tzinfo=UTC)`. asyncpg **refuses** to bind tz-aware to tz-naive, returning a 500 with `DataError: invalid input for query argument`.
- The required stripper (subtract THEN drop, never just drop):
  ```python
  @field_validator("entry_time", mode="after")
  @classmethod
  def strip_tz(cls, v: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
      if v is None or v.tzinfo is None:
          return v
      return (v - v.utcoffset()).replace(tzinfo=None)
  ```
- For `Form(...)` params that bypass Pydantic, strip in the service before constructing the model (see `app/services/photos.py:103-112` for the worked example).
- Confirmed sites: `app/schemas/entry.py` (EntryCreate/Update), `app/schemas/photo.py` (PhotoMealTimeUpdate), `app/services/photos.py` (PhotoService.upload).
- Local SQLite + aiosqlite silently accepts tz-aware — bugs in this category pass local and fail prod. Always verify against Postgres.

---

## Backend-specific patterns to flag

- **Composite PK upsert** — use the read-then-write pattern (`select() → scalar_one_or_none() → update or add`), NOT dialect-specific `insert().on_conflict_do_update()`. The model needs `__table_args__ = (PrimaryKeyConstraint("a", "b", name="..."),)` — single-column `primary_key=True` won't work. See `fastapi-backend/sqlalchemy_composite_pk_upsert.md`.
- **Pydantic v2 immutable-field guard tests** — to test a service guard for a field that `XxxUpdate` excludes, subclass with the field as an explicit constructor arg. `object.__setattr__` and `__pydantic_fields_set__` hacks do not work with v2's storage. See `fastapi-backend/immutable_field_guard_test_pattern.md`.
- **AI seam contracts** — OpenRouter `openai/text-embedding-3-small` with `dimensions=1024` returns 1024-float vectors. Response has extra `provider` + `id` top-level keys vs OpenAI. Access via `response["data"][i]["embedding"]`. Default model in `ai_seams.md` is `google/gemini-2.5-flash` (the `2.0-flash` one is rejected by OpenRouter). See `project_ai_seams.md` and `project_byok_pgvector_gate.md` follow-up 3.
- **BYOK + pgvector ordering** — every code path that calls `Base.metadata.create_all` (production startup, every test fixture, every migration smoke harness) must execute `CREATE EXTENSION IF NOT EXISTS vector` first. The migration itself does this, but `create_all` bypasses migrations. `main.py` aliases the settings router (`from app.routers import settings as settings_router`) because the module name collides with `app.config.settings`. See `project_byok_pgvector.md`.
- **MCP `read_sql` points at prod, NOT dev** — for dev-DB queries during QA, use `curl` against `https://api-dev.marrow-health.com/api/v1/...` with a logged-in cookie. See `qa-engineer/issue_79_findings.md`.
- **Trackers dual-write path** — seeded trackers (`Alcohol units`, `Caffeine servings`, `Sick`, `Hot shower`) must keep both `entries.<col>` and `tracker_log` in sync. Path A: entry autosave → `sync_seed_tracker_log_from_entry` after `db.refresh`. Path B: `PUT tracker_values/{id}` → `_mirror_value_to_entry` (silently skips if no entry exists; Path A will catch up on entry creation). New seeded trackers must be added to `_SEED_NAME_TO_ENTRY_COL`. Zero-suppression: skip None/0 for counters, None/False for binaries. See `fastapi-backend/trackers_dual_write_pattern.md`.

---

## Frontend-specific patterns to flag

- **dnd-kit on 2D grids** — use `rectSortingStrategy`, NOT `verticalListSortingStrategy` (the latter only works for single-column lists). Single columns CAN use `verticalListSortingStrategy` (e.g. reorder mode). See `frontend-dev/dnd_kit_grid_drag_reorder.md`.
- **dnd-kit handle wiring** — `{...listeners} {...attributes}` go on a dedicated `<button>` with `GripVertical` icon ONLY. Never on the card wrapper — every tap inside the card would start a drag. `ref={setNodeRef}` + transform/transition on the outer div. `PointerSensor` with `activationConstraint: { distance: 4 }`, `TouchSensor` with `delay: 350, tolerance: 5` (or `delay:150 tolerance:8` in dedicated reorder mode where tiles have no inner content).
- **col-span on the sortable wrapper** — col-span / grid-placement classes must move to the same node that carries `ref={setNodeRef}`. If they live on an inner `<Card>`, the outer ref div is 0-height and the transform displaces wrong. Add `h-full` to the inner card so it stretches.
- **DragOverlay sizing** — capture `event.active.rect.current.initial.width` in `onDragStart`, pass to `<DragOverlay><div style={{ width }}>`. Without this, overlays render outside the CSS grid and morph. Mobile placeholder uses `opacity-30` (not 50). See `frontend-dev/dnd_kit_grid_drag_reorder.md`.
- **`react-hooks/set-state-in-effect`** — never silence with `eslint-disable`. The fix is the key-bump pattern: parent tracks `errorKey: number`, passes `key={errorKey}` (forces remount) + `shakeOnMount={errorKey > 0}` (initial state via `useState(shakeOnMount)`). `setState` inside a `setTimeout` callback is OK (synchronizing with external timer). See `frontend-dev/react-hooks-set-state-in-effect.md`.
- **SSR hydration mismatch traps** — `'use client'` does NOT disable SSR. App Router still prerenders `'use client'` pages (look for `○` in `npm run build` output). Any `useState(loadFromLocalStorage)` lazy initializer on a prerendered route will mismatch on hydration. Three fix paths in order of preference:
  1. `useSyncExternalStore` with a referentially-stable `getServerSnapshot` (module-level cached array — DON'T return a fresh spread, that's an infinite-loop footgun);
  2. `useState(DEFAULT) + useEffect(() => setX(saved), [])` — but watch for `react-hooks/set-state-in-effect` on small components;
  3. `next/dynamic({ ssr: false })` wrapper. Sacrifices static prerender but sidesteps both bugs.
  See `frontend-dev/customize_hub_foundation.md` (note: that file's earlier wrong claim about `'use client'` is corrected at the top).
- **IconPicker shared map** — `KNOWN_ICONS` (lowercase string[]) and `ICON_COMPONENT_MAP` (name → LucideIcon) are both exported from `components/checkin/cards/components/IconPicker.tsx`. `TrackerRow` imports `ICON_COMPONENT_MAP` — no local `ICON_MAP` clones. Note: `bookopen` (no space) is the DB-stored key for `BookOpen`. New icons go into both lists. See `frontend-dev/icon_picker_pattern.md`.
- **Dual-source card** — seeded tracker values flow via parent props (CheckinBoard → existing autosave), custom tracker values via `useEntryTrackerValues` hook + optimistic `useUpsertTrackerValue` PUT. Disambiguation by `is_seed` flag (preferred) or module-scope `SEEDED_NAMES` Set. Don't double-write. See `frontend-dev/trackers_dual_source_card.md`.
- **Manage/Restore archived pattern** — single `useTrackers(true)` fetch, client-side split into active/archived. Invalidate with `queryKey: ['trackers']` prefix (matches both `['trackers', false]` AND `['trackers', true]`). Manage footer hidden when `archivedTrackers.length === 0` — no empty-state UI. See `frontend-dev/trackers_manage_restore.md`.
- **Dedicated reorder mode** — DndContext only mounted when `isReorderMode=true`. Reorder tiles use `verticalListSortingStrategy` (single column). Always-on drag on content-rich cards causes morph. Exit via `setLayoutVersion(v => v + 1)` to remount. Up/down arrow buttons are the accessibility fallback for keyboard/screen-reader users. See `frontend-dev/reorder_mode_pattern.md`.
- **Hidden cards storage** — separate `ht.cards-v2.hidden` key from `ht.cards-v2.order`. Reorder mode renders ALL cards (so user can un-hide); normal mode filters by `!hiddenCards.includes(id)`. ReorderTile gets `isHidden` + `onToggleHidden` props; Eye button only renders when `onToggleHidden !== undefined`. Hiding all cards is allowed — Hero stats remain.
- **Autosave deps stability** — never include a `useMutation`-derived callback in a self-feeding `useEffect`'s deps. Mutations return fresh references each render → effect re-fires → duplicate PUTs. Use refs (`fireRef.current`) inside the effect, or `useEffectEvent`. `forceFlush` must build a payload from current scalars when `pendingPayloadRef.current === null` (otherwise photo-upload on a fresh date 404s). See `qa-engineer/autosave_gate_findings.md`.

---

## DevOps / infra patterns

- **Fly migrations** — `[deploy] release_command` in `fly.toml` / `fly.prod.toml` runs `alembic upgrade head` as `MIGRATION_DATABASE_URL` (htmigrate). Runtime uses `DATABASE_URL` (healthtracker-app). See `.cursor/rules/infra.mdc`.
- **MPG on Fly** — cluster `nlkxjo5m3240y93v` (`f0rge-db`, org `f0rge`); `FLY_MPG_SKIP_ROLE_DDL=1`; roles via `fly mpg users create`.
- **Custom domains** — `marrow-health.com` DNS on Cloudflare (grey cloud); certs via `fly certs add`.

---

## What NOT to flag (false-positive suppression)

Real things in the repo that are *intentionally* in their current state — do not flag.

- **`ruff format --check` is intentionally OFF in `.github/workflows/ci-develop.yml` and `ci-main.yml`.** ~89 files would reformat. A one-shot formatting PR will land first, then it gets re-enabled. Do not flag unformatted code as a CI gap. Only flag a new file that introduces *new* format issues a touched file already passed.
- **`ruff check` rule set is narrow (E/F/W minus E501/F821) by design.** The comment in `ci-develop.yml` says "Follow-up: enable I + UP + B + SIM + RUF." Do not flag unused-imports / sort-order issues as block-level — they're a pending widen pass.
- **`/icons/icon-192.png` 404 on every page.** PWA icon not deployed yet. Known harmless. Do not flag.
- **`/api/v1/auth/me` 401 on first page load.** Happens before login completes. Disappears after PIN entry.
- **`/api/v1/entries/{date}` 404 before today's entry exists.** Expected; editor falls back to defaults.
- **`(° marker / `ƒ` marker in `npm run build`)** — load-bearing signal of static-vs-dynamic prerender. Do not flag a route changing from `○` to `ƒ` if the diff intentionally added `next/dynamic({ ssr: false })` to solve hydration (see `issue_phase1_customize_hub_findings.md` round-3).
- **Reorder hub row has no tier pill.** `HubRow` `tier` prop is intentionally optional; meta rows (cross-section operations) omit it. Other 4 hub rows still render pills.
- **Hero strip 4 vs 5 tiles depending on treatment.** `grid-cols-3 lg:grid-cols-4` (no treatment) or `lg:grid-cols-5` (with). Not a missing tile.
- **Bristol gate uses pill, not amber ring on the Gut card.** Caption + amber pill in header is the only cue; was intentional UX choice. See `qa-engineer/issue_77_cards_layout_findings.md`.
- **`/checkin/{date}` is editor; `/history/{date}` is read-only summary.** Navigation from `/history` calendar goes to the summary. Both routes exist.
- **`MCP read_sql` points at prod DB, not dev.** Don't flag in a dev-related PR. See `qa-engineer/issue_79_findings.md`.
- **Pre-existing fat routers (`entries.py`, `food_analysis.py`, `photos.upload_photo`).** They violate the thin-router rule. Do NOT block on them unless this PR added a *new* violation. See `feedback_thin_routers.md` "Nuances".

---

## Tone & output format expectations

The bot's review uses inline GitHub PR comments at the precise line where the issue lives, plus one top-level summary comment.

Each inline comment:
- Begins with severity prefix: `[block]`, `[warn]`, `[nit]`.
- `[block]` = violation of a hard rule above. PR cannot merge as-is.
- `[warn]` = real issue that should be addressed but isn't catastrophic (e.g. cosmetic, follow-up-ticket acceptable).
- `[nit]` = style / readability / minor; author can ignore.
- One-sentence description of what's wrong, one-sentence of the fix.
- Cite the originating memory file in backticks: `See feedback_thin_routers.md.`

Top-level summary:
1. **Verdict** line: `GO`, `NO-GO`, or `GO with follow-ups` (matching qa-engineer's prior gate vocabulary).
2. **Block-level findings** list — every `[block]` comment summarized with file:line links. If empty, say "No block-level findings."
3. **Warnings / nits** count only.
4. **Verification ticket** — bulleted checklist of manual checks the human qa-engineer must perform locally (see "Live-server gate" section above for content).
5. **Class-of-bug audit prompt** if the diff touches any of the patterns in the audit table.

Be terse. Each line earns its place. The qa-engineer reads this on a Pi-deployed PR view at 6am — no fluff.

---

*This document is cached. Updates require an explicit refresh PR.*
