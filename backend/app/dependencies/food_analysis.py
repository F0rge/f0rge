from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.food_analysis import FoodAnalysisService
from app.services.ingredient_lookup import IngredientLookupService


def get_food_analysis_service(
    db: AsyncSession = Depends(get_db),
) -> FoodAnalysisService:
    return FoodAnalysisService(db)


def get_ingredient_lookup_service(
    db: AsyncSession = Depends(get_db),
) -> IngredientLookupService:
    return IngredientLookupService(db)
