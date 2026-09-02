from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.nia import NiaThread, NiaUsageEvent
from f0rge_db.crud import BaseCRUD


def utc_month_start_naive() -> datetime.datetime:
    now = datetime.datetime.utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class NiaThreadCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_owned(
        self,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[NiaThread]:
        return (
            await self.db.execute(
                select(NiaThread)
                .options(selectinload(NiaThread.messages))
                .where(
                    NiaThread.id == thread_id,
                    NiaThread.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

    async def list_active_for_user(self, user_id: uuid.UUID) -> list[NiaThread]:
        result = await self.db.execute(
            select(NiaThread)
            .where(
                NiaThread.user_id == user_id,
                NiaThread.archived_at.is_(None),
            )
            .order_by(NiaThread.created_at.desc())
        )
        return list(result.scalars().all())


class NiaUsageEventCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def sum_total_tokens_for_user(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.sum(NiaUsageEvent.total_tokens), 0)).where(
                NiaUsageEvent.user_id == user_id
            )
        )
        return int(result.scalar_one())

    async def sum_total_tokens_for_user_current_utc_month(self, user_id: uuid.UUID) -> int:
        period_start = utc_month_start_naive()
        result = await self.db.execute(
            select(func.coalesce(func.sum(NiaUsageEvent.total_tokens), 0)).where(
                NiaUsageEvent.user_id == user_id,
                NiaUsageEvent.created_at >= period_start,
            )
        )
        return int(result.scalar_one())
