from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, status

from app.dependencies.health_metrics import get_health_metrics_service, require_health_import_auth
from app.middleware.auth import get_current_session
from app.schemas.health_metrics import HealthAutoExportPayload, HealthImportResponse, HealthMetricResponse
from app.services.health_metrics import HealthMetricsService

router = APIRouter(
    prefix="/api/v1/health-metrics",
    tags=["health-metrics"],
)


@router.post("/import", status_code=status.HTTP_200_OK, response_model=HealthImportResponse)
async def import_health_data(
    body: HealthAutoExportPayload,
    _auth: None = Depends(require_health_import_auth),
    service: HealthMetricsService = Depends(get_health_metrics_service),
):
    return await service.import_health_data(body)


@router.get(
    "/{date}",
    response_model=HealthMetricResponse,
    dependencies=[Depends(get_current_session)],
)
async def get_health_metric(
    date: datetime.date,
    service: HealthMetricsService = Depends(get_health_metrics_service),
):
    return await service.get_health_metric(date)
