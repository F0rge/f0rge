from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.insights import InsightsService


def get_insights_service(db: AsyncSession = Depends(get_db)) -> InsightsService:
    return InsightsService(db)
