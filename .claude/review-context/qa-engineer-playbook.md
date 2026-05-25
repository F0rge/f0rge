# QA Review Playbook (committed copy)

## What this is

Review checklist distilled from the qa-engineer's accumulated memory at `~/.claude/projects/-Users-leo-development-health-tracker/memory/` as of 2026-05-25. Loaded by the GitHub Actions PR-review bot (`anthropics/claude-code-action@v1`) on every PR. A fresh Claude reads this and the diff — that's the review.

The bot **cannot** run servers, click UIs, ssh to the Pi, or talk to OpenRouter. Anything that requires those goes into the "Verification ticket for the human" section as a checklist for the qa-engineer locally.

---

## Hard rules — instant block findings

Cite the originating memory file in every block-level comment so future-Leo can trace the rule.

- **Thin routers** — any new or modified route in `backend/app/routers/` must be ≤ 3 lines (signature + delegation + return). Block on presence of `if`, `try:`, `raise HTTPException`, `db.query(`, `db.add(`, `db.commit(`, `setattr(`, or any inline helper. Pre-existing fat routers (`entries.py`, `food_analysis.py`, `photos.upload_photo`) are *not* this PR's problem — only flag NEW violations. See `feedback_thin_routers.md`.
- **No mocks at the seam under test** — block when a test under `backend/tests/test_<svc>*.py` calls `monkeypatch.setattr` on a target inside `app.services.<svc>.*` or on a sibling collaborator the service imports (`render_and_write_daily_file`, `write_daily_file`, `save_photo`, `delete_photo`). Mocks belong at outbound HTTP / SDK / clock / randomness boundaries only. See `feedback_no_mocks_at_seam_under_test.md` (root-cause: 2026-05-16 prod `FileExistsError` regression that the suite missed).
- **Datetime tz-strip at the schema boundary** — any new `Mapped[datetime]` or `Mapped[Optional[datetime]]` column without `timezone=True` must have a `@field_validator(..., mode="after")` that subtracts the UTC offset then drops tzinfo on every input path that can carry tz-aware values. Block on `.replace(tzinfo=None)` without prior subtraction (silent 2-hour corruption). Block on a new schema accepting a frontend datetime without a stripper. See `project_datetime_tz_convention.md`.
- **Class-of-bug audit missing** — when a fix names a pattern (tz-aware bind, `scalar_one_or_none` on non-unique WHERE, `field || undefined` + `exclude_unset`, etc.), the PR must either fix every sibling occurrence in the same diff or open a tracked follow-up issue. Block if neither. See `feedback_audit_class_of_bug.md` (root-cause: 2026-05-17 two prod outages from missing sibling audit on `photos.meal_time`).
- **`.env.example` not updated for new required env vars** — block on any new entry in `backend/app/config.py` (e.g. `HEALTHTRACKER_RO_PASSWORD`, `SETTINGS_ENCRYPTION_KEY`, `MCP_READONLY_DATABASE_URL`) that isn't mirrored in `backend/.env.example`. Redeploys silently break without it. See `mcp_server_issue_49_findings.md`.
- **`ruff format` regression** — if a touched file used to pass `ruff format --check` and no longer does, block. Note: `ruff format --check` is currently OFF in CI (see "What NOT to flag" below), but format regressions are still review-blocking because they leak into the formatting backlog.
- **Migration without RUN_MIGRATIONS verification path** — PRs adding files under `backend/migrations/versions/` must not regress the entrypoint. If `backend/docker-entrypoint.sh` or `RUN_MIGRATIONS=1` on the `backend` service in `docker-compose.{dev,prod}.yml` is touched, block until verified — mcp-server and embedding-worker must still have it unset. See `devops/deploy_migration_entrypoint.md` + `qa-engineer/migrations_not_auto_run.md`.
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
| tz-aware → tz-naive column | `grep -rn 'Mapped\[datetime\|Mapped\[Optional\[datetime' backend/app/models/` then cross-ref every input path (schema + Form + query) | `entries.entry_time` fix shipped; `photos.meal_time` missed → second outage same day (2026-05-17) |
| `.scalar_one_or_none()` on non-unique WHERE | `grep -rn 'scalar_one_or_none' backend/app/services/` then check uniqueness of each WHERE | `IngredientLookupService.lookup()` ilike fallback (single occurrence at the time) |
| `field \|\| undefined` + Pydantic `exclude_unset=True` | `grep -rn '\|\| undefined' frontend/components/` cross-ref with backend UPDATE routes | `notes` clear-not-saving — nearly shipped without audit |
| Unstable `useEffect` dep including a `useCallback` over `useMutation`s | `grep -rn 'useEffect.*\[.*,\s*\(fire\|mutate\|callback\)' frontend/lib/hooks/` | `useAutosaveEntry` duplicate-fire (every save fired twice — see `autosave_gate_findings.md`) |
| `'use client'` page reading localStorage in `useState(initializer)` | `grep -rn '"use client"' frontend/app/customize/` then check for `useState(load*)` or `useState(() => load*())` | `/customize/reorder` SSR hydration mismatch (Phase 1 Customize Hub, see `issue_phase1_customize_hub_findings.md`) |

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
- Migration files → `ssh leo@rpi "docker exec <postgres> psql -U health -d health -c 'SELECT version_num FROM alembic_version;'"` after Coolify redeploys; must match new revision id. Recipe in `devops/deploy_migration_entrypoint.md` § "Coolify post-deploy verification".
- Any `Mapped[datetime]` schema change → after local PASS, verify against the dev Postgres on the Pi (not local SQLite, which silently accepts tz-aware datetimes). `project_datetime_tz_convention.md` final paragraph.
- MCP / embedding / OpenRouter changes → run the dev-env gate recipe Phase 1–5 against `health-dev*.leo-figueiredo.com`. Full recipe in `qa-engineer/dev_env_qa_recipe.md`.
- dnd-kit changes → use real `page.mouse` not synthetic events; mobile path requires real-device verify (CDP `Input.dispatchTouchEvent` does NOT activate dnd-kit `TouchSensor`). See `qa-engineer/issue_78_findings.md`.
- New `Dialog` / overlay / fixed-position UI → `elementsFromPoint(cx, cy)` z-index audit. The capsule lives at z:40, Dialog at z:50, bottom nav at z:50. Pattern in `qa-engineer/issue_pr100_findings.md`.
- New env var → confirm Coolify env has it set on both dev (`lunthdq8rqd0ad3hi6gcoac0`) and prod (`mk404cskowkgcow48g8s8okw`) backend services. UUIDs in `devops/deploy_migration_entrypoint.md`.

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
- **MCP `read_sql` points at prod, NOT dev** — for dev-DB queries during QA, use `curl` against `https://health-dev-api.leo-figueiredo.com/api/v1/...` with a logged-in cookie, OR ask devops to point MCP at dev. See `qa-engineer/issue_79_findings.md`.
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

