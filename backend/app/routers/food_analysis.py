from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.dependencies.food_analysis import get_food_analysis_service
from app.middleware.auth import get_current_session
from app.schemas.food_analysis import (
    IngredientCreate,
    IngredientResponse,
    IngredientUpdate,
    PhotoAnalysisResponse,
)
from app.services.food_analysis import FoodAnalysisService, trigger_analysis_background

router = APIRouter(
    prefix="/api/v1",
    tags=["food-analysis"],
    dependencies=[Depends(get_current_session)],
)


@router.get(
    "/photos/{photo_id}/analysis",
    response_model=PhotoAnalysisResponse,
)
def get_analysis(
    photo_id: int,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> PhotoAnalysisResponse:
    analysis = service.get_analysis(photo_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this photo",
        )
    return analysis


@router.put(
    "/photos/{photo_id}/analysis/confirm",
    response_model=PhotoAnalysisResponse,
)
def confirm_analysis(
    photo_id: int,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> PhotoAnalysisResponse:
    analysis = service.get_analysis(photo_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this photo",
        )
    return service.confirm_analysis(analysis.id)


@router.put(
    "/photos/{photo_id}/analysis/retry",
    response_model=PhotoAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_analysis(
    photo_id: int,
    background_tasks: BackgroundTasks,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> PhotoAnalysisResponse:
    # Delete existing analysis (cascade deletes ingredients)
    existing = service.get_analysis(photo_id)
    if existing:
        service.delete_analysis(existing.id)

    # Create a new pending record and kick off background analysis
    new_analysis = service.create_pending_analysis(photo_id)
    background_tasks.add_task(trigger_analysis_background, photo_id)
    return new_analysis


@router.put(
    "/ingredients/{ingredient_id}",
    response_model=IngredientResponse,
)
def update_ingredient(
    ingredient_id: int,
    body: IngredientUpdate,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> IngredientResponse:
    return service.update_ingredient(ingredient_id, body)


@router.post(
    "/photos/{photo_id}/analysis/ingredients",
    response_model=IngredientResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_ingredient(
    photo_id: int,
    body: IngredientCreate,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> IngredientResponse:
    analysis = service.get_analysis(photo_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this photo",
        )
    return service.add_ingredient(analysis.id, body)


@router.delete(
    "/ingredients/{ingredient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_ingredient(
    ingredient_id: int,
    service: FoodAnalysisService = Depends(get_food_analysis_service),
) -> None:
    service.delete_ingredient(ingredient_id)
