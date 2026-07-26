from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.meal_analysis_queue import MealAnalysisQueue

logger = logging.getLogger(__name__)

LISTEN_CHANNEL = "meal_analysis_queue"


async def enqueue_meal_analysis(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    meal_id: int,
    photo_id: int,
) -> None:
    """Insert or refresh a queue row for this meal and notify the worker.

    Unique on meal_id: a retry resets attempts/error and re-wakes the worker.

    Commits the current session so any flushed pending ``PhotoAnalysis`` in the
    same session is persisted atomically with the queue row.
    """
    stmt = (
        pg_insert(MealAnalysisQueue)
        .values(
            user_id=user_id,
            meal_id=meal_id,
            photo_id=photo_id,
            attempts=0,
            last_attempt_at=None,
            last_error=None,
            stage=None,
        )
        .on_conflict_do_update(
            constraint="uq_meal_analysis_queue_meal_id",
            set_={
                "photo_id": photo_id,
                "user_id": user_id,
                "attempts": 0,
                "last_attempt_at": None,
                "last_error": None,
                "stage": None,
                "enqueued_at": func.now(),
            },
        )
    )
    await db.execute(stmt)
    await db.execute(text("SELECT pg_notify(:channel, 'wake')"), {"channel": LISTEN_CHANNEL})
    await db.commit()
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
