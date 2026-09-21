from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.books_period import BooksPeriod, BooksPeriodStatus
from f0rge_db.crud import BaseCRUD


class BooksPeriodCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, period_id: uuid.UUID) -> Optional[BooksPeriod]:
        return (
            await self.db.execute(select(BooksPeriod).where(BooksPeriod.id == period_id))
        ).scalar_one_or_none()

    async def list_all(self) -> list[BooksPeriod]:
        result = await self.db.execute(
            select(BooksPeriod).order_by(
                BooksPeriod.period_from.desc(),
                BooksPeriod.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def find_overlapping(
        self, period_from: datetime.date, period_to: datetime.date
    ) -> Optional[BooksPeriod]:
        result = await self.db.execute(
            select(BooksPeriod)
            .where(
                BooksPeriod.period_from <= period_to,
                BooksPeriod.period_to >= period_from,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def find_locked_covering(self, target_date: datetime.date) -> Optional[BooksPeriod]:
        result = await self.db.execute(
            select(BooksPeriod)
            .where(
                BooksPeriod.status == BooksPeriodStatus.LOCKED,
                BooksPeriod.period_from <= target_date,
                BooksPeriod.period_to >= target_date,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()
