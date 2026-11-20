# Railway environment variables (marrow)

Marrow runs in the Railway project **Marrow** from images CI builds on `main`. Service names, start commands, health path and the migration command live in the deploy blocks of `apps/marrow/backend/project.json` and `apps/marrow/frontend/project.json`; `.github/deploy/deploy.mjs` sends them with every Release ([the deploy page](../../../../.github/deploy/README.md)). There are no Railway config files in the repo. Variables below stay in Railway. Canonical decisions: [`docs/adr/README.md`](../../../../docs/adr/README.md).

## Services

| Service | Project (image) | Public domain | Port var |
|---------|-----------------|---------------|----------|
| `marrow-api` | `marrow-backend` | yes | `PORT=8000` |
| `marrow-worker` | `marrow-backend` | no | — |
| `marrow-mcp` | `marrow-backend` | yes | `PORT=8005` |
| `marrow-frontend` | `marrow-frontend` | yes | `PORT=3000` |

`marrow-api` runs the migration (`alembic upgrade head` as `MIGRATION_DATABASE_URL`) as its pre-deploy command, so it is released first.

## Reference variables

After Postgres (pgvector), Redis, and Bucket `photos` exist:

| App env | Value |
|---------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://healthtracker_app:...@${{Postgres.RAILWAY_PRIVATE_DOMAIN}}:5432/railway` (or rewrite `${{Postgres.DATABASE_URL}}` to asyncpg + app role) |
| `MIGRATION_DATABASE_URL` | htmigrate (or Postgres owner) URL for alembic pre-deploy |
| `MCP_READONLY_DATABASE_URL` | `healthtracker_ro` URL (MCP only) |
| `OPENROUTER_API_KEY` | Same as API (`${{marrow-api.OPENROUTER_API_KEY}}` on `marrow-mcp`) — required for MCP `search` embeddings |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` on API, worker, **and** `marrow-mcp`. MCP meal writes call `invalidate_user_insights_cache`. Without Redis, the API keeps serving the cached day (check-in still says there are no food photos) until `cache_ttl_entry_seconds`. |
| `BUCKET_NAME` | `${{photos.BUCKET}}` on API, worker, **and** `marrow-mcp` |
| `AWS_ACCESS_KEY_ID` | `${{photos.ACCESS_KEY_ID}}` on API, worker, **and** `marrow-mcp` |
| `AWS_SECRET_ACCESS_KEY` | `${{photos.SECRET_ACCESS_KEY}}` on API, worker, **and** `marrow-mcp` |
| `AWS_ENDPOINT_URL_S3` | `${{photos.ENDPOINT}}` on API, worker, **and** `marrow-mcp` |
| `AWS_REGION` | `${{photos.REGION}}` on API, worker, **and** `marrow-mcp` |

`marrow-mcp` must use the same `photos` bucket as `marrow-api`. Meal bytes are
served only by the API (`/photos/{id}/file` and `/thumb`). If the MCP service
has no bucket credentials it writes the JPEG to container-local `PHOTO_DIR`,
the API 404s, and the check-in tile falls back to the bowl icon. On Railway,
`log_meal` / `attach_meal_photo` refuse that write instead of reporting
`has_photo: true` for a file the API cannot read. Rows already saved that way
are not repaired by a migration: the object is not in the bucket. Attach the
image again after the bucket variables are set.

`f0rge_db.resolve_database_url` already rewrites `postgres://` / `postgresql://`
to `postgresql+asyncpg://`.

## Managed secret inventory

`JWT_SECRET`, `SETTINGS_ENCRYPTION_KEY`, `HEALTHTRACKER_APP_PASSWORD`,
`HEALTHTRACKER_RO_PASSWORD`, `OPENROUTER_API_KEY`, `HEALTH_IMPORT_TOKEN`,
APNS keys, `DEFAULT_STORAGE_USER_ID`, optional `SENTRY_DSN`. Keep existing values in the approved secret store; changes require an authorized operations task.
`OPENWEATHERMAP_API_KEY` is unused (weather is Open-Meteo, no key).
`OPENWEATHERMAP_CITY` still sets the geocode city (default Luxembourg).

## Non-secret env

| Key | Notes |
|-----|-------|
| `CORS_ORIGINS` | JSON list of frontend origins |
| `PHOTO_DIR` | `/app/photos` |
| `DIETARY_DATA_DIR` | `/app/data-seed` |
| `MCP_SERVER_HOST` / `MCP_SERVER_PORT` | `0.0.0.0` / `8005` |
| `API_URL` (frontend **build arg**) | Public API URL for Next rewrites; set in `marrow-frontend`'s deploy block (`build.args`), not in Railway |
| `SKIP_DATABASE_ROLE_DDL` | Set `1` after running `scripts/railway_bootstrap_roles.sql` (roles already exist) |
| `FOOD_ANALYSIS_VIA_AIRFLOW` | `true` to enqueue meal classify on Pi Airflow instead of BackgroundTasks |
| `AIRFLOW_URL` | `https://airflow.leo-figueiredo.com` (same UI for both envs) |
| `AIRFLOW_USERNAME` / `AIRFLOW_PASSWORD` | FAB user used to mint `/auth/token` |
| `AIRFLOW_SERVICE_TOKEN` | Bearer for Airflow worker → this env's `/api/v1/internal/airflow/*` (generate a distinct token per Railway env) |
| `AIRFLOW_CLASSIFY_DAG_ID` | `marrow_classify_meal_prod` on production |

## Domains

| Surface | Frontend | API | MCP |
|---------|----------|-----|-----|
| Interim Railway | `marrow-frontend-production.up.railway.app` | `marrow-api-production.up.railway.app` | `marrow-mcp-production.up.railway.app` |
| Production DNS | `marrow-health.com` | `api.marrow-health.com` | `mcp.marrow-health.com` |

Bootstrap: [`scripts/railway_bootstrap_roles.sql`](../scripts/railway_bootstrap_roles.sql) and bucket sync runbooks under `scripts/`.
