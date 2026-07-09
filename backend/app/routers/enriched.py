from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends

from app.dependencies.enriched import get_enriched_service
from app.middleware.auth import get_current_session
from app.schemas.enriched import EnrichedDayResponse
from app.services.enriched import EnrichedService

router = APIRouter(
    prefix="/api/v1/enriched",
    tags=["enriched"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/{date}", response_model=EnrichedDayResponse)
async def get_enriched_day_endpoint(
    date: datetime.date,
    service: EnrichedService = Depends(get_enriched_service),
):
    return await service.get_enriched_day(date)
