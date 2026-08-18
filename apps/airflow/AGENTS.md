# Airflow — Agent Instructions

Shared **Airflow 3** control plane for f0rge apps. Deployed on **rpi** via standalone Docker Compose (not Coolify, not Railway).

CeleryExecutor + Redis. DAGs come from GitHub via **GitDagBundle** (not host bind mounts). Apps trigger DAGs over the Airflow REST API.

## Layout

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | postgres 16 + redis + api-server + scheduler + dag-processor + celery worker + flower |
| `Dockerfile` | `apache/airflow:3.1.7` + `requirements.txt` (`common-ai[openai]==0.7`, `amazon[s3fs]`, git) |
| `dags/_system/smoke.py` | `airflow_smoke` system DAG (bundle `airflow`) |
| `scripts/status.sh` | Stack health: compose ps, stats, redis, celery ping, API |
| `scripts/scale-workers.sh` | Scale celery workers `1\|2\|3` |
| `apps/marrow/dags` | Marrow-owned DAGs (`marrow_*`) — GitDagBundles `marrow_dev` (@ develop) and `marrow_prod` (@ main) |
| `apps/dk/dags` | dk-owned DAGs (`dk_*`) — GitDagBundle `dk` |

## Boot (rpi)

```bash
cd ~/development/f0rge/apps/airflow
cp .env.example .env                  # strong passwords + Fernet + JWT secret
# AIRFLOW__API_AUTH__JWT_SECRET must be set (openssl rand -hex 32)
export AIRFLOW_UID=1000
docker compose -p airflow up -d --build
# Default: 1 celery worker. Scale when needed:
./scripts/scale-workers.sh 2          # or 1 / 3
```

| Service | URL |
|---------|-----|
| UI / API (public) | https://airflow.leo-figueiredo.com |
| UI / API (on Pi) | http://127.0.0.1:8082 |
| UI / API (Tailscale) | http://100.103.61.77:8082 |
| Flower (Tailscale) | http://100.103.61.77:5555 |

Public URL is routed via **file-mode** cloudflared ingress on tunnel `6c58d6b1-ad4d-4df9-8249-0e2bb88a9c01` → `http://127.0.0.1:8082` (no Cloudflare Access; FAB login only). Flower is **not** on Cloudflare — Tailscale/loopback only.

Postgres and Redis have **no** host ports. Do **not** attach this stack to Coolify webhooks (Coolify `--force-recreate`s entire compose projects).

A plain `docker compose up -d` resets workers to **1** unless you pass `--scale airflow-worker=N` (or use `scale-workers.sh`).

## How a new DAG appears

1. Merge DAG Python under `apps/<app>/dags/` with the right `dag_id` prefix.
2. dag-processor GitDagBundle fetches `https://github.com/F0rge/f0rge.git` about every **60s**.
3. Four bundles, same repo, different `subdir` / `tracking_ref`: `airflow` → `apps/airflow/dags` @ `develop`, `marrow_dev` → `apps/marrow/dags` @ `develop`, `marrow_prod` → `apps/marrow/dags` @ `main`, `dk` → `apps/dk/dags` @ `develop`.
4. Meal classify `dag_id`s must differ (`marrow_classify_meal_dev` vs `_prod`) so both clones can load. Env (S3 conn + Marrow URL/token) is derived from the clone path, not a process env var.
5. Repo is **public** — no deploy key / PAT. If it becomes private, add an Airflow `git` connection (`AIRFLOW_CONN_GIT_DEFAULT`) and `git_conn_id` on each bundle.

No `git pull` on the Pi for DAGs. Compose/env changes still need a copy onto the Pi (rsync or a real clone of the control-plane tree).

## DAG ownership

- Platform owns the runtime; apps own DAG Python under `apps/<app>/dags/`.
- `dag_id` **must** be prefixed: `airflow_*`, `marrow_*`, `dk_*`.
- Extra providers (OpenRouter, common-ai, …) belong in a **follow-up image layer** only when a consumer DAG needs them — not in the base platform image.

## Consumption contract (no client lib yet)

Airflow 3 public API uses JWT (not basic auth on `/api/v2`).

```bash
AIRFLOW_URL=https://airflow.leo-figueiredo.com

TOKEN=$(curl -sS -X POST "$AIRFLOW_URL/auth/token" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$AIRFLOW_USER\",\"password\":\"$AIRFLOW_PASSWORD\"}" \
  | jq -r .access_token)

# Trigger
curl -sS -X POST "$AIRFLOW_URL/api/v2/dags/airflow_smoke/dagRuns" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"logical_date": null, "conf": {}}'

# Poll
curl -sS "$AIRFLOW_URL/api/v2/dags/airflow_smoke/dagRuns/<dag_run_id>" \
  -H "Authorization: Bearer $TOKEN"
```

**Reachability:** public `https://airflow.leo-figueiredo.com`, Tailscale, and processes on the Pi. Marrow on Railway **cannot** reach the Pi privately without a separate auth/routing decision (e.g. Cloudflare Access or a proxy).

## Monitor the stack

```bash
cd ~/development/f0rge/apps/airflow
./scripts/status.sh
```

Celery only:

```bash
CELERY_APP=airflow.providers.celery.executors.celery_executor.app
docker compose -p airflow exec airflow-worker \
  celery --app "$CELERY_APP" inspect ping
docker compose -p airflow exec airflow-worker \
  celery --app "$CELERY_APP" inspect active
docker compose -p airflow logs -f --tail=50 airflow-worker
```

`inspect ping` lists every live worker (`celery@<hostname>`). After `./scripts/scale-workers.sh 3` you should see three pongs. Flower UI shows the same: http://100.103.61.77:5555

Airflow UI task instances show the worker hostname that ran them.

## Gotchas

- Set `AIRFLOW__API_AUTH__JWT_SECRET` explicitly. Without it each process auto-generates a different key and tasks fail with `Invalid auth token: Signature verification failed`.
- Airflow 3 public API needs JWT from `POST /auth/token` (not basic auth on `/api/v2`).
- DAG imports: use `from airflow.sdk import dag, task` on 3.0.3 base image (not `airflow.providers.common.compat.sdk` — that needs extra providers).
- Do not put this under Coolify; webhook redeploys would bounce the scheduler.
- Setting `dag_bundle_config_list` **replaces** the default LocalDagBundle. After cutover from LocalExecutor, retarget leftover `dag_version.bundle_name = 'dags-folder'` rows (and delete the inactive `dag_bundle` row). Otherwise `/ui/dags/recent_dag_runs` 500s with `Requested bundle 'dags-folder' is not configured` and the UI shows "Importing a module script failed."
- `apache-airflow-providers-git` 0.0.4 (what 3.0.3 ships) has no `sparse_dirs`; each bundle clones the repo. f0rge is ~4 MB — fine. Do not bump the git provider to 0.4.x on this image (`common-compat` 1.7.2 vs ≥1.15).
- `AIRFLOW__DAG_PROCESSOR__DAG_BUNDLE_STORAGE_PATH=/opt/airflow/dag_bundles` — default `/tmp` ignores the named volume. Fresh `dag-bundles` volume is root-owned; `airflow-init` chowns it to `AIRFLOW_UID:0`.
- Pi has 8 GB RAM and many containers. Default **1** worker. Scale to 2–3 only when needed; scale back after.
- Redis is dedicated to this compose project — do not reuse Coolify Redis.

## Out of scope

- Chat API/UI, Monty, Jaeger
- `health_brief` / OpenRouter (marrow consumer later)
- Helm, Railway, Coolify, triggerer
- `libs/backend/airflow` HTTP wrapper
- Public Flower hostname
