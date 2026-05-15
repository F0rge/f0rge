from __future__ import annotations

import csv
import datetime
import io
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.export import FeatureMatrixPage
from app.services.feature_matrix import FEATURE_SCHEMA_VERSION, build_feature_matrix

router = APIRouter(
    tags=["export"],
    dependencies=[Depends(get_current_session)],
)

_SCHEMA_VERSION_HEADER = {"X-Feature-Schema-Version": str(FEATURE_SCHEMA_VERSION)}


@router.get("/api/v1/export/feature-matrix.csv")
def export_csv(
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows, columns = build_feature_matrix(db, start, end)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)

    start_str = rows[0]["date"] if rows else "empty"
    end_str = rows[-1]["date"] if rows else "empty"
    filename = f"feature_matrix_{start_str}_{end_str}.csv"

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            **_SCHEMA_VERSION_HEADER,
        },
    )


@router.get("/api/v1/analytics/feature-matrix", response_model=FeatureMatrixPage)
def analytics_matrix(
    response: Response,
    start: Optional[datetime.date] = Query(default=None),
    end: Optional[datetime.date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> FeatureMatrixPage:
    rows, columns = build_feature_matrix(db, start, end)

    total = len(rows)
    pages = max(1, (total + size - 1) // size)
    offset = (page - 1) * size
    page_rows = rows[offset : offset + size]

    response.headers.update(_SCHEMA_VERSION_HEADER)

    return FeatureMatrixPage(
        data=page_rows,
        columns=columns,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
