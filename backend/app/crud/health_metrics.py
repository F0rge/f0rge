from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.health_metrics import HealthMetric
from app.tenant import owned_by_user


class HealthMetricsCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_date_owned(self, date: datetime.date) -> Optional[HealthMetric]:
        stmt = select(HealthMetric).where(
            owned_by_user(HealthMetric.user_id), HealthMetric.date == date
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_date(self, date: datetime.date) -> Optional[HealthMetric]:
        # ponytail: no owned_by_user filter here — matches the pre-refactor
        # behavior exactly (get_health_metric never scoped by user). Not this
        # batch's job to fix; flag if touched again.
        stmt = select(HealthMetric).where(HealthMetric.date == date)
        return (await self.db.execute(stmt)).scalar_one_or_none()