- **`docker-entrypoint.sh` + `RUN_MIGRATIONS=1`** — `backend/Dockerfile` ENTRYPOINT runs `uv run alembic upgrade head` then `exec "$@"` when the flag is set. ONLY the `backend` service in `docker-compose.{dev,prod}.yml` sets it. `mcp-server` and `embedding-worker` share the image but leave it unset (avoids DDL race). Single-replica backend in both envs — if scaled >1, need an init-container or job. See `devops/deploy_migration_entrypoint.md`.
- **Coolify bind-mount materialization quirk** — Coolify's dockercompose build-pack does NOT do a full repo checkout on the Pi; only paths referenced as compose bind-mount sources are materialized. The entrypoint script is fine because it's `COPY`'d into the image, not bind-mounted. New scripts that need to be on the Pi must either be COPY'd in or referenced from a bind-mount source. See `devops/deploy_migration_entrypoint.md` "Caveats" + `MEMORY.md` link to `health-tracker-backup-strategy`.
- **`mem_limit:` not `deploy.resources.limits.memory:`** — `docker-compose.prod.yml` uses the legacy v2 style consistently. Match it for new services (mcp-server 256m, embedding-worker 512m). Same for `env_file: [.env]` + inline `environment:` block. See `project_mcp_phase_2_2c_infra.md`.
- **Port allocation on the Pi** — 8000–8006 are all occupied (8005 by entre-nos). `health-tracker` MCP uses host:8007 → container:8005. Before adding any new exposed port, `ssh leo@rpi "sudo ss -tlnp | grep ':80[0-9][0-9]\s'"`. See `project_mcp_phase_2_2c_infra.md`.
- **Cloudflare config** — `*.leo-figueiredo.com` routes go in file-mode `/etc/cloudflared/config.yml` on the Pi (mirror at `/home/leo/.cloudflared/config.yml`). Tunnel ID `6c58d6b1-ad4d-4df9-8249-0e2bb88a9c01`. The `*.taxpilot.lu` routes increasingly live in Zero Trust dashboard — don't mix patterns. See `project_mcp_phase_2_2c_infra.md`.
- **Catalog seeds re-run on every backend boot** — `app.main.lifespan` is idempotent (early-returns when rows exist). If the postgres volume is wiped, seeds re-run automatically. Don't add new seeds outside `lifespan` without preserving idempotency. See `devops/deploy_migration_entrypoint.md`.
- **`HEALTHTRACKER_RO_PASSWORD` required by migration 004** — already set on both Coolify envs. Missing it crashes the entrypoint on a fresh DB. If a future migration requires a new env var, set it on the `backend` service (entrypoint sees it before alembic runs).

---

## What NOT to flag (false-positive suppression)

Real things in the repo that are *intentionally* in their current state — do not flag.

- **`ruff format --check` is intentionally OFF in `.github/workflows/ci-develop.yml` and `ci-main.yml`.** ~89 files would reformat. A one-shot formatting PR will land first, then it gets re-enabled. Do not flag unformatted code as a CI gap. Only flag a new file that introduces *new* format issues a touched file already passed.
- **`ruff check` rule set is narrow (E/F/W minus E501/F821) by design.** The comment in `ci-develop.yml` says "Follow-up: enable I + UP + B + SIM + RUF." Do not flag unused-imports / sort-order issues as block-level — they're a pending widen pass.
- **Vault-write `logger.warning(...)` in dev backend logs.** `VAULT_PATH` is unmounted in dev by design; the `obsidian.write_daily_file()` early-returns and the makedirs OSError is logged-then-swallowed. Do not flag in dev gate logs. See `qa-engineer/dev_env_findings.md`.
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
