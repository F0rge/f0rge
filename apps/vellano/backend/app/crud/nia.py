from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.nia import NiaScheduledRun, NiaScheduledTask, NiaThread, NiaUsageEvent
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


class NiaScheduledTaskCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_owned(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[NiaScheduledTask]:
        return (
            await self.db.execute(
                select(NiaScheduledTask).where(
                    NiaScheduledTask.id == task_id,
                    NiaScheduledTask.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[NiaScheduledTask]:
        result = await self.db.execute(
            select(NiaScheduledTask)
            .where(NiaScheduledTask.user_id == user_id)
            .order_by(NiaScheduledTask.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_enabled(self) -> list[NiaScheduledTask]:
        result = await self.db.execute(
            select(NiaScheduledTask).where(NiaScheduledTask.enabled.is_(True))
        )
        return list(result.scalars().all())

    async def count_enabled_for_user(
        self,
        user_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> int:
        query = (
            select(func.count())
            .select_from(NiaScheduledTask)
            .where(
                NiaScheduledTask.user_id == user_id,
                NiaScheduledTask.enabled.is_(True),
            )
        )
        if exclude_id is not None:
            query = query.where(NiaScheduledTask.id != exclude_id)
        result = await self.db.execute(query)
        return int(result.scalar_one())

    async def get_for_update_skip_locked(
        self,
        task_id: uuid.UUID,
    ) -> Optional[NiaScheduledTask]:
        return (
            await self.db.execute(
                select(NiaScheduledTask)
                .where(NiaScheduledTask.id == task_id)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()


class NiaScheduledRunCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def latest_for_task(self, task_id: uuid.UUID) -> Optional[NiaScheduledRun]:
        return (
            await self.db.execute(
                select(NiaScheduledRun)
                .where(NiaScheduledRun.task_id == task_id)
                .order_by(NiaScheduledRun.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()


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
