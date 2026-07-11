# Marrow Fly.io deploy runbook

Production and develop run entirely on Fly.io. Custom domains on `marrow-health.com` (Cloudflare DNS-only → Fly).

> **Org migration:** See [fly-org-migration.md](fly-org-migration.md) for the `personal` → `f0rge` org cutover runbook.

## Fly dev stack

| Component | Fly app | URL |
|---|---|---|
| API + worker | `marrow-dev` | https://marrow-dev.fly.dev · https://api-dev.marrow-health.com |
| MCP | `marrow-mcp-dev` | https://marrow-mcp-dev.fly.dev |
| Frontend | `marrow-ui-dev` | https://marrow-ui-dev.fly.dev · https://app-dev.marrow-health.com |
| Postgres | MPG `f0rge-db` (`nlkxjo5m3240y93v`, `fra`) — database `marrow_dev` | via secrets |
| Object storage | Tigris | via `fly storage create` |

## Fly prod stack

| Component | Fly app | URL |
|---|---|---|
| API + worker | `marrow` | https://marrow.fly.dev · https://api.marrow-health.com |
| MCP | `marrow-mcp` | https://marrow-mcp.fly.dev |
| Frontend | `marrow-ui` | https://marrow-ui.fly.dev · https://marrow-health.com |
| Postgres | MPG `f0rge-db` (`nlkxjo5m3240y93v`, `fra`) — database `marrow` | via secrets |
| Object storage | Tigris on API prod app | via `fly storage create` |

### Shared MPG cluster

Dev and prod share **one** MPG cluster (`nlkxjo5m3240y93v`, `fra`, name `f0rge-db`, org `f0rge`). Isolation is by database name:

| Database | Environment | Attached apps |
|---|---|---|
| `marrow` | prod | `marrow`, `marrow-mcp` |
| `marrow_dev` | dev | `marrow-dev`, `marrow-mcp-dev` |

Deploy configs: `apps/marrow/backend/fly.prod.toml`, `apps/marrow/backend/fly.mcp.prod.toml`, `apps/marrow/frontend/fly.prod.toml`.

```bash
cd apps/marrow/backend && fly deploy --config fly.prod.toml
cd apps/marrow/backend && fly deploy --config fly.mcp.prod.toml
cd apps/marrow/frontend && fly deploy --config fly.prod.toml
```

## CI/CD (automated)

After merge to `develop` or `main`, Fly deploys run automatically once the matching CI workflow succeeds:

| Branch | CI gate | Fly workflow | Apps deployed |
|---|---|---|---|
| `develop` | `CI (develop)` | `.github/workflows/fly-deploy-develop.yml` | `marrow-dev`, `marrow-mcp-dev`, `marrow-ui-dev` |
| `main` | `CI (main)` | `.github/workflows/fly-deploy-main.yml` | `marrow`, `marrow-mcp`, `marrow-ui` |

Deploy order: **API** (runs `alembic upgrade head` via `release_command`) → **MCP** (serial after API); **frontend** runs in parallel with MCP when both are affected. Each component is a separate job (`plan`, `deploy api`, `deploy mcp`, `deploy frontend`, `smoke`). Failed CI does not trigger a deploy. PR CI runs are ignored (push-only).

**Manual dispatch** — redeploy one component without touching the others:

```bash
gh workflow run "Fly Deploy (develop)" --ref develop -f component=mcp
gh workflow run "Fly Deploy (main)" --ref main -f component=api
```

`component` choices: `all` (default), `api`, `mcp`, `frontend`. MCP-only dispatch skips API (and migrations); use only when schema is already current.

**CI** — `CI (develop)` / `CI (main)` run parallel `backend` and `frontend` jobs when Nx affected; aggregate `ci` job is the required branch check. Post-deploy `smoke` curls API/frontend health for components that deployed.

**One-time setup:** add repo secret `FLY_API_TOKEN` in GitHub → Settings → Secrets and variables → Actions.

`workflow_run` workflows execute from the repo default branch — both workflow files must be on `main` before automated deploys activate.

## Deploy from feature branch (manual)

```bash
export FLY_API_TOKEN=...
cd apps/marrow/backend && fly deploy --config fly.toml
cd apps/marrow/backend && fly deploy --config fly.mcp.toml
cd apps/marrow/frontend && fly deploy --config fly.toml
```

