from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.airflow_meal_analysis import (
    AirflowMealAnalysisService,
    validate_airflow_service_token,
)


async def require_airflow_service_auth(
    authorization: Optional[str] = Header(default=None),
) -> None:
    validate_airflow_service_token(authorization)


def get_airflow_meal_analysis_service(
    db: AsyncSession = Depends(get_db),
) -> AirflowMealAnalysisService:
    return AirflowMealAnalysisService(db)
