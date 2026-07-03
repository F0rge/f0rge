from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.schemas.enriched import EnrichedDayResponse
from app.services.weather import get_daily_summary


async def get_enriched_day(db: AsyncSession, date: datetime.date) -> EnrichedDayResponse:
    entry = (await db.execute(select(Entry).where(Entry.date == date))).scalar_one_or_none()
    weather = await get_daily_summary(db, date)
    health = (
        await db.execute(select(HealthMetric).where(HealthMetric.date == date))
    ).scalar_one_or_none()
    return EnrichedDayResponse(entry=entry, weather=weather, health_metrics=health)
