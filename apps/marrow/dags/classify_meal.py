"""marrow_classify_meal — meal photo vision via common-ai 0.7 LLMFileAnalysisOperator.

dag_run.conf: {"photo_id": int, "user_id": "<uuid>"}

The Celery worker never imports Marrow or opens its DB. Resolve/persist go through
Marrow internal HTTP (MARROW_API_BASE_URL + MARROW_AIRFLOW_SERVICE_TOKEN).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from airflow.providers.common.ai.operators.llm_file_analysis import LLMFileAnalysisOperator
from airflow.sdk import dag, task
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured output — keep in sync with apps/marrow/backend/.../vision_prompt.py
# ---------------------------------------------------------------------------


class VisionIngredient(BaseModel):
    name: str
    visible: bool = True
    confidence: float


class VisionResult(BaseModel):
    dish_name: str
    cuisine: Optional[str] = None
    confidence: float
    ingredients: list[VisionIngredient]


SYSTEM_PROMPT = """\
You are a food identification assistant. Given a photo, you output \
structured JSON describing the dish and its ingredients.

## Process
1. Identify the dish or meal. If the photo contains multiple dishes, pick \
the most prominent one and note others in dish_name (e.g. "rice with \
grilled chicken and side salad").
2. List every ingredient you can see in the photo. Mark each as \
visible=true.
3. Infer additional ingredients that are likely present based on common \
recipes for this dish. Mark each as visible=false.
4. Assign a confidence score (0.0-1.0) to each ingredient. If you are \
unsure, set confidence below 0.5 — do not guess.
5. Assign an overall confidence score for the dish identification.

## Output format
Return ONLY a JSON object (no markdown, no commentary) matching this schema:

{
  "dish_name": "string — lowercase, concise name",
  "cuisine": "string or null — e.g. italian, japanese, mexican",
  "confidence": 0.0-1.0,
  "ingredients": [
    {"name": "ingredient", "visible": true, "confidence": 0.0-1.0}
  ]
}

## Ingredient naming rules
- Lowercase, singular form: "tomato" not "Tomatoes", "egg" not "eggs"
- Use common English names: "cilantro" not "coriander leaf"
- Be specific when visible: "red bell pepper" not just "pepper"

## Edge cases
- Non-food image: {"dish_name": "unknown", "cuisine": null, "confidence": 0, \
"ingredients": []}
- Unclear or blurry image: set confidence below 0.3 and include only what \
you can identify with reasonable certainty.
- Multiple separate dishes: describe the primary dish; mention others in \
dish_name if relevant.\
"""

CATALOG_PROMPT_ADDENDUM = """\

## User ingredient catalog
The user maintains a personal ingredient catalog below. Use it to align \
ingredient names with their tracked vocabulary.

Rules:
- When a visible or inferred ingredient plausibly matches a catalog entry, \
emit the exact canonical_name from the list in ingredients[].name.
- Treat listed aliases as recognition aids only — never emit an alias as \
the ingredient name; always output the canonical_name.
- If nothing in the catalog fits what you see, use the best free-form \
visual name (lowercase, singular) and apply normal confidence rules.

Catalog (alphabetical, canonical names):
"""

USER_PROMPT = (
    "Analyze this food photo. Return a JSON object with dish_name, "
    "cuisine, confidence, and ingredients array."
)

LLM_CONN_ID = "pydanticai_openrouter"
FILE_CONN_ID = "aws_photos"


def _marrow_base() -> str:
    base = os.environ.get("MARROW_API_BASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("MARROW_API_BASE_URL is not set on the Airflow worker")
    return base


def _marrow_token() -> str:
    token = os.environ.get("MARROW_AIRFLOW_SERVICE_TOKEN", "")
    if not token:
        raise RuntimeError("MARROW_AIRFLOW_SERVICE_TOKEN is not set on the Airflow worker")
    return token


def _marrow_request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    query: str = "",
) -> dict[str, Any]:
    url = f"{_marrow_base()}{path}"
    if query:
        url = f"{url}?{query}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {_marrow_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Marrow {method} {path} -> {exc.code}: {detail}") from exc


def _mark_failed(context: dict[str, Any]) -> None:
    """Best-effort: tell Marrow the analysis failed so UI does not stick on analyzing."""
    try:
        ti = context.get("ti")
        job = ti.xcom_pull(task_ids="resolve_job") if ti else None
        analysis_id = (job or {}).get("analysis_id")
        if not analysis_id:
            conf = (context.get("dag_run") or {}).conf or {}
            # resolve never ran — nothing to mark
            logger.warning(
                "on_failure: no analysis_id (photo_id=%s)", conf.get("photo_id")
            )
            return
        exc = context.get("exception")
        message = f"{type(exc).__name__}: {exc}" if exc else "DAG task failed"
        _marrow_request(
            "POST",
            f"/api/v1/internal/airflow/meal-analysis/{analysis_id}/fail",
            body={
                "error_message": message[:500],
                "user_id": (job or {}).get("user_id"),
            },
        )
    except Exception:
        logger.exception("on_failure: failed to notify Marrow")


@dag(
    dag_id="marrow_classify_meal",
    schedule=None,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    tags=["marrow", "meal", "vision", "common-ai"],
    on_failure_callback=_mark_failed,
)
def marrow_classify_meal() -> None:
    @task
    def resolve_job(**context: Any) -> dict[str, Any]:
        conf = context["dag_run"].conf or {}
        photo_id = conf.get("photo_id")
        user_id = conf.get("user_id")
        if photo_id is None or not user_id:
            raise ValueError("dag_run.conf requires photo_id and user_id")

        payload = _marrow_request(
            "POST",
            "/api/v1/internal/airflow/meal-analysis/resolve",
            body={"photo_id": int(photo_id), "user_id": str(user_id)},
        )
        catalog = payload.get("catalog_context") or ""
        system_prompt = SYSTEM_PROMPT
        if catalog:
            system_prompt = SYSTEM_PROMPT + CATALOG_PROMPT_ADDENDUM + catalog

        return {
            "analysis_id": payload["analysis_id"],
            "file_path": payload["file_path"],
            "system_prompt": system_prompt,
            "photo_id": int(photo_id),
            "user_id": str(user_id),
        }

    job = resolve_job()

    classify = LLMFileAnalysisOperator(
        task_id="classify",
        prompt=USER_PROMPT,
        system_prompt="{{ ti.xcom_pull(task_ids='resolve_job')['system_prompt'] }}",
        llm_conn_id=LLM_CONN_ID,
        file_path="{{ ti.xcom_pull(task_ids='resolve_job')['file_path'] }}",
        file_conn_id=FILE_CONN_ID,
        multi_modal=True,
        output_type=VisionResult,
        serialize_output=True,
        require_approval=False,
        retries=2,
        retry_delay=timedelta(seconds=45),
        max_file_size_bytes=8 * 1024 * 1024,
    )

    @task
    def persist(job_data: dict[str, Any], vision: Any) -> dict[str, Any]:
        if isinstance(vision, VisionResult):
            body = vision.model_dump()
        elif isinstance(vision, dict):
            body = vision
        else:
            body = VisionResult.model_validate(vision).model_dump()
        body["user_id"] = job_data["user_id"]

        return _marrow_request(
            "POST",
            f"/api/v1/internal/airflow/meal-analysis/{job_data['analysis_id']}/complete",
            body=body,
        )

    job >> classify
    persist(job, classify.output)


marrow_classify_meal()
