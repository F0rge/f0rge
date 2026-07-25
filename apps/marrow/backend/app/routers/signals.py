from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query

from app.dependencies.signals import get_signals_service
from app.middleware.auth import get_current_session
from app.schemas.signals import SignalsResponse
from app.services.signals.service import SignalsService

router = APIRouter(
    prefix="/api/v1/signals",
    tags=["signals"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=SignalsResponse)
async def get_signals(
    outcome: str = Query(...),
    start: datetime.date | None = Query(default=None),
    end: datetime.date | None = Query(default=None),
    service: SignalsService = Depends(get_signals_service),
) -> SignalsResponse:
    return await service.compute(outcome, start, end)
