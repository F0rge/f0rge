from __future__ import annotations

from datetime import datetime, timezone

from airflow.sdk import dag, task


@dag(
    dag_id="airflow_smoke",
    schedule=None,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    tags=["airflow", "system", "smoke"],
)
def airflow_smoke() -> None:
    @task
    def ping() -> dict[str, str]:
        return {"ok": "true", "message": "f0rge airflow control plane"}

    ping()


airflow_smoke()
