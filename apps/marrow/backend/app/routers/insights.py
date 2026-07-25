from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies.insights import get_insights_service
from app.middleware.auth import get_current_session
from app.schemas.insights import TreatmentResponseList, TrendsResponse
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


@router.get("/treatment-response", response_model=TreatmentResponseList)
async def get_treatment_response(
    outcome: str = Query(...),
    service: InsightsService = Depends(get_insights_service),
) -> TreatmentResponseList:
    return await service.compute_treatment_response(outcome)
