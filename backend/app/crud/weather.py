from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.weather import WeatherReading


class WeatherCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_timestamp(self, timestamp: datetime.datetime) -> Optional[WeatherReading]:
        stmt = select(WeatherReading).where(WeatherReading.timestamp == timestamp)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_by_date(self, date: datetime.date) -> list[WeatherReading]:
        stmt = select(WeatherReading).where(WeatherReading.date == date)
        return list((await self.db.execute(stmt)).scalars().all())
