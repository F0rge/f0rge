from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.food_analysis import FoodAnalysisService
from app.services.ingredient_lookup import IngredientLookupService


def get_food_analysis_service(
    db: Session = Depends(get_db),
) -> FoodAnalysisService:
    return FoodAnalysisService(db)


def get_ingredient_lookup_service(
    db: Session = Depends(get_db),
) -> IngredientLookupService:
    return IngredientLookupService(db)
