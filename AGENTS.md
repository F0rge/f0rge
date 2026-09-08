# Health Tracker — Agent Instructions

**Extends `~/.cursor/rules/leo-system-wide.mdc`** — global preferences, stack defaults, git workflow, boundaries, and sub-agent delegation live there. This file holds project-specific rules only.

Personal daily symptom check-in app for Leo's health research vault.

## Stack

- Backend: FastAPI + async SQLAlchemy + Postgres (asyncpg) — Python 3.10
- Frontend: Next.js 16 + React 19 + Tailwind 4 + shadcn/ui
- Auth: JWT in `ht_session` httpOnly cookie (email + password)
- Deploy: Railway (API, worker, MCP, frontend) + Railway pgvector Postgres + Redis + Buckets for photos

## Environments

Marrow runs on Railway project **zoological-fulfillment** (`a633a271-…`). Environments: `production` ← branch `main`, `develop` ← branch `develop`. dk tag-printer stays on Coolify/Pi.

### Production (`main`)

| Component | Railway service | URL |
|---|---|---|
| API + worker | `marrow-api` / `marrow-worker` | https://api.marrow-health.com |
| MCP | `marrow-mcp` | https://mcp.marrow-health.com |
| Frontend | `marrow-frontend` | https://marrow-health.com |
| Postgres | `pgvector` | via `DATABASE_URL` |
| Redis | `Redis` | via `REDIS_URL` |
| Photos | bucket `photos` | via `AWS_*` / `BUCKET_NAME` |

### Develop (`develop`)

| Component | Railway service | URL |
|---|---|---|
| API + worker | `marrow-api` / `marrow-worker` | https://api-dev.marrow-health.com |
| MCP | `marrow-mcp` | https://mcp-dev.marrow-health.com |
| Frontend | `marrow-frontend` | https://app-dev.marrow-health.com |
| Postgres | `pgvector-hRmh` | via `DATABASE_URL` |
| Redis | `Redis-fVqY` | via `REDIS_URL` |
| Photos | bucket `photos-dev` | via `AWS_*` / `BUCKET_NAME` |

