# Marrow local setup

Read this when preparing a clean local Marrow checkout or applying local migrations. Start Docker using the host’s normal mechanism; use the [root local commands](../../AGENTS.md#running-locally) for pgvector, backend and frontend. Install repository JavaScript dependencies with `npm ci` and backend dependencies with `uv sync --frozen --project apps/marrow/backend`.

## Local configuration

- `apps/marrow/backend/.env` (gitignored) holds local secrets. If missing, recreate with: `JWT_SECRET` (any string), `SETTINGS_ENCRYPTION_KEY` (a valid Fernet key: `uv run --project apps/marrow/backend python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`), `DATABASE_URL=postgresql+asyncpg://health:health@localhost:5432/health`, `PHOTO_DIR=photos`, and `HEALTHTRACKER_RO_PASSWORD` / `HEALTHTRACKER_APP_PASSWORD` (any random strings, consumed by migrations 004/019). Do **not** put `CORS_ORIGINS` as a bare string in `.env` — it is a `list[str]` parsed as JSON and a plain value crashes startup; omit it (default already allows `http://localhost:3000`).

## Local migrations

- Alembic migrations 004/019 read `HEALTHTRACKER_RO_PASSWORD` / `HEALTHTRACKER_APP_PASSWORD` from **`os.environ`, not** from `.env` via pydantic. Export the `.env` before migrating: `cd apps/marrow/backend && set -a && . ./.env && set +a && uv run alembic upgrade head`. Running the backend itself does not need this (pydantic loads `.env`), only the migration step does.
- **Cross-tenant data migrations under FORCE RLS:** use `f0rge_db.rls.migration_bypass` (transient `app.service_role = 'migrator'` policy). Do not loop per user with `set_config('app.user_id', ...)`. Single-tenant reference-user seeds may still use `app.user_id`. Full convention: `docs/agents/rules/backend.md` § Alembic migrations under FORCE RLS.

## Running and safe fixtures

- Backend `:8000` + frontend `:3000` (frontend proxies `/api/*` → `:8000`): run `uv run uvicorn app.main:app --port 8000 --reload` in `apps/marrow/backend` and `npm run dev` in `apps/marrow/frontend` (from repo root: `npx nx run marrow-frontend:dev`). Install deps with `npm ci` at repo root (workspaces).
- Signup rejects non-routable email TLDs (e.g. `.local`); use a normal domain like `demo@example.com` when testing auth.
- Optional services (not needed for the core check-in app): embedding worker (`uv run python -m app.embedding_pipeline`, needs `OPENROUTER_API_KEY`) and MCP server (`uv run python -m app.mcp ...`).
