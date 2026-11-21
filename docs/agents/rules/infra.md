> Canonical decisions: [`docs/adr/README.md`](../../adr/README.md). Follow [P-005](../../adr/governance.md#p-005) for review/automatic squash merging. A reviewed merge to `main` releases the affected Apps ([P-006](../../adr/governance.md#p-006)). Legacy commands below remain inventory, not approved exceptions.

# f0rge Infrastructure

Use the [shared protocol](../protocol.md) and resolve each path with `node scripts/agents/agents.mjs route <repo-relative-path...>`. `f0rge-delivery` owns build/CI work; `f0rge-devops` owns runtime infrastructure and operations. The manifest assigns the precise primary and reviewers.

## Pipeline

Overview and App table: [root `AGENTS.md`](../../../AGENTS.md#cicd). Programs, deploy block, manual Releases and accepted ceilings: [the deploy page](../../../.github/deploy/README.md). Terms: [Delivery glossary](../../../.github/CONTEXT.md).

- A reviewed merge to `main` with CI passing releases every affected App (P-006). There is no release hold, no per-release approval and no release tag.
- Service names, health paths, migration and start commands live in each Project's deploy block. Provider services are found by name. There are no provider config files in the repo.
- Migrations are a service's `preDeployCommand`; Railway runs it before the new code starts (P-020). The release program refuses `preDeployCommand` and `startCommand` on a Pi service.
- Each App's Host token lives in the GitHub environment named after the App: `RAILWAY_TOKEN` (a project token), or `COOLIFY_URL` and `COOLIFY_TOKEN`. Leo creates tokens and switches each App at its Host himself. An App that is not switched fails closed.
- On the Pi, Coolify pulls the Artifact. Coolify's own Healthcheck stays off; every Pi Dockerfile needs a Docker `HEALTHCHECK`, which decides whether a Release is healthy. Do not SSH to the Pi to release, and do not add a per-App release program (P-048).
- Provider operations outside the pipeline (variables, domains, volumes, databases, moving an App to another Host) need their own task authorization.

## Host notes

| App | Notes |
|-----|-------|
| marrow | Railway project `Marrow`. Services `marrow-api`, `marrow-worker`, `marrow-mcp` (no HTTP health path) and `marrow-frontend`. |
| firstout | **Own** Railway project `Firstout`; hosts `firstout.co.za` / `api.firstout.co.za`. |
| daskasas | Own Railway project `DasKasas`; services `storefront` and `storefront-commerce`. |
| envmon | Pi, Coolify, internal only (backend 5001, frontend 5000). SQLite `/app/data/readings.db` on volume `environment-monitor_sensor_data`. |

# Marrow Infrastructure (Railway)

**Deploy gotchas:** read [`apps/marrow/backend/docs/railway_env.md`](../../../apps/marrow/backend/docs/railway_env.md) and verify the current provider state. Cloudflare DNS Edit for `marrow-health.com` often needs UI (API token may 9109/7003).

## Environments

| Env | Branch | Frontend | Backend API | MCP |
|---|---|---|---|---|
| Production | `main` | https://marrow-health.com | https://api.marrow-health.com | https://mcp.marrow-health.com |

**Do not open pull requests against `develop`.** A remote `develop` ref may still exist; it is not an approved long-lived branch.

Railway `*.up.railway.app` hostnames also work for interim smoke.

- Short-lived feature branches off `main` (`feat/…`, `fix/…`, `chore/…`, `docs/…`, `hotfix/…`); PRs into `main` only; CI green; squash merge. No long-lived branches. Hotfixes are ordinary PRs into `main`.
- Green CI on `main` releases Marrow when the change affects it.

## Postgres / Redis / photos

- Postgres: Railway service `Postgres` (`d76d2b40-…`) with pgvector; roles via `scripts/railway_bootstrap_roles.sql`
- Set `SKIP_DATABASE_ROLE_DDL=1` on Railway apps after bootstrap (managed roles are already provisioned)
- Migrations: the `preDeployCommand` in `marrow-backend`'s deploy block runs alembic as `MIGRATION_DATABASE_URL` (htmigrate) before each Release. Runtime uses `DATABASE_URL` (healthtracker_app).
- Redis: Railway Redis plugin (`REDIS_URL`)
- Photos: Railway Buckets (`AWS_*`, `BUCKET_NAME`); sync runbook `scripts/railway_bucket_sync.sh`

`apps/marrow/backend/docker-entrypoint.sh` still supports `RUN_MIGRATIONS=1` for local Docker builds.

## Local development

Postgres via Docker; backend and frontend in separate terminals (no root `start.sh`):

```bash
docker start ht-postgres 2>/dev/null || docker run -d --name ht-postgres \
  -e POSTGRES_USER=health -e POSTGRES_PASSWORD=health -e POSTGRES_DB=health \
  -p 5432:5432 pgvector/pgvector:pg16

cd apps/marrow/backend && uv run uvicorn app.main:app --port 8000 --reload
cd apps/marrow/frontend && npm run dev   # :3000
```

## Monorepo build context

Docker builds use **repo root** as context (not `apps/marrow/{backend,frontend}`):

```bash
docker build -f apps/marrow/backend/Dockerfile .
docker build -f apps/marrow/frontend/Dockerfile .
```

`.dockerignore` files are **root-relative whitelists** (`*` then `!apps/marrow/...` then `!libs/**`). Blacklist patterns ship the whole repo to remote builders.

Frontend Dockerfile: root `npm ci` (workspaces), `npm run build -w apps/marrow/frontend`. Backend Dockerfile: `COPY libs/backend/...` before `uv sync`.

## Root `uv.lock` warning

**Never create a root `uv.lock`.** `@nxlv/python`'s UVProvider checks `fs.existsSync(<root>/uv.lock)` and silently flips to workspace mode, breaking per-project lock isolation. Always `uv --project <dir>`.

## New config vars checklist

For every new `app/config.py` setting:

- [ ] In `apps/marrow/backend/.env.example`
- [ ] README/deploy doc updated if required
- [ ] Production variable changes are a separately authorized Railway operation; the pipeline does not set variables, and the merge releases the code
- [ ] Degrades gracefully when missing (no 500 storm)
- [ ] Startup warning when feature enabled but credentials missing
