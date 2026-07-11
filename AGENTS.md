# Health Tracker — Agent Instructions

**Extends `~/.cursor/rules/leo-system-wide.mdc`** — global preferences, stack defaults, git workflow, boundaries, and sub-agent delegation live there. This file is project-specific only.

## Project rules

Scoped rules in `.cursor/rules/` (auto-applied by glob):

| Rule | Scope |
|------|-------|
| `orchestration.mdc` | Always — planning must delegate to sub-agents |
| `backend.mdc` | `backend/**/*.py`, migrations |
| `frontend.mdc` | `frontend/**/*.tsx`, `frontend/**/*.ts` |
| `infra.mdc` | Docker, compose, CI, deploy |
| `qa-gate.mdc` | tests, workflows |
| `data-pipelines.mdc` | `backend/scripts/**`, `backend/data/**` |

See also `CLAUDE.md` for env URLs, key paths, and issue-writing template.

## Sub-agents

Delegate per `~/.cursor/rules/leo-system-wide.mdc` and `.cursor/rules/orchestration.mdc`. Every plan names a sub-agent per work chunk before implementation. Brief each sub-agent to read `~/.cursor/agent-memory/<agent-name>/MEMORY.md` before starting and write back gotchas when done.

## Shipping features

End-to-end workflow (prompt or GitHub issue → develop → dev smoke → main PR): `.cursor/skills/ship-feature/SKILL.md`.

## PR review context

Bugbot/PR review playbooks live in `.cursor/review-context/`.

## Agent memory

**Canonical:** `~/.cursor/agent-memory/<agent>/` (global, cross-project).

## Cursor Cloud specific instructions

The VM snapshot already has `uv`, Node 22, Docker, backend `.venv`, `ruff`, and frontend `node_modules`. The startup update script only refreshes deps (`uv sync --frozen --project backend`, `uv tool install ruff@latest`, `npm --prefix frontend ci`). Services and the database are NOT auto-started — bring them up as below. Standard run/lint/test commands live in `CLAUDE.md`, `.cursor/rules/backend.mdc`, and `.cursor/rules/qa-gate.mdc`.

### Database + Docker (must start manually each session)
- There is **no local dev docker-compose**; the `docker-compose*.yml` files are Coolify/Fly deploy stacks, not local dev.
- The Docker daemon is not auto-started. Start it once per session: `sudo dockerd > /tmp/dockerd.log 2>&1 &` then `sudo chmod 666 /var/run/docker.sock` (lets `uv run pytest`'s testcontainers reach the socket as the `ubuntu` user). `/etc/docker/daemon.json` is pre-set to `fuse-overlayfs` + `containerd-snapshotter: false` (required for Docker 29 in this VM) — do not change it.
- Backend + tests need a **pgvector** Postgres on `localhost:5432` with user/pass/db all `health`. Start/reuse it:
  `docker start ht-postgres 2>/dev/null || docker run -d --name ht-postgres -e POSTGRES_USER=health -e POSTGRES_PASSWORD=health -e POSTGRES_DB=health -p 5432:5432 pgvector/pgvector:pg16`
- `backend/.env` (gitignored) holds local secrets. If missing, recreate with: `JWT_SECRET` (any string), `SETTINGS_ENCRYPTION_KEY` (a valid Fernet key: `uv run --project backend python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`), `DATABASE_URL=postgresql+asyncpg://health:health@localhost:5432/health`, `PHOTO_DIR=photos`, and `HEALTHTRACKER_RO_PASSWORD` / `HEALTHTRACKER_APP_PASSWORD` (any random strings, consumed by migrations 004/019). Do **not** put `CORS_ORIGINS` as a bare string in `.env` — it is a `list[str]` parsed as JSON and a plain value crashes startup; omit it (default already allows `http://localhost:3000`).

### Migrations gotcha
- Alembic migrations 004/019 read `HEALTHTRACKER_RO_PASSWORD` / `HEALTHTRACKER_APP_PASSWORD` from **`os.environ`, not** from `.env` via pydantic. Export the `.env` before migrating: `cd backend && set -a && . ./.env && set +a && uv run alembic upgrade head`. Running the backend itself does not need this (pydantic loads `.env`), only the migration step does.

### Running
- `./start.sh` runs both (backend `:8000`, frontend `:3000`); frontend proxies `/api/*` → `:8000`. The backend auto-seeds dietary reference tables on first boot against a fresh DB.
- Signup rejects non-routable email TLDs (e.g. `.local`); use a normal domain like `demo@example.com` when testing auth.
- Optional services (not needed for the core check-in app): embedding worker (`uv run python -m app.embedding_pipeline`, needs `OPENROUTER_API_KEY`) and MCP server (`uv run python -m app.mcp ...`).
