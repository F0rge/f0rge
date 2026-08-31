# Railway environment variables (marrow)

Shared monorepo services. Do **not** set Root Directory. Point each service's
Config File at the matching `railway*.toml`.

## Service → config

| Service | Config path | Public domain | Port var |
|---------|-------------|---------------|----------|
| `marrow-api` | `apps/marrow/backend/railway.toml` | yes | `PORT=8000` |
| `marrow-worker` | `apps/marrow/backend/railway.worker.toml` | no | — |
| `marrow-mcp` | `apps/marrow/backend/railway.mcp.toml` | yes | `PORT=8005` |
| `marrow-frontend` | `apps/marrow/frontend/railway.toml` | yes | `PORT=3000` |

## Reference variables

After Postgres (pgvector), Redis, and Bucket `photos` exist:

| App env | Value |
|---------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://healthtracker_app:...@${{Postgres.RAILWAY_PRIVATE_DOMAIN}}:5432/railway` (or rewrite `${{Postgres.DATABASE_URL}}` to asyncpg + app role) |
| `MIGRATION_DATABASE_URL` | htmigrate (or Postgres owner) URL for alembic pre-deploy |
| `MCP_READONLY_DATABASE_URL` | `healthtracker_ro` URL (MCP only) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` (API + worker) |
| `BUCKET_NAME` | `${{photos.BUCKET}}` |
| `AWS_ACCESS_KEY_ID` | `${{photos.ACCESS_KEY_ID}}` |
| `AWS_SECRET_ACCESS_KEY` | `${{photos.SECRET_ACCESS_KEY}}` |
| `AWS_ENDPOINT_URL_S3` | `${{photos.ENDPOINT}}` |
| `AWS_REGION` | `${{photos.REGION}}` |

`f0rge_db.resolve_database_url` already rewrites `postgres://` / `postgresql://`
to `postgresql+asyncpg://`.

## Secrets to copy from Fly

`JWT_SECRET`, `SETTINGS_ENCRYPTION_KEY`, `HEALTHTRACKER_APP_PASSWORD`,
`HEALTHTRACKER_RO_PASSWORD`, `OPENROUTER_API_KEY`, `HEALTH_IMPORT_TOKEN`,
APNS keys, `DEFAULT_STORAGE_USER_ID`, optional `SENTRY_DSN`.
`OPENWEATHERMAP_API_KEY` is unused (weather is Open-Meteo, no key).
`OPENWEATHERMAP_CITY` still sets the geocode city (default Luxembourg).

## Non-secret env

| Key | Notes |
|-----|-------|
| `CORS_ORIGINS` | JSON list of frontend origins |
| `PHOTO_DIR` | `/app/photos` |
| `DIETARY_DATA_DIR` | `/app/data-seed` |
| `MCP_SERVER_HOST` / `MCP_SERVER_PORT` | `0.0.0.0` / `8005` |
| `API_URL` (frontend **build arg**) | Public API URL for Next rewrites |
| `FLY_MPG_SKIP_ROLE_DDL` | Set `1` after running `scripts/railway_bootstrap_roles.sql` (roles already exist) |
| `FOOD_ANALYSIS_VIA_AIRFLOW` | `true` to enqueue meal classify on Pi Airflow instead of BackgroundTasks |
| `AIRFLOW_URL` | `https://airflow.leo-figueiredo.com` (same UI for both envs) |
| `AIRFLOW_USERNAME` / `AIRFLOW_PASSWORD` | FAB user used to mint `/auth/token` |
| `AIRFLOW_SERVICE_TOKEN` | Bearer for Airflow worker → this env's `/api/v1/internal/airflow/*` (generate a distinct token per Railway env) |
| `AIRFLOW_CLASSIFY_DAG_ID` | develop: `marrow_classify_meal_dev`; production: `marrow_classify_meal_prod` |

## Domains (cutover)

| Env | Frontend | API | MCP |
|-----|----------|-----|-----|
| Interim Railway | `marrow-frontend-production.up.railway.app` | `marrow-api-production.up.railway.app` | `marrow-mcp-production.up.railway.app` |
| Production DNS | `marrow-health.com` | `api.marrow-health.com` | `mcp.marrow-health.com` |
| Develop DNS | `app-dev.marrow-health.com` | `api-dev.marrow-health.com` | `mcp-dev.marrow-health.com` |

## Blockers on Free plan

Postgres (pgvector), Bucket, and `develop` environment duplication require a
paid Railway plan (Hobby+). Upgrade, then:

```bash
railway deploy --template 3jJFCA          # or pgvector-pg18
railway bucket create photos --region ams
railway environment new develop --duplicate production
# Point develop services at branch develop
```

Then run [`scripts/railway_bootstrap_roles.sql`](../scripts/railway_bootstrap_roles.sql)
and the dump/restore + bucket sync runbooks under `scripts/`.
