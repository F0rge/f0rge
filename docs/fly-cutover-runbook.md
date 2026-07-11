# Fly.io cutover runbook (Marrow)

Parallel stack only until Leo signs off. **Do not run DNS cutover or stop Coolify without explicit approval.**

## Current Fly dev stack

| Component | Fly app | URL |
|---|---|---|
| API + worker | `marrow-dev` | https://marrow-dev.fly.dev |
| MCP | `marrow-mcp-dev` | https://marrow-mcp-dev.fly.dev |
| Frontend | `marrow-ui-dev` | https://marrow-ui-dev.fly.dev |
| Postgres | Shared MPG `health-tracker-db-prod` — database `marrow_dev` | via secrets |
| Object storage | Tigris (when billing enabled) | via `fly storage create` |

## Fly prod stack (parallel — no DNS cutover)

| Component | Fly app | URL |
|---|---|---|
| API + worker | `marrow` | https://marrow.fly.dev |
| MCP | `marrow-mcp` | https://marrow-mcp.fly.dev |
| Frontend | `marrow-ui` | https://marrow-ui.fly.dev |
| Postgres | Shared MPG `health-tracker-db-prod` (`z23750v13yl096d1`, `fra`) — database `marrow` | via secrets |
| Object storage | Tigris on API prod app | via `fly storage create` |

### Shared MPG cluster (one cluster, multiple apps + databases)

Dev and prod Fly stacks share **one** MPG cluster (`z23750v13yl096d1`, `fra`). Environment isolation is by **database name**, not separate clusters:

| Database | Environment | Attached apps |
|---|---|---|
| `marrow` | prod | `marrow`, `marrow-mcp` |
| `marrow_dev` | dev | `marrow-dev`, `marrow-mcp-dev` |

Consolidation script (dev data migration): `./scripts/fly-mpg-consolidate-dev.sh`.

Deploy configs: `backend/fly.prod.toml`, `backend/fly.mcp.prod.toml`, `frontend/fly.prod.toml`.

```bash
cd backend && fly deploy --config fly.prod.toml
cd backend && fly deploy --config fly.mcp.prod.toml
cd frontend && fly deploy --config fly.prod.toml
```

Coolify/Pi remains authoritative for `health*.leo-figueiredo.com` until cutover.

## CI/CD (automated)

After merge to `develop` or `main`, Fly deploys run automatically once the matching CI workflow succeeds:

| Branch | CI gate | Fly workflow | Apps deployed |
|---|---|---|---|
| `develop` | `CI (develop)` | `.github/workflows/fly-deploy-develop.yml` | `marrow-dev`, `marrow-mcp-dev`, `marrow-ui-dev` |
| `main` | `CI (main)` | `.github/workflows/fly-deploy-main.yml` | `marrow`, `marrow-mcp`, `marrow-ui` |

Deploy order: **API** (runs `alembic upgrade head` via `release_command`) → **MCP** → **frontend**. Failed CI does not trigger a deploy. PR CI runs are ignored (push-only).

