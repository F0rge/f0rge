from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.meals import get_meal_service
from app.middleware.auth import get_current_session
from app.schemas.meal import MealCloneCreate, RecentMealResponse
from app.schemas.photo import PhotoResponse
from app.services.meals import MealService

router = APIRouter(
    prefix="/api/v1",
    tags=["meals"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/meals/recent", response_model=list[RecentMealResponse])
async def recent_meals(
    limit: int = Query(default=12, ge=1, le=50),
    service: MealService = Depends(get_meal_service),
) -> list[RecentMealResponse]:
    return await service.list_recent(limit)


@router.post(
    "/entries/{date}/meals/clone",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_meal(
    date: datetime.date,
    body: MealCloneCreate,
    service: MealService = Depends(get_meal_service),
) -> PhotoResponse:
    return await service.clone(date, body.source_photo_id, body.meal_time)
