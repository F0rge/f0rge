from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vat201_period import Vat201Period, Vat201PeriodEvent
from f0rge_db.crud import BaseCRUD


class Vat201PeriodCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, period_id: uuid.UUID) -> Optional[Vat201Period]:
        return (
            await self.db.execute(select(Vat201Period).where(Vat201Period.id == period_id))
        ).scalar_one_or_none()

    async def list_all(self) -> list[Vat201Period]:
        result = await self.db.execute(
            select(Vat201Period).order_by(Vat201Period.period_from.desc(), Vat201Period.id.desc())
        )
        return list(result.scalars().all())

    async def find_overlapping(
        self, period_from: datetime.date, period_to: datetime.date
    ) -> Optional[Vat201Period]:
        result = await self.db.execute(
            select(Vat201Period)
            .where(
                Vat201Period.period_from <= period_to,
                Vat201Period.period_to >= period_from,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def add_event(self, event: Vat201PeriodEvent) -> None:
        await self.add_and_flush(event)
