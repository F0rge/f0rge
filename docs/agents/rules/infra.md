> Canonical decisions: [`docs/adr/README.md`](../../adr/README.md). New apps follow that index. Commands and safety rules below stay in force for the legacy area they name. They are not an approved exception and they do not migrate the app. Leo approves every production release. Do not enable auto-merge, and do not merge or deploy without that approval.

# f0rge Infrastructure

Use the [shared protocol](../protocol.md) and resolve each path with `node scripts/agents/agents.mjs route <repo-relative-path...>`. `f0rge-delivery` owns build/CI work; `f0rge-devops` owns runtime infrastructure and operations. The manifest assigns the precise primary and reviewers; neither role authorizes a production release.

## Historical deployment target inventory

| App | Target | Branches | Manifest component |
|-----|--------|----------|-------------------|
| marrow | Railway project `Marrow` (`a633a271-…`) | `main` only | `marrow-backend`, `marrow-frontend` |
| firstout | **Own** Railway project `Firstout` (`c76d8df1-…`). Production environment `9f7b0c34-bd95-442b-b746-a9791dcc2895`; hosts `firstout.co.za` / `api.firstout.co.za` | `main` only | `firstout-backend`, `firstout-frontend` |
| DasKasas storefront | Own Railway project `DasKasas` (`d58a2884-…`), production (`d73ff2d5-…`); services `storefront` and `storefront-commerce` | `main` only | `daskasas-web`, `daskasas-commerce` (outside this manifest) |
| dk tag printer | Pi Coolify | `main` only | `dk-tag-printer-backend`, `dk-tag-printer-frontend` |
| buycycle | Pi Coolify, internal only (host ports 8095/8096, no domain); tracker = Coolify scheduled task; Turso DB on `/data` volume | `main` only | `buycycle` |
| environment-monitor | Pi Coolify, internal only (backend 5001, frontend 5000). SQLite `/app/data/readings.db` on volume `environment-monitor_sensor_data` | `main` only | `environment-monitor-backend`, `environment-monitor-frontend` |

The existing **Deploy** workflow is disabled. This proposed change makes [`deploy.yml`](../../../.github/workflows/deploy.yml) manual preparation only and [`deploy-reusable.yml`](../../../.github/workflows/deploy-reusable.yml) an inert, failing release hold. Neither calls providers, uses deployment credentials or runs production smoke. Both reference the configured GitHub `production` environment with `deployment: false`; that protection has not been exercised with these workflows and does not protect direct Railway/Coolify operations.

Runtime provider state has not been checked for this change. Before any authorized release work, read [the release hold requirements](../../../.github/deploy/README.md): tested immutable artifact promotion, deployment-secret migration, an independent automation/approval identity and control of alternate provider paths remain future work. Leo's explicit release approval is required.

Historical source-based path: [the manifest](../../../.github/deploy/manifest.yml) plus Nx affected selected Railway smoke or Coolify webhook POSTs. Retained [`railway-smoke-reusable.yml`](../../../.github/workflows/railway-smoke-reusable.yml) and webhook names are investigation inventory, not an active release path. The former Coolify secrets were `COOLIFY_BASE_URL`, `COOLIFY_WEBHOOK_DASKASAS_BACKEND`, `COOLIFY_WEBHOOK_DASKASAS_FRONTEND`, `COOLIFY_WEBHOOK_BUYCYCLE`, `COOLIFY_WEBHOOK_ENVMON_BACKEND` and `COOLIFY_WEBHOOK_ENVMON_FRONTEND`; their current storage, consumers and permissions require a separate audit.

# Marrow Infrastructure (Railway)

**Deploy gotchas:** read [`apps/marrow/backend/docs/railway_env.md`](../../../apps/marrow/backend/docs/railway_env.md) and verify the current provider state. Cloudflare DNS Edit for `marrow-health.com` often needs UI (API token may 9109/7003).

## Environments

| Env | Branch | Frontend | Backend API | MCP |
|---|---|---|---|---|
| Production | `main` | https://marrow-health.com | https://api.marrow-health.com | https://mcp.marrow-health.com |

**Do not open pull requests against `develop`.** A remote `develop` ref may still exist; it is not an approved long-lived branch. Railway and Coolify files describe deploys from `main`. That description is configuration inventory, not a live check and not Leo's approval of a release.

Railway `*.up.railway.app` hostnames also work for interim smoke.

- Short-lived feature branches off `main` (`feat/…`, `fix/…`, `chore/…`, `docs/…`, `hotfix/…`); PRs into `main` only; CI green; squash merge. No long-lived branches. Hotfixes are ordinary PRs into `main`.
- Green CI on `main` does not trigger a release in the proposed workflows. Preserve the release hold; historical reruns and direct provider paths need separate verification before activation.

## Railway services

| Role | Service | Config |
|---|---|---|
| API | `marrow-api` | `apps/marrow/backend/railway.toml` |
| Worker | `marrow-worker` | `apps/marrow/backend/railway.worker.toml` |
| MCP | `marrow-mcp` | `apps/marrow/backend/railway.mcp.toml` (no HTTP healthcheckPath) |
| Frontend | `marrow-frontend` | `apps/marrow/frontend/railway.toml` |

Shared monorepo: **no Root Directory**; Dockerfile build context = repo root.

## Postgres / Redis / photos

- Postgres: Railway service `Postgres` (`d76d2b40-…`) with pgvector; roles via `scripts/railway_bootstrap_roles.sql`
- Set `SKIP_DATABASE_ROLE_DDL=1` on Railway apps after bootstrap (managed roles are already provisioned)
- Migrations: Railway `preDeployCommand` runs alembic as `MIGRATION_DATABASE_URL` (htmigrate). Runtime uses `DATABASE_URL` (healthtracker_app).
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
- [ ] Plan production variable changes for a separately authorized Railway operation; preparation does not set them
- [ ] Degrades gracefully when missing (no 500 storm)
- [ ] Startup warning when feature enabled but credentials missing
