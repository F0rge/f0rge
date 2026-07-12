# FastAPI Backend Review Playbook

## What this is

Authoritative review checklist for the Claude PR review bot operating on health-tracker backend diffs. Every rule is grounded in a memory file written from a real production incident or architectural decision — not generic FastAPI best practice.

---

## Scope — what files YOU review

- `apps/marrow/backend/app/routers/**` — thin HTTP layer
- `apps/marrow/backend/app/services/**` — all business logic
- `apps/marrow/backend/app/dependencies/**` — `Depends()` factories
- `apps/marrow/backend/app/schemas/**` — Pydantic v2 input/output shapes
- `apps/marrow/backend/app/models/**` — SQLAlchemy ORM models
- `apps/marrow/backend/app/exceptions.py` — domain exception definitions
- `apps/marrow/backend/app/main.py` — global exception handler registration, router inclusion
- `apps/marrow/backend/app/config.py` — settings + `resolve_llm_credentials`
- `apps/marrow/backend/migrations/versions/*.py` — Alembic revisions
- `apps/marrow/backend/tests/**` — pytest suite
- `apps/marrow/backend/pyproject.toml` — deps + ruff config
- `libs/backend/**` — shared Python libs (`f0rge_core`, `f0rge_db`, `f0rge_storage`, `f0rge_testing`)

**NOT your scope:** `.github/`, `apps/marrow/backend/docker-entrypoint.sh`, `apps/marrow/frontend/`, `libs/ui/` — those go to `devops` or `frontend-dev`.

**Non-duplication:** block re-implementations of lib-owned helpers. Apps must import from `f0rge_core`, `f0rge_db`, `f0rge_storage`, `f0rge_testing` — never duplicate exceptions, CRUD base, session factories, RLS hooks, or object storage clients.

---

## Hard rules — instant BLOCK findings

### Architecture

- **Thin routers** — any router endpoint longer than ~3 lines, or containing `if`, `else`, ternary, `try`, `except`, `raise`, `raise HTTPException`, `db.query`, `db.add`, `db.commit`, `db.flush`, or a helper function defined in the same router module is a BLOCK. Pre-existing redirect branches in `photos.serve_photo` and `account.serve_avatar` are grandfathered — flag NEW violations only. See `feedback_thin_routers.md`.

  Canonical 3-line endpoint shape:
  ```python
  @router.post("/", response_model=ThingOut, status_code=status.HTTP_201_CREATED)
  def create_thing(data: ThingCreate, svc: ThingService = Depends(get_thing_service)):
      return svc.create(data)
  ```

- **Domain exceptions, not HTTPException** — services raise `NotFoundError`, `ValidationError`, or `ConflictError` from `app/exceptions.py`; global handlers in `app/main.py` map them to HTTP responses. Any new code constructing `HTTPException` anywhere in `app/routers/**` or `app/services/**` is a BLOCK. See `feedback_thin_routers.md`.

- **Services injected via `Depends()`** — routers must never instantiate a service directly (`MyService(db=...)` in a router body is a BLOCK). See agent definition.

- **`from __future__ import annotations` missing** — every new `.py` file in `apps/marrow/backend/app/` or `apps/marrow/backend/tests/` must have this as the first non-comment line. BLOCK if absent. See agent definition.

### Testing

- **No mocks at the seam under test** — a test for `app.services.photos` must NOT `monkeypatch` `app.services.photos.*` or collaborators in the same module (e.g. `save_photo`, `delete_photo`, `render_and_write_daily_file`). Acceptable mock targets: outbound HTTP (`httpx`, OpenAI/OpenRouter SDK), third-party SDKs (`anthropic`, AWS), `datetime.now()` / `random` / `secrets.token_*`, and read-only env config. BLOCK when the seam under test is hollowed out. See `feedback_no_mocks_at_seam_under_test.md`.

  Prefer real `tmp_path` filesystem + `async_db` SAVEPOINT fixture + real collaborators. A 3-second integration test beats a 50ms test that misses prod bugs.

- **Monkeypatch path must match import location** — after any router→service refactor, grep tests for `monkeypatch.setattr("app.routers.<module>.*")` and verify the target moved. Python patches the *importing* module's name, not the definition site. BLOCK if the patch target no longer exists. See `feedback_no_mocks_at_seam_under_test.md`.

### Datetime / timezone

