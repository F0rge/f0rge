from __future__ import annotations

from typing import Optional

from fastapi import Header

from app.config import settings
from app.services.meal_analysis_stages import MealAnalysisStageService, require_internal_token


def get_meal_analysis_stage_service(
    x_meal_analysis_token: Optional[str] = Header(default=None, alias="X-Meal-Analysis-Token"),
) -> MealAnalysisStageService:
    require_internal_token(x_meal_analysis_token, settings.meal_analysis_internal_token)
    return MealAnalysisStageService()
