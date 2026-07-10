from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.tenant import owned_by_user


class EnrichedCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_entry_by_date(self, date: datetime.date) -> Optional[Entry]:
        stmt = select(Entry).where(owned_by_user(Entry.user_id), Entry.date == date)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_health_metric_by_date(self, date: datetime.date) -> Optional[HealthMetric]:
        stmt = select(HealthMetric).where(
            owned_by_user(HealthMetric.user_id), HealthMetric.date == date
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
