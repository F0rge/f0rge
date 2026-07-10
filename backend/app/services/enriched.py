from __future__ import annotations

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.enriched import EnrichedCRUD
from app.schemas.enriched import EnrichedDayResponse
from app.services.weather import WeatherService


class EnrichedService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = EnrichedCRUD(db)

    async def get_enriched_day(self, date: datetime.date) -> EnrichedDayResponse:
        entry = await self.crud.get_entry_by_date(date)
        weather = await WeatherService(self.db).get_daily_summary(date)
        health = await self.crud.get_health_metric_by_date(date)
        return EnrichedDayResponse(entry=entry, weather=weather, health_metrics=health)
