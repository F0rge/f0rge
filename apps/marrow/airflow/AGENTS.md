# Marrow Airflow — meal analysis DAG

Airflow 3 LocalExecutor stack that runs `meal_analysis` (extract → enrich → gate → persist) by calling Marrow internal stage APIs.

## Boot

```bash
cd apps/marrow/airflow
cp .env.example .env   # set MEAL_ANALYSIS_INTERNAL_TOKEN (same as Marrow)
docker compose up --build
```

| Surface | URL |
|---------|-----|
| Airflow UI | http://localhost:8080 (`airflow` / `airflow`) |
| Pi overlay | http://\<tailscale-ip\>:8083 (`docker compose -f docker-compose.yml -f docker-compose.pi.yml up -d`) |

## Marrow wiring

On the API (`.env` / Fly secrets):

```
AIRFLOW_API_URL=http://localhost:8080
AIRFLOW_USERNAME=airflow
AIRFLOW_PASSWORD=airflow
MEAL_ANALYSIS_DAG_ID=meal_analysis
MEAL_ANALYSIS_INTERNAL_TOKEN=<same as Airflow .env>
```

Local without Airflow: `MEAL_ANALYSIS_INLINE=true` runs the staged pipeline in-process.

## Trigger

Photo upload / analysis retry → Marrow `AirflowClient.trigger_meal_analysis` → `POST /api/v2/dags/meal_analysis/dagRuns` with conf `{photo_id, user_id}`.

## Auth note

Airflow 3 API needs JWT from `POST /auth/token` (not basic auth on `/api/v2`).
