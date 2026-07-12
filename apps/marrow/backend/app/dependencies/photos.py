from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.food_analysis import get_food_analysis_orchestrator
from app.dependencies.meal_tags import get_meal_tag_service
from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
from app.services.meal_tags import MealTagService
from app.services.photos import PhotoService


def get_photo_service(
    db: AsyncSession = Depends(get_db),
    orchestrator: FoodAnalysisOrchestrator = Depends(get_food_analysis_orchestrator),
    meal_tags: MealTagService = Depends(get_meal_tag_service),
) -> PhotoService:
    return PhotoService(db, orchestrator, meal_tags)
