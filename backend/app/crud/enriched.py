from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.entry import Entry
from app.models.health_metrics import HealthMetric


class EnrichedCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_entry_by_date(self, date: datetime.date) -> Optional[Entry]:
        # ponytail: no owned_by_user filter — matches pre-refactor behavior exactly.
        return (await self.db.execute(select(Entry).where(Entry.date == date))).scalar_one_or_none()

    async def get_health_metric_by_date(self, date: datetime.date) -> Optional[HealthMetric]:
        return (
            await self.db.execute(select(HealthMetric).where(HealthMetric.date == date))
        ).scalar_one_or_none()
