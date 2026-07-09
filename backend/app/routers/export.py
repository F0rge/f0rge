from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse

from app.dependencies.export import get_export_service
from app.middleware.auth import get_current_session
from app.schemas.export import FeatureMatrixPage
from app.services.export import ExportService

router = APIRouter(
    tags=["export"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/api/v1/export/feature-matrix.csv")
async def export_csv(
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    service: ExportService = Depends(get_export_service),
) -> StreamingResponse:
    return await service.stream_feature_matrix_csv(start, end)


@router.get("/api/v1/analytics/feature-matrix", response_model=FeatureMatrixPage)
async def analytics_matrix(
    response: Response,
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=30, ge=1, le=365),
    service: ExportService = Depends(get_export_service),
) -> FeatureMatrixPage:
    return await service.get_analytics_matrix_page(response, start, end, page, size)
