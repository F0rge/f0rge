from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies.insights import get_insights_service
from app.middleware.auth import get_current_session
from app.schemas.insights import (
    CorrelatesResponse,
    SleepNextDayResponse,
    TreatmentResponseList,
    TrendsResponse,
)
from app.services.insights import InsightsService

router = APIRouter(
    prefix="/api/v1/insights",
    tags=["insights"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    service: InsightsService = Depends(get_insights_service),
) -> TrendsResponse:
    return await service.compute_trends(start, end)


@router.get("/correlates", response_model=CorrelatesResponse)
async def get_correlates(
    outcome: str = Query(...),
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    category: Optional[str] = Query(default=None),
    min_n: int = Query(default=10, ge=3, le=365),
    service: InsightsService = Depends(get_insights_service),
) -> CorrelatesResponse:
    return await service.compute_correlates(start, end, outcome, category, min_n)


@router.get("/treatment-response", response_model=TreatmentResponseList)
async def get_treatment_response(
    outcome: str = Query(...),
    service: InsightsService = Depends(get_insights_service),
) -> TreatmentResponseList:
    return await service.compute_treatment_response(outcome)


@router.get("/sleep-next-day", response_model=SleepNextDayResponse)
async def get_sleep_next_day(
    outcome: str = Query(...),
    metric: str = Query(...),
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    service: InsightsService = Depends(get_insights_service),
) -> SleepNextDayResponse:
    return await service.compute_sleep_next_day(start, end, outcome, metric)
