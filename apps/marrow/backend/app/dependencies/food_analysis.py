from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.food_analysis import FoodAnalysisService
from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
from app.services.ingredient_lookup import IngredientLookupService


def get_food_analysis_orchestrator() -> FoodAnalysisOrchestrator:
    return FoodAnalysisOrchestrator()


def get_food_analysis_service(
    db: AsyncSession = Depends(get_db),
    orchestrator: FoodAnalysisOrchestrator = Depends(get_food_analysis_orchestrator),
) -> FoodAnalysisService:
    return FoodAnalysisService(db, orchestrator)


def get_ingredient_lookup_service(
    db: AsyncSession = Depends(get_db),
) -> IngredientLookupService:
    return IngredientLookupService(db)