## Required secrets (API app)

- `DATABASE_URL` — runtime URL as `healthtracker-app` (writer). `app.db_url.resolve_database_url` coerces schemes for asyncpg.
- `MIGRATION_DATABASE_URL` — `htmigrate` for `alembic upgrade head` only (`release_command`).
- `JWT_SECRET` — ≥32 random bytes
- `SETTINGS_ENCRYPTION_KEY`
- `FLY_MPG_SKIP_ROLE_DDL=1` — roles provisioned via `fly mpg users create`
- `CORS_ORIGINS` — JSON array including custom domains and `*.fly.dev` frontends
- Tigris: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, `BUCKET_NAME`, `AWS_REGION=auto`

MCP app: `MCP_READONLY_DATABASE_URL` + `DATABASE_URL` (reader URLs).

## MPG setup

- **Cluster:** `nlkxjo5m3240y93v` (`f0rge-db`, org `f0rge`, region `fra`)
- **Databases:** `marrow` (prod), `marrow_dev` (dev)
- **Extensions** (per database): `vector`, `citext`
- **Users:** `healthtracker-ro`, `healthtracker-app`, `htmigrate` (`schema_admin`)

Migrations run as `htmigrate` via `[deploy] release_command`; runtime uses `healthtracker-app` so RLS stays enforced.

**Attach commands:**

```bash
CLUSTER=nlkxjo5m3240y93v

# Prod API
fly mpg attach $CLUSTER -a marrow -d marrow -u healthtracker-app --variable-name DATABASE_URL
fly mpg attach $CLUSTER -a marrow -d marrow -u htmigrate --variable-name MIGRATION_DATABASE_URL

# Prod MCP
fly mpg attach $CLUSTER -a marrow-mcp -d marrow -u healthtracker-ro --variable-name MCP_READONLY_DATABASE_URL
fly mpg attach $CLUSTER -a marrow-mcp -d marrow -u healthtracker-ro --variable-name DATABASE_URL

# Dev API
fly mpg attach $CLUSTER -a marrow-dev -d marrow_dev -u healthtracker-app --variable-name DATABASE_URL
fly mpg attach $CLUSTER -a marrow-dev -d marrow_dev -u htmigrate --variable-name MIGRATION_DATABASE_URL

# Dev MCP
fly mpg attach $CLUSTER -a marrow-mcp-dev -d marrow_dev -u healthtracker-ro --variable-name MCP_READONLY_DATABASE_URL
fly mpg attach $CLUSTER -a marrow-mcp-dev -d marrow_dev -u healthtracker-ro --variable-name DATABASE_URL
```

Helper scripts: `./scripts/fly-mpg-consolidate-dev.sh`, `./scripts/fly-mpg-migrate-cluster.sh`, `./scripts/fly-rename-marrow.sh`.

## Custom domains (`marrow-health.com`)

Renaming Fly apps does not move certs or DNS. After creating new apps, re-add hostnames and repoint Cloudflare (**DNS only** / grey cloud).

| Hostname | Fly app | A | AAAA |
|---|---|---|---|
| `app-dev.marrow-health.com` | `marrow-ui-dev` | `66.241.125.174` | `2a09:8280:1::148:4401:0` |
| `api-dev.marrow-health.com` | `marrow-dev` | (see `fly certs setup`) | |
| `marrow-health.com` | `marrow-ui` | `66.241.124.129` | `2a09:8280:1::148:43ff:0` |
| `api.marrow-health.com` | `marrow` | `213.188.212.155` | `2a09:8280:1::148:43fb:0` |

```bash
fly certs add <hostname> -a <app>
fly certs setup <hostname> -a <app>
```

Add ACME CNAME `_acme-challenge.<hostname>` until `fly certs check` shows **Issued**. Grey cloud avoids HTTP 525 during cert issuance.

## Historical migrations (2026-07)

- **App rename:** `health-tracker-*` → `marrow*` via blue/green deploy; legacy Fly apps destroyed.
- **MPG cluster rename:** `z23750v13yl096d1` (`health-tracker-db-prod`) → `d1zj5omzqwvryqkv` (`marrow-db-prod`); old cluster destroyed.
- **Pi/Coolify:** Health Tracker stacks and `health*.leo-figueiredo.com` tunnel routes removed; Fly is sole deploy target.