- **tz-strip at boundary** — all `DateTime` ORM columns are `TIMESTAMP WITHOUT TIME ZONE` (tz-naive UTC). asyncpg hard-rejects tz-aware datetimes bound to tz-naive columns (SQLite silently accepts them — the bug only surfaces on Postgres). Any new `Mapped[datetime]` or `Mapped[Optional[datetime]]` column that accepts frontend input without a tz-strip is a BLOCK. See `project_datetime_tz_convention.md`.

  Exact required stripper pattern — subtract the UTC offset FIRST, then drop tzinfo. Do NOT just `.replace(tzinfo=None)` (silently stores local wall-clock as UTC):
  ```python
  @field_validator("my_field", mode="after")
  @classmethod
  def strip_tz(cls, v: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
      if v is None or v.tzinfo is None:
          return v
      utc_offset = v.utcoffset()
      return (v - utc_offset).replace(tzinfo=None)
  ```
  For `Form(...)` parameters that bypass Pydantic, apply the same subtract-then-drop logic in the **service** before constructing the model.

- **Columns to audit on every PR touching models** — grep `Mapped\[datetime` and `Mapped\[Optional\[datetime` in `app/models/`. Candidates not yet confirmed as safe: `treatments.start_date`/`end_date`, `labs.collected_at`, any `onset_time`. See `project_datetime_tz_convention.md`.

### Pydantic / ORM

- **Pydantic v2 immutable field guard test** — use the subclass-with-explicit-constructor pattern. `object.__setattr__` hacks and direct `__pydantic_fields_set__` assignment do NOT produce valid `model_dump(exclude_unset=True)` output. BLOCK if the hack pattern is used. See `fastapi-backend/immutable_field_guard_test_pattern.md`.

  Correct pattern:
  ```python
  class _TrackerUpdateWithKind(TrackerUpdate):
      kind: str = "counter"

  body = _TrackerUpdateWithKind(kind="counter")  # explicit → in fields_set
  ```

- **Composite PK upsert** — use read-then-write, NOT `insert().on_conflict_do_update()`. Dialect-specific ON CONFLICT couples the service to Postgres. Composite PK model requires `__table_args__ = (PrimaryKeyConstraint("col_a", "col_b", name="pk_name"),)`. BLOCK if dialect-specific upsert appears. See `fastapi-backend/sqlalchemy_composite_pk_upsert.md`.

  Correct pattern:
  ```python
  existing = (await db.execute(
      select(TrackerLog).where(TrackerLog.tracker_id == tid, TrackerLog.date == date)
  )).scalar_one_or_none()
  if existing is not None:
      existing.value = value
      await db.commit()
      await db.refresh(existing)
  else:
      log = TrackerLog(tracker_id=tid, date=date, value=value)
      db.add(log)
      await db.commit()
      await db.refresh(log)
  ```

### AI / BYOK