**One-time setup:** add a repo secret `FLY_API_TOKEN` in GitHub → Settings → Secrets and variables → Actions. Create a deploy token at [fly.io/user/personal_access_tokens](https://fly.io/user/personal_access_tokens). Without it, the Fly workflows fail at the first `flyctl deploy` step.

`workflow_run` workflows execute from the repo default branch — both workflow files must be on `main` before automated deploys activate.

## Deploy from feature branch (manual)

```bash
export FLY_API_TOKEN=...
cd backend && fly deploy --config fly.toml
cd backend && fly deploy --config fly.mcp.toml
cd frontend && fly deploy --config fly.toml
```

## Required secrets (API app)

- `DATABASE_URL` — runtime URL as the least-privilege `healthtracker-app` (writer) role (`postgresql+asyncpg://...`). `app.db_url.resolve_database_url` coerces `postgres://`/`postgresql://` schemes, so an `fly mpg attach` URL works as-is.
- `MIGRATION_DATABASE_URL` — owner-capable role for `alembic upgrade head` only (see MPG setup notes). The `[deploy] release_command` runs `DATABASE_URL="${MIGRATION_DATABASE_URL:-$DATABASE_URL}" uv run alembic upgrade head` so migrations run as owner while runtime stays least-privilege.
- `JWT_SECRET` — ≥32 random bytes
- `SETTINGS_ENCRYPTION_KEY`
- `HEALTHTRACKER_RO_PASSWORD` — only for self-hosted Pi; skipped on Fly (`FLY_MPG_SKIP_ROLE_DDL=1`)
- `CORS_ORIGINS` — include Fly frontend URL (`https://marrow-ui-dev.fly.dev`, `https://marrow-ui.fly.dev`)
- Tigris: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, `BUCKET_NAME`, `AWS_REGION=auto`

MCP app: `MCP_READONLY_DATABASE_URL` (attach with `--username healthtracker-ro`).

## MPG setup notes

- **Cluster:** `z23750v13yl096d1` (`health-tracker-db-prod`, region `fra`). MPG not available in `cdg`. Cluster display name is unchanged; databases were renamed to `marrow` / `marrow_dev`.
- **Databases:** `marrow` (prod), `marrow_dev` (dev Fly stack). Create with `fly mpg databases create z23750v13yl096d1 -n marrow_dev`.
- **Extensions** (per database): `vector`, `citext` (migration 020)
  ```bash
  fly mpg databases extensions enable vector z23750v13yl096d1 -d marrow
  fly mpg databases extensions enable citext z23750v13yl096d1 -d marrow
  fly mpg databases extensions enable vector z23750v13yl096d1 -d marrow_dev
  fly mpg databases extensions enable citext z23750v13yl096d1 -d marrow_dev
  ```
- **MPG users** (cluster-scoped): `healthtracker-ro` (reader), `healthtracker-app` (writer), `htmigrate` (`schema_admin`)
- Set `FLY_MPG_SKIP_ROLE_DDL=1` — roles provisioned via `fly mpg users create`
- **Migration role:** migrations run as `htmigrate`; runtime uses `healthtracker-app` (writer). See migration 027 / RLS notes in repo.
- **Attach commands** (use `fly secrets set --stage` + `fly deploy` if secrets already exist — attach alone redeploys):
  ```bash
  CLUSTER=z23750v13yl096d1

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
- **Pi dump restore:** run `alembic upgrade head` as `htmigrate`, not `healthtracker-app`. Then grant tables to `healthtracker-app` / `healthtracker-ro` (quote hyphenated names). See `scripts/fly-mpg-consolidate-dev.sh` for grant SQL.
- **MCP app:** needs both `MCP_READONLY_DATABASE_URL` and `DATABASE_URL` (reader URL for both is fine on Fly).

## Marrow rename migration (2026-07)

Legacy apps (`health-tracker-*`) were replaced with `marrow*` apps via blue/green deploy. Databases were migrated by **copy** (`pg_dump` → `pg_restore` into new `marrow` / `marrow_dev` databases). In-place `ALTER DATABASE` requires the `postgres` owner on Fly MPG. Legacy databases `fly-db` and `health_dev` remain on the cluster for rollback until Leo signs off.

Helper script: `./scripts/fly-rename-marrow.sh`. Pre-rename backup ID recorded in PR notes.

## Data migration (dry-run)

```bash
PI_DATABASE_URL=postgresql://health:***@<pi-host>:5432/health \
  ./scripts/fly-migrate-from-pi.sh --dry-run
```

Full restore: pg_dump → scratch MPG → verify per-table counts vs Pi → copy files to Tigris under Leo's `user_id` prefix.

## Pre-cutover checklist

- [ ] Two-user isolation gate GREEN on Fly dev
- [ ] Leo data counts match Pi source on scratch restore
- [ ] Tigris billing enabled + photo round-trip survives redeploy
- [ ] `JWT_SECRET` + all secrets set on prod Fly apps (not created until cutover approval)
- [ ] Rollback plan documented (re-point DNS to Pi; Pi kept running)

## Cutover (ASK LEO FIRST)

1. Final backup of Pi Postgres + volumes
2. Restore prod data to prod MPG cluster
3. Point Cloudflare `health*.leo-figueiredo.com` to Fly apps
4. Update `CORS_ORIGINS` on prod Fly API
5. Smoke test prod URLs
6. Stop Coolify stacks only after 48h stable

## Rollback

Re-point DNS/tunnels to Pi. Keep MPG/Tigris as staging until re-verified. Do not delete Pi data or backups until signed off. To undo database rename (only if no new writes): `ALTER DATABASE marrow RENAME TO "fly-db"; ALTER DATABASE marrow_dev RENAME TO health_dev;`
