# Airflow — Agent Instructions

Shared **Airflow 3** control plane for f0rge apps. Deployed on **rpi** via standalone Docker Compose (not Coolify, not Railway).

Apps trigger DAGs over the Airflow REST API when needed. There is no chat sidecar and no Jaeger in this stack.

## Layout

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | postgres 16 + api-server + scheduler + dag-processor (LocalExecutor) |
| `docker-compose.pi.yml` | Pi ports, `parallelism=2`, Tailscale/loopback bind |
| `Dockerfile` | `apache/airflow:3.0.3` (no app-specific providers) |
| `dags/_system/smoke.py` | `airflow_smoke` system DAG |
| `../marrow/dags` | Marrow-owned DAGs (`marrow_*` ids) — mounted at runtime |
| `../dk/dags` | dk-owned DAGs (`dk_*` ids) — mounted at runtime |

## Boot (local Mac)

```bash
cd apps/airflow
cp .env.example .env
# set POSTGRES_PASSWORD, _AIRFLOW_WWW_USER_PASSWORD, AIRFLOW__CORE__FERNET_KEY
export AIRFLOW_UID=$(id -u)
docker compose -p airflow up -d --build
```

| Service | URL |
|---------|-----|
| UI / API | http://localhost:8080 |
| Health | http://localhost:8080/api/v2/version |

## Boot (rpi)

```bash
cd ~/development/f0rge/apps/airflow   # real git clone, not the old loose demo tree
cp .env.example .env                  # strong passwords + Fernet + JWT secret
# AIRFLOW__API_AUTH__JWT_SECRET must be set (openssl rand -hex 32) — shared by all Airflow processes
export AIRFLOW_UID=1000
docker compose -p airflow -f docker-compose.yml -f docker-compose.pi.yml up -d --build
```

| Service | URL |
|---------|-----|
| UI / API (on Pi) | http://127.0.0.1:8082 |
| UI / API (Tailscale) | http://100.103.61.77:8082 |

Postgres has **no** host port. Do **not** attach this stack to Coolify webhooks (Coolify `--force-recreate`s entire compose projects).

## DAG ownership

- Platform owns the runtime; apps own DAG Python under `apps/<app>/dags/`.
- `dag_id` **must** be prefixed: `airflow_*`, `marrow_*`, `dk_*`.
- Extra providers (OpenRouter, common-ai, …) belong in a **follow-up image layer** only when a consumer DAG needs them — not in the base platform image.

## Consumption contract (no client lib yet)

Airflow 3 public API uses JWT (not basic auth on `/api/v2`).

```bash
AIRFLOW_URL=http://100.103.61.77:8082   # or http://localhost:8082 on the Pi

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

**Reachability today:** Mac / homelab on Tailscale, and processes on the Pi. Marrow on Railway **cannot** reach the Pi privately — exposing via Cloudflare Access is a separate decision.

## Gotchas

- Set `AIRFLOW__API_AUTH__JWT_SECRET` explicitly. Without it each process auto-generates a different key and LocalExecutor tasks fail with `Invalid auth token: Signature verification failed`.
- Airflow 3 public API needs JWT from `POST /auth/token` (not basic auth on `/api/v2`).
- DAG imports: use `from airflow.sdk import dag, task` on 3.0.3 base image (not `airflow.providers.common.compat.sdk` — that needs extra providers).
- Do not put this under Coolify; webhook redeploys would bounce the scheduler.

## Cutover from `demo-orchestrator`

1. Land this tree on the Pi git checkout of f0rge.
2. Start `airflow` compose project; smoke-trigger `airflow_smoke`.
3. `docker compose -p demo-orchestrator down` (omit `-v` until old demo DB volume is confirmed disposable).
4. Delete or archive `/home/leo/development/f0rge/apps/demo/orchestrator` loose tree once git-backed `apps/airflow` is the source of truth.

## Out of scope (this landing)

- Chat API/UI, Monty, Jaeger
- `health_brief` / OpenRouter (marrow consumer later)
- Celery, Helm, Railway, Coolify
- `libs/backend/airflow` HTTP wrapper
- Public `airflow.leo-figueiredo.com`