- **BYOK key resolution** — every new code path that calls OpenRouter or any LLM API must use `resolve_llm_credentials(db)`, NOT `settings.openrouter_api_key` directly. The known miss: `lab_extraction.py` still uses the env var directly (tracked follow-up, not this PR's blocker). New code must not repeat this. BLOCK on new callsites bypassing BYOK. See `project_byok_pgvector_gate.md`.

- **Embedding dim=1024 locked** — `embedding.embedding VECTOR(1024)` column is fixed. BLOCK any new embedding column declaration, API request, or response parsing that uses a different dimension. See `project_ai_seams.md`.

- **OpenRouter response shape** — access `response["data"][i]["embedding"]`; do not assert on top-level key count (OpenRouter returns extra `provider` and `id` keys vs vanilla OpenAI). BLOCK assertions like `assert set(response.keys()) == {"object", "data", "model", "usage"}`. See `project_ai_seams.md`.

- **pgvector extension before `create_all`** — any test fixture or startup path that calls `Base.metadata.create_all` on a fresh Postgres must first execute `CREATE EXTENSION IF NOT EXISTS vector`. BLOCK if missing. See `project_byok_pgvector.md`.

### Migrations

- **asyncpg DDL parameter marker prohibition** — `ALTER ROLE ... PASSWORD $1` is invalid in Postgres DDL. New migrations that set passwords must embed the value via Python f-string (value comes from an owned env var, so interpolation is safe). BLOCK if bound parameters used in DDL. See `project_mcp_migrations.md`.

- **`DO $$ ... $$` blocks need `format()` + `%I`** — DO blocks do not accept bound parameters. Use `EXECUTE format('GRANT CONNECT ON DATABASE %I ...', current_database())` for identifier injection. BLOCK if `$1` / `.execute(text(...), {...})` appears inside a DO block. See `project_mcp_migrations.md`.

- **`GRANT CONNECT ON DATABASE current_database()` is invalid SQL** — `current_database()` is a function, not usable as an identifier in GRANT directly. Must resolve inside a DO block with `EXECUTE format(...)`. See `project_mcp_migrations.md`.

### Dual-write integrity

- **Seeded trackers must dual-write** — any change to `Alcohol units`, `Caffeine servings`, `Sick`, or `Hot shower` tracker values must sync both `entries.<col>` and `tracker_log` (Path A: entry save → `sync_seed_tracker_log_from_entry`; Path B: PUT tracker_values → `_mirror_value_to_entry`). BLOCK if new code removes either path or adds a new seeded tracker without updating `_SEED_NAME_TO_ENTRY_COL`. See `fastapi-backend/trackers_dual_write_pattern.md`.

- **`MutableDict.as_mutable` for in-place JSON mutation** — `Column(JSON)` without `MutableDict.as_mutable(JSON)` silently drops in-place dict mutations (`entry.symptoms_json["k"] = v` is invisible to SQLAlchemy). BLOCK if a new JSON column that is mutated in-place omits the wrapper.

### Config hygiene

- **`.env.example` mirror** — every new field added to `app/config.py` (i.e., a new `Settings` attribute with a default that must be overridden in deployment) requires a matching entry in `apps/marrow/backend/.env.example`. BLOCK if absent.

---

## Class-of-bug audit

When a fix touches a named pattern, grep for siblings before approving. Past incidents where missing the sibling caused a second prod outage the same day:

| Pattern | Grep command | Known incident |
|---|---|---|
| tz-aware datetime bound to tz-naive column | `grep -rn "Mapped\[datetime\|Mapped\[Optional\[datetime" apps/marrow/backend/app/models/` then trace input paths | 2026-05-17: entry_time fixed, photos.meal_time missed; two 500s |
| `save_photo`/`delete_photo` called in service without DB-first commit order | `grep -n "save_photo\|delete_photo" apps/marrow/backend/app/services/photos.py` — commit must precede filesystem | 2026-05-16: orphan file on commit failure |
| Filename collision — MAX vs COUNT | `grep -n "count()\|COUNT()" apps/marrow/backend/app/services/photos.py` — must use MAX+1, not COUNT+1 | 2026-05-16: deleted row caused collision |
| Monkeypatch path after router→service refactor | `grep -rn "monkeypatch.setattr.*app.routers" apps/marrow/backend/tests/` — stale paths silently pass | 2026-05-16: test suite green, prod 500 |
| BYOK bypass | `grep -rn "settings\.openrouter_api_key" apps/marrow/backend/app/` — must go through `resolve_llm_credentials` | lab_extraction.py miss flagged in gate #48 |

---

## Architecture compliance checklist

Work through this in order for any non-trivial backend diff.

1. **Router thinness** — run: `grep -En "if |raise |try:|HTTPException|db\.query|db\.add|db\.commit|db\.flush" apps/marrow/backend/app/routers/<file>.py` → must return nothing for new code.
2. **`from __future__ import annotations`** at top of every new `.py` file.
3. **Python 3.10 syntax** — no `match/case`, no `X | Y` union syntax in runtime code (use `Union[X, Y]` or `Optional[X]`). `X | Y` is allowed in type comments and `isinstance(..., X | Y)` only in 3.10+, which we target, but avoid for consistency.
4. **Pydantic v2 schema naming** — `ThingCreate` / `ThingUpdate` / `ThingResponse`. `model_config = ConfigDict(from_attributes=True)` on any schema that is returned from an ORM query.
5. **`db.flush()` then `db.refresh()`** before returning an ORM-mapped object from a service method. Never return a detached instance.
6. **Session scoping** — `AsyncSession` is injected per-request via `Depends(get_db)`. Services receive it in `__init__`. Never create a bare `async_session_maker()` in a service (that bypasses request scoping).
7. **No PostgreSQL-specific features** in services/schemas — pgvector (`VECTOR` column type) is the one sanctioned exception. All other ORM code must be dialect-neutral. See `project_byok_pgvector.md` (tests now run against a real Postgres via testcontainers, SQLite compat no longer required — but avoid Postgres-only constructs outside pgvector/migration files).
8. **`relationship()` needs `lazy="selectin"`** — async lazy-load after session close raises `MissingGreenlet`. Every new `relationship()` in a model must include `lazy="selectin"`.

---

## Async SQLAlchemy specifics

- `await db.execute(select(...))` + `.scalar_one_or_none()` / `.scalars().all()` — not the legacy `db.query(...)` API.
- `await db.flush()` before `await db.refresh(obj)` when you need the DB-generated `id` / `created_at`.
- `await db.commit()` closes the implicit transaction; subsequent access to attributes on an expired instance needs `await db.refresh(obj)`.
- The `async_db` test fixture uses a SAVEPOINT (nested transaction) that rolls back. Rows inserted with `async_db` are NOT visible to a second engine connection (e.g. a separate `async_session_maker()` call). For cross-connection tests, use a real session + explicit cleanup.
- asyncpg named parameters: if the same bind name (`:t`) appears in both the SELECT list and WHERE clause of a `text()` query, asyncpg raises `AmbiguousParameterError`. Use distinct names (`:t_ins`, `:t_chk`).

---

## AI seam contracts

Source of truth: `docs/architecture/ai_seams.md`.

| Contract | Value |
|---|---|
| Embedding model | `openai/text-embedding-3-small` via OpenRouter |
| Embedding dim | `1024` — locked to `VECTOR(1024)` column; `dimensions=1024` required in every request |
| Default LLM | `google/gemini-3-flash-preview` — NOT `gemini-2.0-flash` (OpenRouter rejects it) |
| Embedding response access | `response["data"][i]["embedding"]` — top-level has extra `provider` + `id` keys vs OpenAI, do not assert on key set |
| BYOK resolution order | `resolve_llm_credentials(db)` → user `user_settings.openrouter_api_key` if set, else `settings.openrouter_api_key` env var |
| Async embed method patch | `new=async_fn` not `side_effect=lambda` — `side_effect` adds `self` as extra arg on instance method patches |

---

## Migration safety

- Fly deploy runs migrations via `[deploy] release_command` in `fly.toml` / `fly.prod.toml` (`alembic upgrade head` as `MIGRATION_DATABASE_URL`). See `.cursor/rules/infra.mdc`.
- `RUN_MIGRATIONS=1` + `docker-entrypoint.sh` is optional for **local Docker image** builds only — do not set on MCP or embedding-worker containers.
- After `alembic revision --autogenerate -m "..."`, always audit the generated file. Autogenerate misses: index renames, `server_default` changes, `CHECK` constraint adds/drops, and extension-level DDL. Hand-write those `op.execute()` calls.
- Migration 004 introduced `HEALTHTRACKER_RO_PASSWORD` env var requirement. Any new migration that references Postgres roles must document the required env var in the migration file's docstring and in `apps/marrow/backend/.env.example`. See `project_mcp_migrations.md`.

---

## What NOT to flag (false-positive suppression)

- **Pre-existing redirect branches** — `photos.serve_photo` and `account.serve_avatar` contain `if` for presigned URL redirects. Do not block a PR for touching them without worsening the violation.
- **`ruff format --check`** is enforced in CI via `nx run-many -t format-check`. Flag format regressions on touched files.
- **Narrow ruff rule set** — CI runs `ruff check` with `E/F/W` rules, `E501`/`F821` excluded. Don't flag line-length violations or forward-reference resolution issues unless they indicate a real semantic problem.
- **`lazy="selectin"` on models added before the async migration** — pre-existing models may be missing this. Don't block; open a follow-up. BLOCK only on new `relationship()` calls.
- **`lab_extraction.py` BYOK bypass** — pre-existing tracked follow-up. Don't block PRs that don't touch `lab_extraction.py` for this.

---

## Tone & output

Return JSON matching this schema:

```json
{
  "findings": [
    {
      "severity": "block" | "warn" | "nit",
      "file": "apps/marrow/backend/app/routers/foo.py",
      "line": 42,
      "msg": "Router endpoint contains `if` statement — move condition to service. See feedback_thin_routers.md.",
      "cites": ["feedback_thin_routers.md"]
    }
  ],
  "summary": "2 blockers, 1 warning. Thin-router violation in foo.py:42; missing tz-strip on Bar.start_time in bar.py:17."
}
```

Severity rules:
- `block` — hard rule listed above is violated; PR cannot merge.
- `warn` — real issue that is safe to merge with a tracked follow-up (e.g. missing `.env.example` entry for an internal-only config key, pre-existing violation worsened slightly).
- `nit` — cosmetic (naming, ordering, minor style).

Every finding MUST have at least one entry in `cites`. Be terse — every word earns its place.
