from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.meal_analysis_stages import MealAnalysisStageService, require_internal_token


def get_meal_analysis_stage_service(
    x_meal_analysis_token: Optional[str] = Header(default=None, alias="X-Meal-Analysis-Token"),
    db: AsyncSession = Depends(get_db),
) -> MealAnalysisStageService:
    require_internal_token(x_meal_analysis_token, settings.meal_analysis_internal_token)
    return MealAnalysisStageService(db)
