from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.health_metrics import require_health_import_auth
from app.middleware.auth import get_current_session
from app.schemas.health_metrics import HealthMetricResponse
from app.services import health_metrics as hm_service

router = APIRouter(
    prefix="/api/v1/health-metrics",
    tags=["health-metrics"],
)


@router.post("/import", status_code=status.HTTP_200_OK)
async def import_health_data(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(require_health_import_auth),
):
    return await hm_service.import_health_data(db, body)


@router.get(
    "/{date}",
    response_model=HealthMetricResponse,
    dependencies=[Depends(get_current_session)],
)
async def get_health_metric(date: datetime.date, db: AsyncSession = Depends(get_db)):
    return await hm_service.get_health_metric(db, date)
