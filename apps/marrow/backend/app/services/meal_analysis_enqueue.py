from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.base import unit_of_work
from app.crud.meal_analysis_queue import LISTEN_CHANNEL, MealAnalysisQueueCRUD

logger = logging.getLogger(__name__)

__all__ = ["LISTEN_CHANNEL", "enqueue_meal_analysis"]


async def enqueue_meal_analysis(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    meal_id: int,
    photo_id: int,
) -> None:
    """Insert or refresh a queue row for this meal and notify the worker.

    Unique on meal_id: a retry resets attempts/error and re-wakes the worker.

    Commits via ``unit_of_work`` so any flushed pending ``PhotoAnalysis`` in the
    same session is persisted atomically with the queue row.
    """
    crud = MealAnalysisQueueCRUD(db)
    async with unit_of_work(db):
        await crud.upsert_pending(user_id=user_id, meal_id=meal_id, photo_id=photo_id)
    logger.info(
        {
            "event": "meal_analysis_enqueued",
            "meal_id": meal_id,
            "photo_id": photo_id,
        }
    )

    if settings.meal_analysis_inline:
        from app.meal_analysis_pipeline.worker import process_pending_once

        await process_pending_once()
