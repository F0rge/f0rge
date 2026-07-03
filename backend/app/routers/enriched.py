from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.enriched import EnrichedDayResponse
from app.services.enriched import get_enriched_day

router = APIRouter(
    prefix="/api/v1/enriched",
    tags=["enriched"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/{date}", response_model=EnrichedDayResponse)
async def get_enriched_day_endpoint(date: datetime.date, db: AsyncSession = Depends(get_db)):
    return await get_enriched_day(db, date)
