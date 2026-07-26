"""Per-meal analysis DAG: extract → enrich → gate → persist via Marrow internal API."""

from __future__ import annotations

import os
from typing import Any

import httpx
from airflow.exceptions import AirflowException, AirflowSkipException
from airflow.providers.common.compat.sdk import dag, task
from airflow.sdk import get_current_context

MARROW_API_URL = os.environ.get("MARROW_API_URL", "http://host.docker.internal:8000").rstrip("/")
INTERNAL_TOKEN = os.environ.get("MEAL_ANALYSIS_INTERNAL_TOKEN", "")
BASE = f"{MARROW_API_URL}/api/v1/internal/meal-analysis"


def _headers() -> dict[str, str]:
    return {
        "X-Meal-Analysis-Token": INTERNAL_TOKEN,
        "Content-Type": "application/json",
    }


def _post(path: str, payload: dict[str, Any], *, timeout: float = 120.0) -> dict[str, Any]:
    url = f"{BASE}{path}"
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=_headers())
    if response.status_code in (401, 403, 404):
        raise AirflowException(f"{path} → {response.status_code}: {response.text[:500]}")
    if response.status_code >= 400:
        raise AirflowException(f"{path} → {response.status_code}: {response.text[:500]}")
    return response.json()


@dag(
    dag_id="meal_analysis",
    schedule=None,
    catchup=False,
    tags=["marrow", "meal-analysis"],
    doc_md="Triggered by Marrow on photo upload/retry. Stages call Marrow internal HTTP APIs.",
)
def meal_analysis():
    @task
    def extract() -> dict[str, Any]:
        conf = get_current_context()["dag_run"].conf or {}
        photo_id = conf.get("photo_id")
        user_id = conf.get("user_id")
        if photo_id is None or user_id is None:
            raise AirflowException("dag_run.conf must include photo_id and user_id")

        data = _post(
            "/extract",
            {"photo_id": int(photo_id), "user_id": str(user_id)},
            timeout=180.0,
        )
        if data.get("skipped"):
            raise AirflowSkipException(data.get("skip_reason") or "extract skipped")
        return data

    @task
    def enrich(extract_result: dict[str, Any]) -> dict[str, Any]:
        data = _post(
            "/enrich",
            {
                "user_id": extract_result["user_id"],
                "vision": extract_result["vision"],
            },
        )
        return {
            **extract_result,
            "ingredients": data["ingredients"],
        }

    @task
    def gate(enriched: dict[str, Any]) -> dict[str, Any]:
        data = _post("/gate", {"vision": enriched["vision"]})
        return {**enriched, "status": data["status"]}

    @task
    def persist(gated: dict[str, Any]) -> dict[str, Any]:
        return _post(
            "/persist",
            {
                "user_id": gated["user_id"],
                "analysis_id": gated["analysis_id"],
                "photo_id": gated["photo_id"],
                "raw_content": gated["raw_content"],
                "vision": gated["vision"],
                "ingredients": gated["ingredients"],
                "status": gated["status"],
            },
        )

    persist(gate(enrich(extract())))


meal_analysis()
