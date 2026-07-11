# Fly org migration: personal → f0rge

Migrate all Marrow Fly resources from the `personal` org to a new `f0rge` org. Modeled on [fly-cutover-runbook.md](fly-cutover-runbook.md) and `scripts/fly-mpg-*.sh`.

**Constraint:** MPG clusters and Tigris buckets cannot move between orgs. This is create-new + copy + cutover, not `fly move` for data plane resources.

## Current state (personal org)

| Resource | ID / name | Notes |
|---|---|---|
| MPG cluster | `marrow-db-prod` (`d1zj5omzqwvryqkv`, `fra`) | DBs: `marrow`, `marrow_dev` |
| API (prod) | `marrow` | |
| API (dev) | `marrow-dev` | |
| MCP (prod) | `marrow-mcp` | |
| MCP (dev) | `marrow-mcp-dev` | |
| Frontend (prod) | `marrow-ui` | |
| Frontend (dev) | `marrow-ui-dev` | |
| Tigris | per-app buckets via `fly storage` | |

Apps **can** move orgs with `fly apps move` (machines, volumes, secrets, certs/domains).

## Target state (f0rge org)

| Resource | Name / ID |
|---|---|
| Org | `f0rge` |
| MPG cluster | `marrow-db` (`nlkxjo5m3240y93v`, `fra`, Basic 10GB) |
| Databases | `marrow`, `marrow_dev` |
| Dev apps (migrated) | `marrow-dev`, `marrow-mcp-dev`, `marrow-ui-dev` |
| Dev Tigris | `f0rge-marrow-dev-photos` |
| Prod apps (migrated) | `marrow`, `marrow-mcp`, `marrow-ui` |
| Prod Tigris | `f0rge-marrow-prod-photos` |

### Dev cutover status (2026-07-11)

- [x] `f0rge` org + billing
- [x] New MPG cluster + extensions (`vector`, `citext`)
- [x] `marrow_dev` data migrated from `d1zj5omzqwvryqkv` (row counts verified)
- [x] Dev apps moved to `f0rge`
- [x] MPG attach + `FLY_MPG_SKIP_ROLE_DDL=1` on API/MCP
- [x] New Tigris bucket + secrets on `marrow-dev`
- [x] `rclone copy` old bucket `empty-sea-6682` → `f0rge-marrow-dev-photos` (required — DB rows reference filenames, not bucket)
- [x] `FLY_API_TOKEN` → single `f0rge` org token (all apps in `f0rge`)
- [ ] Old cluster/bucket decommission

### Prod cutover status (2026-07-11)

- [x] `marrow` database migrated to `nlkxjo5m3240y93v` (104 entries, 148 photos, 5 users, 18 labs)
- [x] `rclone copy` `late-rain-9962` → `f0rge-marrow-prod-photos` (151 objects)
- [x] Prod apps moved to `f0rge` + MPG attach
- [x] Deployed API/MCP/frontend from `main` monorepo paths
- [ ] Old cluster/bucket decommission (after soak)

## Prerequisites

- Fly billing on `f0rge` org (dashboard)
- GitHub `FLY_API_TOKEN` with multi-token during window: `"<personal-token>,<f0rge-deploy-token>"`
- `rclone` configured for Tigris (S3-compatible)
- Local: `flyctl`, `docker` (for pg_dump via proxy scripts)

## Phase 1 — Create org + cluster

```bash
fly orgs create f0rge
# Add billing in https://fly.io/dashboard

fly mpg create --name marrow-db --org f0rge --region fra
# Size ≥ current cluster; note new cluster ID

fly mpg databases create marrow --cluster <new-cluster-id>
fly mpg databases create marrow_dev --cluster <new-cluster-id>
```

### Roles + RLS (per database)

Reuse pattern from `scripts/fly-mpg-migrate-cluster.sh`:

1. `fly mpg proxy <cluster-id>` on port 16380
2. Create users: `healthtracker-ro`, `healthtracker-app`, `htmigrate` (`schema_admin`)
3. Run RLS grants from `apps/marrow/backend/app/rls.py` table list
4. Set `FLY_MPG_SKIP_ROLE_DDL=1` on all apps

## Phase 2 — Tigris bucket sync

```bash
fly storage list -a marrow-dev    # enumerate prod + dev buckets
fly storage create -a marrow-dev --org f0rge   # new bucket in f0rge org

rclone copy old-s3:bucket new-s3:bucket --progress
rclone check old-s3:bucket new-s3:bucket
```

Record new `AWS_*` secrets for each app.

## Phase 3 — Dev cutover (rehearsal)

**Order matters.** Old cluster stays live as rollback until decommission.

```bash
# 1. Stop writes (web serves API mutations; worker only drains embeddings)
fly scale count web=0 worker=0 -a marrow-dev

# 2. Dump dev DB via OLD cluster proxy
fly mpg proxy d1zj5omzqwvryqkv -p 16380 &   # old cluster (rollback source)
pg_dump -Fc --no-owner --no-acl -h localhost -p 16380 -U <admin> marrow_dev > /tmp/marrow_dev.dump

# 3. Restore to NEW cluster (nlkxjo5m3240y93v) as schema_admin
fly mpg proxy nlkxjo5m3240y93v -p 16381 &
pg_restore -h localhost -p 16381 -U schema_admin -d marrow_dev --no-owner --no-acl /tmp/marrow_dev.dump
psql ... -c "ANALYZE;"

# 4. Row-count spot checks (entries, photos, auth_users, ...)

# 5. Move apps (minutes downtime each; DNS/certs move with app)
fly apps move marrow-dev --org f0rge
fly apps move marrow-mcp-dev --org f0rge
fly apps move marrow-ui-dev --org f0rge

# 6. Swap secrets on each app
fly secrets set DATABASE_URL=... MIGRATION_DATABASE_URL=... -a marrow-dev
fly secrets set MCP_READONLY_DATABASE_URL=... DATABASE_URL=... -a marrow-mcp-dev
fly secrets set AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... BUCKET_NAME=... -a marrow-dev

# 7. Scale API + worker back, then deploy-all
fly scale count web=1 worker=1 -a marrow-dev
gh workflow run "Fly Deploy (develop)" --ref develop
```

### Dev live gate

- [ ] `curl -sf https://api-dev.marrow-health.com/api/v1/health`
- [ ] Login on https://app-dev.marrow-health.com
- [ ] Submit check-in write
- [ ] Upload photo → object in **new** bucket
- [ ] MCP endpoint answers
- [ ] Embedding worker drains queue

## Phase 4 — Prod cutover (after ~1 week dev soak)

**Requires explicit approval** — brief write-freeze on prod.

Same recipe as dev for `marrow`, `marrow-mcp`, `marrow-ui` + database `marrow`.

## Phase 5 — Decommission (after 1–2 week prod soak)

Only after sign-off:

1. Final `pg_dump` archive of old cluster
2. `rclone check` old vs new bucket
3. Destroy old MPG cluster
4. Delete old Tigris bucket
5. `FLY_API_TOKEN` → single f0rge deploy token; revoke personal tokens
6. Update `AGENTS.md` env tables with new cluster ID + org

## Rollback

Until decommission:

```bash
fly apps move <app> --org personal
fly secrets set DATABASE_URL=<old-cluster-url> ...
```

Old cluster + bucket remain authoritative until secret swap on cutover.

## CI/CD notes

- P4 adds `workflow_dispatch` on deploy workflows — use for post-move redeploys
- Multi-token `FLY_API_TOKEN` bridges split-org window during migration
- App org membership is metadata; no fly.toml changes required
