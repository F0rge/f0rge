from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user_id, get_home_service
from app.schemas.home import HomeSummaryResponse
from app.services.home import HomeService

home_router = APIRouter(prefix="/api/v1/home", tags=["home"])


@home_router.get("", response_model=HomeSummaryResponse)
async def home_summary(
    _: uuid.UUID = Depends(get_current_user_id),
    service: HomeService = Depends(get_home_service),
) -> HomeSummaryResponse:
    return await service.summary()
