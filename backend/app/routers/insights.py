from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.insights import (
    CorrelatesResponse,
    SleepNextDayResponse,
    TreatmentResponseList,
    TrendsResponse,
)
from app.services import insights as insights_service

router = APIRouter(
    prefix="/api/v1/insights",
    tags=["insights"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> TrendsResponse:
    return await insights_service.compute_trends(db, start, end)


@router.get("/correlates", response_model=CorrelatesResponse)
async def get_correlates(
    outcome: str = Query(...),
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    category: Optional[str] = Query(default=None),
    min_n: int = Query(default=10, ge=3, le=365),
    db: AsyncSession = Depends(get_db),
) -> CorrelatesResponse:
    return await insights_service.compute_correlates(db, start, end, outcome, category, min_n)


@router.get("/treatment-response", response_model=TreatmentResponseList)
async def get_treatment_response(
    outcome: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> TreatmentResponseList:
    return await insights_service.compute_treatment_response(db, outcome)


@router.get("/sleep-next-day", response_model=SleepNextDayResponse)
async def get_sleep_next_day(
    outcome: str = Query(...),
    metric: str = Query(...),
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> SleepNextDayResponse:
    return await insights_service.compute_sleep_next_day(db, start, end, outcome, metric)
