# Fly.io cutover runbook (health-tracker)

Parallel stack only until Leo signs off. **Do not run DNS cutover or stop Coolify without explicit approval.**

## Current Fly dev stack

| Component | Fly app | URL |
|---|---|---|
| API + worker | `health-tracker-api-dev` | https://health-tracker-api-dev.fly.dev |
| MCP | `health-tracker-mcp-dev` | https://health-tracker-mcp-dev.fly.dev |
| Frontend | `health-tracker-web-dev` | https://health-tracker-web-dev.fly.dev |
| Postgres | MPG `health-tracker-db-dev` (`d1zj5omzqg9ryqkv`, `fra`) | via secrets |
| Object storage | Tigris (when billing enabled) | via `fly storage create` |

## Fly prod stack (parallel — no DNS cutover)

| Component | Fly app | URL |
|---|---|---|
| API + worker | `health-tracker-api-prod` | https://health-tracker-api-prod.fly.dev |
| MCP | `health-tracker-mcp-prod` | https://health-tracker-mcp-prod.fly.dev |
| Frontend | `health-tracker-web-prod` | https://health-tracker-web-prod.fly.dev |
| Postgres | MPG `health-tracker-db-prod` (`fra`) | via secrets |
| Object storage | Tigris on API prod app | via `fly storage create` |

Deploy configs: `backend/fly.prod.toml`, `backend/fly.mcp.prod.toml`, `frontend/fly.prod.toml`.

```bash
cd backend && fly deploy --config fly.prod.toml
cd backend && fly deploy --config fly.mcp.prod.toml
cd frontend && fly deploy --config fly.prod.toml
```

Coolify/Pi remains authoritative for `health*.leo-figueiredo.com` until cutover.

## Deploy from feature branch

```bash
export FLY_API_TOKEN=...
cd backend && fly deploy --config fly.toml
cd backend && fly deploy --config fly.mcp.toml
cd frontend && fly deploy --config fly.toml
```

## Required secrets (API app)

- `DATABASE_URL` — direct MPG URL (`postgresql+asyncpg://...`)
- `JWT_SECRET` — ≥32 random bytes
- `SETTINGS_ENCRYPTION_KEY`
- `HEALTHTRACKER_RO_PASSWORD` — only for self-hosted Pi; skipped on Fly (`FLY_MPG_SKIP_ROLE_DDL=1`)
- `CORS_ORIGINS` — include Fly frontend URL
- Tigris: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, `BUCKET_NAME`, `AWS_REGION=auto`

MCP app: `MCP_READONLY_DATABASE_URL` (attach with `--username healthtracker-ro`).

## MPG setup notes

- Region: `fra` (MPG not available in `cdg`)
- Enable pgvector: `fly mpg databases extensions enable vector -c <cluster> -d fly-db`
- Enable citext (required by migration 020): `fly mpg databases extensions enable citext -c <cluster> -d fly-db`
- MPG users: `healthtracker-ro` (reader), `healthtracker-app` (writer)
- Set `FLY_MPG_SKIP_ROLE_DDL=1` — roles provisioned via `fly mpg users create`
- **Pi dump restore:** run `alembic upgrade head` as `fly-user` (schema_admin), not `healthtracker-app` — writer lacks CREATE on `public` after pg_restore. Then `GRANT ALL ON ALL TABLES IN SCHEMA public TO "healthtracker-app"` (quote hyphenated role names) and switch `DATABASE_URL` back to writer.
- **MCP app:** needs both `MCP_READONLY_DATABASE_URL` and `DATABASE_URL` (copy reader URL or attach twice).

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

Re-point DNS/tunnels to Pi. Keep MPG/Tigris as staging until re-verified. Do not delete Pi data or backups until signed off.
