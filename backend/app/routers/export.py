from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.export import FeatureMatrixPage
from app.services.export import get_feature_matrix_csv, get_feature_matrix_page
from app.services.feature_matrix import FEATURE_SCHEMA_VERSION

router = APIRouter(
    tags=["export"],
    dependencies=[Depends(get_current_session)],
)

_SCHEMA_VERSION_HEADER = {"X-Feature-Schema-Version": str(FEATURE_SCHEMA_VERSION)}


@router.get("/api/v1/export/feature-matrix.csv")
async def export_csv(
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    csv_content, filename = await get_feature_matrix_csv(db, start, end)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            **_SCHEMA_VERSION_HEADER,
        },
    )


@router.get("/api/v1/analytics/feature-matrix", response_model=FeatureMatrixPage)
async def analytics_matrix(
    response: Response,
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> FeatureMatrixPage:
    response.headers.update(_SCHEMA_VERSION_HEADER)
    return await get_feature_matrix_page(db, start, end, page, size)
