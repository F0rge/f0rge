from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.meals import get_meal_service
from app.middleware.auth import get_current_session
from app.schemas.meal import (
    MealCloneCreate,
    MealFromLibraryCreate,
    PlatformMealResponse,
    RecentMealResponse,
)
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


@router.get("/meals/library", response_model=list[PlatformMealResponse])
async def library_meals(
    q: str | None = Query(default=None),
    service: MealService = Depends(get_meal_service),
) -> list[PlatformMealResponse]:
    return await service.list_library(q=q)


@router.post(
    "/entries/{date}/meals/from-library",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def log_meal_from_library(
    date: datetime.date,
    body: MealFromLibraryCreate,
    service: MealService = Depends(get_meal_service),
) -> PhotoResponse:
    return await service.log_from_library(date, body.platform_meal_id, body.meal_time)


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
