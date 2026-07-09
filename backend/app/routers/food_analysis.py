from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.dependencies.food_analysis import get_food_analysis_service
from app.middleware.auth import get_current_session
from app.schemas.food_analysis import (
    DietaryConfirmUpdate,
    IngredientCreate,
    IngredientResponse,
    IngredientUpdate,
    PhotoAnalysisResponse,
)
from app.services.food_analysis import FoodAnalysisService

router = APIRouter(
    prefix="/api/v1",
    tags=["food-analysis"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/photos/{photo_id}/analysis", response_model=PhotoAnalysisResponse)
async def get_analysis(
    photo_id: int,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> PhotoAnalysisResponse:
    return await service.get_analysis_or_404(photo_id)


@router.put("/photos/{photo_id}/analysis/confirm", response_model=PhotoAnalysisResponse)
async def confirm_analysis(
    photo_id: int,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> PhotoAnalysisResponse:
    return await service.confirm_analysis_by_photo_id(photo_id)


@router.put("/photos/{photo_id}/analysis/dietary-confirm", response_model=PhotoAnalysisResponse)
async def set_dietary_confirmations(
    photo_id: int,
    body: DietaryConfirmUpdate,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> PhotoAnalysisResponse:
    return await service.set_dietary_confirmations(photo_id, body)


@router.put(
    "/photos/{photo_id}/analysis/retry",
    response_model=PhotoAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_analysis(
    photo_id: int,
    background_tasks: BackgroundTasks,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> PhotoAnalysisResponse:
    return await service.retry_analysis(photo_id, background_tasks)


@router.put("/ingredients/{ingredient_id}", response_model=IngredientResponse)
async def update_ingredient(
    ingredient_id: int,
    body: IngredientUpdate,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> IngredientResponse:
    return await service.update_ingredient(ingredient_id, body)


@router.post(
    "/photos/{photo_id}/analysis/ingredients",
    response_model=IngredientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_ingredient(
    photo_id: int,
    body: IngredientCreate,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> IngredientResponse:
    return await service.add_ingredient_to_photo(photo_id, body)


@router.delete("/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ingredient(
    ingredient_id: int,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> None:
    await service.delete_ingredient(ingredient_id)
