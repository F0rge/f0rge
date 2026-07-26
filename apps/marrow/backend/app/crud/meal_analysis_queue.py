from __future__ import annotations

import uuid

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.meal_analysis_queue import MealAnalysisQueue

LISTEN_CHANNEL = "meal_analysis_queue"


class MealAnalysisQueueCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def upsert_pending(
        self,
        *,
        user_id: uuid.UUID,
        meal_id: int,
        photo_id: int,
    ) -> None:
        """Insert or refresh a queue row and NOTIFY the worker (no commit)."""
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
        await self.db.execute(stmt)
        await self.db.execute(
            text("SELECT pg_notify(:channel, 'wake')"),
            {"channel": LISTEN_CHANNEL},
        )
