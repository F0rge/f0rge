from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.food_analysis import get_food_analysis_orchestrator
from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
from app.services.photos import PhotoService


def get_photo_service(
    db: AsyncSession = Depends(get_db),
    orchestrator: FoodAnalysisOrchestrator = Depends(get_food_analysis_orchestrator),
) -> PhotoService:
    return PhotoService(db, orchestrator)
