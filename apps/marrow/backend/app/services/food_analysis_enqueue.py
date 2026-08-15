from __future__ import annotations

import logging
import uuid

from fastapi import BackgroundTasks

from app.config import settings

logger = logging.getLogger(__name__)


async def enqueue_food_analysis(
    photo_id: int,
    user_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    *,
    orchestrator_run,
) -> None:
    """Enqueue meal vision via Airflow DAG or FastAPI BackgroundTasks.

    Prefer Airflow when FOOD_ANALYSIS_VIA_AIRFLOW is on and AIRFLOW_URL is set.
    On Airflow trigger failure, fall back to the in-process orchestrator so uploads
    still get analyzed.
    """
    if settings.food_analysis_via_airflow and settings.airflow_url:
        try:
            from app.services.airflow_meal_analysis import trigger_classify_meal_dag

            dag_run_id = await trigger_classify_meal_dag(photo_id, user_id)
            logger.info(
                "Enqueued marrow_classify_meal for photo %s (dag_run_id=%s)",
                photo_id,
                dag_run_id,
            )
            return
        except Exception:
            logger.exception(
                "Airflow enqueue failed for photo %s; falling back to BackgroundTasks",
                photo_id,
            )

    background_tasks.add_task(orchestrator_run, photo_id, user_id)
