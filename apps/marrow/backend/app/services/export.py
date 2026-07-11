from __future__ import annotations

import csv
import datetime
import io
from typing import Optional

from fastapi import Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.export import FeatureMatrixPage
from app.services.feature_matrix import FEATURE_SCHEMA_VERSION, build_feature_matrix

_SCHEMA_VERSION_HEADER = {"X-Feature-Schema-Version": str(FEATURE_SCHEMA_VERSION)}


class ExportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def stream_feature_matrix_csv(
        self,
        start: Optional[datetime.date],
        end: Optional[datetime.date],
    ) -> StreamingResponse:
        csv_content, filename = await self._build_csv(start, end)
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                **_SCHEMA_VERSION_HEADER,
            },
        )

    async def get_analytics_matrix_page(
        self,
        response: Response,
        start: Optional[datetime.date],
        end: Optional[datetime.date],
        page: int,
        size: int,
    ) -> FeatureMatrixPage:
        response.headers.update(_SCHEMA_VERSION_HEADER)
        return await self._build_page(start, end, page, size)

    async def _build_csv(
        self,
        start: Optional[datetime.date],
        end: Optional[datetime.date],
    ) -> tuple[str, str]:
        rows, columns = await build_feature_matrix(self.db, start, end)
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        buf.seek(0)
        start_str = rows[0]["date"] if rows else "empty"
        end_str = rows[-1]["date"] if rows else "empty"
        filename = f"feature_matrix_{start_str}_{end_str}.csv"
        return buf.getvalue(), filename

    async def _build_page(
        self,
        start: Optional[datetime.date],
        end: Optional[datetime.date],
        page: int,
        size: int,
    ) -> FeatureMatrixPage:
        rows, columns = await build_feature_matrix(self.db, start, end)
        total = len(rows)
        pages = max(1, (total + size - 1) // size)
        offset = (page - 1) * size
        page_rows = rows[offset : offset + size]
        return FeatureMatrixPage(
            data=page_rows,
            columns=columns,
            total=total,
            page=page,
            size=size,
            pages=pages,
        )