Deploy configs: `apps/marrow/backend/railway.toml`, `railway.worker.toml`, `railway.mcp.toml`, `apps/marrow/frontend/railway.toml`. CI smokes only (Railway autodeploys). See [README.md](README.md#cicd), [`.cursor/rules/infra.mdc`](.cursor/rules/infra.mdc), [`apps/marrow/backend/docs/railway_env.md`](apps/marrow/backend/docs/railway_env.md).
## apps/dk (tag printer)

DasKasas price tag tool — stateless FastAPI + Next.js, **no auth, no DB**.

| Env | Host | URLs |
|-----|------|------|
| Production (`main`) | Pi Coolify | https://tags.leo-figueiredo.com, https://tags-api.leo-figueiredo.com |

Local dev:

```bash
cd apps/dk/tag-printer && docker compose up --build   # :3002 / :8002
```

Infra: [`apps/dk/tag-printer/AGENTS.md`](apps/dk/tag-printer/AGENTS.md) (nested — auto-loaded when working in that subtree). Coolify repoint after first `main` merge: `apps/dk/tag-printer/scripts/repoint-coolify.sh`.

## apps/vellano

Furniture retailer back office. Nested [`apps/vellano/AGENTS.md`](apps/vellano/AGENTS.md). **Own Railway project** — do **not** add Vellano services, Postgres, or buckets to Marrow `zoological-fulfillment` or the Marrow develop environment. Develop hosts: https://vellano-dev.leo-figueiredo.com and https://vellano-dev-api.leo-figueiredo.com (`/docs` for Swagger). Local ports `:8003` / `:3003` / Postgres `:5433`. UI is IBM Carbon, not `@f0rge/ui`.

## Branch workflow

- `develop` is the integration branch; PRs land there, run `.github/workflows/ci.yml` (ruff + pytest + frontend lint/typecheck/build), then merge.
- Promotion to prod is a PR `develop` → `main`, gated by the same `.github/workflows/ci.yml` (same checks + prod-shaped frontend build).
- After CI green on push, the manifest-driven deploy workflow smokes marrow on Railway and deploys dk tag printer to Coolify (main only).

## Running locally

Postgres (pgvector) via Docker; backend and frontend in separate terminals:

```bash
docker start ht-postgres 2>/dev/null || docker run -d --name ht-postgres \
  -e POSTGRES_USER=health -e POSTGRES_PASSWORD=health -e POSTGRES_DB=health \
  -p 5432:5432 pgvector/pgvector:pg16

cd apps/marrow/backend && uv run uvicorn app.main:app --port 8000 --reload   # :8000
cd apps/marrow/frontend && npm run dev                                      # :3000, proxies /api/* → :8000
```

No root-level `start.sh` — local dev is the Postgres container plus separate backend and frontend processes (see Running locally above).

## Key Paths

- Backend API: http://localhost:8000/api/v1
- Frontend: http://localhost:3000
- Shared libs: `libs/backend/{core,db,storage,testing}/`, `libs/ui/`
- Database: Railway pgvector in deployed envs; local tests use disposable Postgres via `testcontainers` (see `apps/marrow/backend/tests/conftest.py`). `DATABASE_URL` must use asyncpg driver, e.g. `postgresql+asyncpg://...`.
- Photo storage: Railway Buckets in deployed envs; `apps/marrow/backend/photos/` locally

## Shared libraries

Canonical reference for what lives in `libs/` and the non-duplication mandate. See also [`.cursor/rules/shared-libs.mdc`](.cursor/rules/shared-libs.mdc).

| Lib | Import | Contents | Owner | Mandate |
|-----|--------|----------|-------|---------|
| `libs/backend/core` | `f0rge_core` | Domain exceptions, `register_exception_handlers` | `fastapi-backend` | Import only — never re-implement |
| `libs/backend/db` | `f0rge_db` | Engine/session/get_db factories, auth context, RLS mechanism, `unit_of_work`, `BaseCRUD`, mixins | `fastapi-backend` | Import only — never re-implement |
| `libs/backend/storage` | `f0rge_storage` | Object storage client, `resize_image` | `fastapi-backend` | Import only — app wires settings |
| `libs/backend/testing` | `f0rge_testing` | pgvector testcontainer, savepoint session fixtures | `fastapi-backend` | Dev dep only |
| `libs/ui` | `@f0rge/ui`, `@f0rge/ui/api`, `@f0rge/ui/forms` (when present) | 12 shadcn primitives, `cn`, hooks, API client, `FetchError`; Storybook catalogue | `frontend-dev` | All UI primitives from lib; shadcn adds land in `libs/ui` |

**Stays in marrow (deliberately):** shared `Base` instance, `USER_OWNED_TABLES`, LLM/prompts, domain schemas, `CatalogItemCRUD`, `use-autosave-entry`, brand tokens (`--marrow-*`).

**Never create a root `uv.lock`** — `@nxlv/python` silently flips to workspace mode. Always `uv --project <dir>`.

## Conventions

- Python: ruff for linting/formatting, target Python 3.10 (no 3.11+ syntax)
- Use `from __future__ import annotations` in all Python files
- Frontend: TypeScript strict, Tailwind for styling; primitives from `@f0rge/ui`; forms from `@f0rge/ui/forms`; token skins in app CSS; Storybook is the catalogue — see `.cursor/rules/ui-kit.mdc`
- API prefix: /api/v1
- Auth cookie name: ht_session

## Nx conventions

Always-on agent policy: [`.cursor/rules/nx.mdc`](.cursor/rules/nx.mdc). Bugbot / Agent Review checklist: [`.cursor/BUGBOT.md`](.cursor/BUGBOT.md). New apps/libs need `project.json` + `platform:` tags; CI uses `nx affected` (no custom project-list detect job); OpenAPI via `marrow-frontend:codegen:check`; Playwright via `nx run …:e2e`.

## Project rules

Scoped rules in `.cursor/rules/` (auto-applied by glob):

| Rule | Scope |
|------|-------|
| `orchestration.mdc` | Always — planning must delegate to sub-agents |
| `nx.mdc` | Always — Nx registration, cache, affected CI, boundaries |
| `shared-libs.mdc` | `libs/**` — shared library conventions |
| `backend.mdc` | `apps/marrow/backend/**/*.py`, migrations |
| `frontend.mdc` | `apps/marrow/frontend/**/*.tsx`, `apps/marrow/frontend/**/*.ts` |
| `ui-kit.mdc` | `libs/ui/**`, `apps/**/frontend/**` — design-system imports, tokens, primitives |
| `infra.mdc` | `**/fly*.toml`, `.github/**`, `**/Dockerfile`, `**/docker-compose*.yml` |
| `qa-gate.mdc` | tests, workflows |
| `data-pipelines.mdc` | `apps/marrow/backend/scripts/**`, `apps/marrow/backend/data/**` |

`.cursor/rules/` is read **only at workspace root** — nested `.cursor/rules/` in a subdirectory is silently ignored. Nested `AGENTS.md` **is** auto-applied for that subtree; use it for per-app instructions (see `apps/dk/tag-printer/AGENTS.md`, `libs/ui/AGENTS.md`).

## Sub-agents

Delegate per `~/.cursor/rules/leo-system-wide.mdc` and `.cursor/rules/orchestration.mdc`. Every plan names a sub-agent per work chunk before implementation. Brief each sub-agent to read `~/.cursor/agent-memory/<agent-name>/MEMORY.md` before starting and write back gotchas when done.

## Creating issues

Agent-ready GitHub issue authoring (scope split, decision surfacing, parent/sub-issues): `.cursor/skills/create-github-issue/SKILL.md`.

## Shipping features

End-to-end workflow (prompt or GitHub issue → develop → dev smoke → main PR): `.cursor/skills/ship-feature/SKILL.md`.

## PR review context

Review playbooks live in `.cursor/review-context/`. **Nothing loads these automatically** — no workflow reads them. When reviewing a PR, read `_shared/*.md` plus the playbook matching the diff's area (`fastapi-backend`, `frontend-dev`, `devops`, `qa-engineer`).

**Bugbot / Agent Review:** [`.cursor/BUGBOT.md`](.cursor/BUGBOT.md) is auto-loaded by Bugbot (project `.mdc` rules are not). Keep Nx gates and UI kit import bans there; point playbooks at `nx.mdc` / `BUGBOT.md` instead of duplicating checklists.
## Agent memory

**Canonical:** `~/.cursor/agent-memory/<agent>/` (global, cross-project).

## Writing issues for sub-agents

Every implementation issue is a self-contained prompt for an agent that has no prior context. Use this structure, in this order:

1. **Problem (Why)** — one paragraph on what hurts now. Describe the constraint, not the solution.
2. **Goal** — one sentence on what changes when this is done.
3. **Sub-agent assignments** — table mapping each chunk to a sub-agent (`fastapi-backend`, `frontend-dev`, `data-engineer`, `data-scientist`, `devops`, `qa-engineer`). Each agent reads `~/.cursor/agent-memory/<agent-name>/MEMORY.md` before starting and writes back what's worth keeping when done.
4. **Proposed approach** — high-level technical approach + reasoning. Design, not implementation. Each issue gets a dedicated per-issue planning pass before code is written.
5. **Files** — *Existing modified* (paths + line numbers where known) and *New* (paths to create). Starting points, not exhaustive.
6. **Out of scope (non-goals)** — stated positively ("do not change X"). Agents cannot infer from omission.
7. **Boundaries** — tiered:
   - Always: actions the agent can take without asking
   - Ask first: actions that need user approval
   - Never: hard stops (secrets, force-push, destructive ops, `--no-verify`)
8. **Acceptance criteria / Definition of done** — concrete, runnable, objectively true/false. **Must include a live-server walkthrough** per `feedback_qa_e2e_live_server.md` — pytest passing is not the gate.
9. **Dependencies** — `Blocked by:` / `Blocks:` / `Required env / secrets:`.
10. **Rollback** — only when destructive or production-affecting. Trigger criteria + concrete revert steps.

**Anti-patterns to avoid:**
- Vague acceptance criteria ("user can log in" — write "POST /auth/login with valid credentials returns 200 and sets `ht_session` cookie")
- Implicit scope ("just clean things up while you're there" — list every file)
- Bundling unrelated work (one issue = one cohesive change)
- Skipping the live-server walkthrough in favor of "tests pass"
- Omitting boundaries — without them, agents take defensible-but-unwanted actions

**Sizing heuristic:** if an issue's sub-agent table has more than ~5 agents listed, or estimated effort exceeds ~5 person-days, split it.

References:
- [Osmani — How to write a good spec for AI agents](https://addyosmani.com/blog/good-spec/)
- [GitHub — Getting the best results from Copilot coding agent](https://docs.github.com/en/copilot/tutorials/cloud-agent/get-the-best-results)
- [GitHub — Reliable AI workflows with agentic primitives and context engineering](https://github.blog/ai-and-ml/github-copilot/how-to-build-reliable-ai-workflows-with-agentic-primitives-and-context-engineering/)

## Cursor Cloud specific instructions

The VM snapshot already has `uv`, Node 22, Docker, backend `.venv`, `ruff`, and frontend `node_modules`. The startup update script only refreshes deps (`uv sync --frozen --project apps/marrow/backend`, `uv tool install "ruff==$(cat .github/ruff-version)"`, `npm ci` at repo root). Services and the database are NOT auto-started — bring them up as below. Standard run/lint/test commands live in this file, `.cursor/rules/backend.mdc`, and `.cursor/rules/qa-gate.mdc`.

### Database + Docker (must start manually each session)
- There is **no local dev docker-compose**; deploy is Railway (`railway*.toml` + GitHub Actions smoke) and Coolify for dk.
- The Docker daemon is not auto-started. Start it once per session: `sudo dockerd > /tmp/dockerd.log 2>&1 &` then `sudo chmod 666 /var/run/docker.sock` (lets `uv run pytest`'s testcontainers reach the socket as the `ubuntu` user). `/etc/docker/daemon.json` is pre-set to `fuse-overlayfs` + `containerd-snapshotter: false` (required for Docker 29 in this VM) — do not change it.
- Backend + tests need a **pgvector** Postgres on `localhost:5432` with user/pass/db all `health`. Start/reuse it:
  `docker start ht-postgres 2>/dev/null || docker run -d --name ht-postgres -e POSTGRES_USER=health -e POSTGRES_PASSWORD=health -e POSTGRES_DB=health -p 5432:5432 pgvector/pgvector:pg16`
- `apps/marrow/backend/.env` (gitignored) holds local secrets. If missing, recreate with: `JWT_SECRET` (any string), `SETTINGS_ENCRYPTION_KEY` (a valid Fernet key: `uv run --project apps/marrow/backend python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`), `DATABASE_URL=postgresql+asyncpg://health:health@localhost:5432/health`, `PHOTO_DIR=photos`, and `HEALTHTRACKER_RO_PASSWORD` / `HEALTHTRACKER_APP_PASSWORD` (any random strings, consumed by migrations 004/019). Do **not** put `CORS_ORIGINS` as a bare string in `.env` — it is a `list[str]` parsed as JSON and a plain value crashes startup; omit it (default already allows `http://localhost:3000`).

### Migrations gotcha
- Alembic migrations 004/019 read `HEALTHTRACKER_RO_PASSWORD` / `HEALTHTRACKER_APP_PASSWORD` from **`os.environ`, not** from `.env` via pydantic. Export the `.env` before migrating: `cd apps/marrow/backend && set -a && . ./.env && set +a && uv run alembic upgrade head`. Running the backend itself does not need this (pydantic loads `.env`), only the migration step does.
- **Cross-tenant data migrations under FORCE RLS:** use `f0rge_db.rls.migration_bypass` (transient `app.service_role = 'migrator'` policy). Do not loop per user with `set_config('app.user_id', ...)`. Single-tenant reference-user seeds may still use `app.user_id`. Full convention: `.cursor/rules/backend.mdc` § Alembic migrations under FORCE RLS.

### Running
- Backend `:8000` + frontend `:3000` (frontend proxies `/api/*` → `:8000`): run `uv run uvicorn app.main:app --port 8000 --reload` in `apps/marrow/backend` and `npm run dev` in `apps/marrow/frontend` (from repo root: `npx nx run marrow-frontend:dev`). Install deps with `npm ci` at repo root (workspaces).
- Signup rejects non-routable email TLDs (e.g. `.local`); use a normal domain like `demo@example.com` when testing auth.
- Optional services (not needed for the core check-in app): embedding worker (`uv run python -m app.embedding_pipeline`, needs `OPENROUTER_API_KEY`) and MCP server (`uv run python -m app.mcp ...`).
