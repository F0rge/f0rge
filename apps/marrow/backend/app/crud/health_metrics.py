from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.health_metrics import HealthMetric
from f0rge_db.tenant import owned_by_user


class HealthMetricsCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_date_owned(self, date: datetime.date) -> Optional[HealthMetric]:
        stmt = select(HealthMetric).where(
            owned_by_user(HealthMetric.user_id), HealthMetric.date == date
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_date(self, date: datetime.date) -> Optional[HealthMetric]:
        return await self.get_by_date_owned(date)

    async def list_in_range(self, start: datetime.date, end: datetime.date) -> list[HealthMetric]:
        stmt = (
            select(HealthMetric)
            .where(
                owned_by_user(HealthMetric.user_id),
                HealthMetric.date.between(start, end),
            )
            .order_by(HealthMetric.date.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())
