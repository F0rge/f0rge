"""Which Marrow Airflow env this DAG file was cloned as.

GitDagBundle paths look like:
  /opt/airflow/dag_bundles/marrow_dev/versions/<sha>/apps/marrow/dags/classify_meal.py
  /opt/airflow/dag_bundles/marrow_prod/versions/<sha>/apps/marrow/dags/classify_meal.py

Do not use a process env var — dag-processor is shared across bundles.
"""

from __future__ import annotations

import os
from pathlib import Path

_PROD_BUNDLE = "marrow_prod"
_DEV_BUNDLE = "marrow_dev"


def marrow_airflow_env(dag_file: str | Path | None = None) -> str:
    """Return ``dev`` or ``prod`` from the GitDagBundle clone path."""
    path = Path(dag_file or __file__).resolve()
    parts = path.parts
    if _PROD_BUNDLE in parts:
        return "prod"
    if _DEV_BUNDLE in parts:
        return "dev"
    # Local checkout / tests (no bundle dir): develop.
    return "dev"


def classify_dag_id(env: str | None = None, dag_file: str | Path | None = None) -> str:
    resolved = env or marrow_airflow_env(dag_file)
    return f"marrow_classify_meal_{resolved}"


def photos_conn_id(env: str | None = None, dag_file: str | Path | None = None) -> str:
    resolved = env or marrow_airflow_env(dag_file)
    return f"aws_photos_{resolved}"


def marrow_api_base_url(env: str | None = None, dag_file: str | Path | None = None) -> str:
    resolved = env or marrow_airflow_env(dag_file)
    if resolved == "prod":
        keys = ("MARROW_PROD_API_BASE_URL",)
    else:
        keys = ("MARROW_DEV_API_BASE_URL", "MARROW_API_BASE_URL")
    for key in keys:
        value = (os.environ.get(key) or "").rstrip("/")
        if value:
            return value
    raise RuntimeError(
        f"Marrow API base URL is not set for env={resolved} ({' / '.join(keys)})"
    )


def marrow_service_token(env: str | None = None, dag_file: str | Path | None = None) -> str:
    resolved = env or marrow_airflow_env(dag_file)
    if resolved == "prod":
        keys = ("MARROW_PROD_AIRFLOW_SERVICE_TOKEN",)
    else:
        keys = ("MARROW_DEV_AIRFLOW_SERVICE_TOKEN", "MARROW_AIRFLOW_SERVICE_TOKEN")
    for key in keys:
        value = os.environ.get(key) or ""
        if value:
            return value
    raise RuntimeError(
        f"Marrow Airflow service token is not set for env={resolved} ({' / '.join(keys)})"
    )
