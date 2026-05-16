from __future__ import annotations

import csv
import datetime
import io
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.export import FeatureMatrixPage
from app.services.feature_matrix import build_feature_matrix


async def get_feature_matrix_csv(
    db: AsyncSession,
    start: Optional[datetime.date],
    end: Optional[datetime.date],
) -> tuple[str, str]:
    """Return (csv_content, filename)."""
    rows, columns = await build_feature_matrix(db, start, end)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    start_str = rows[0]["date"] if rows else "empty"
    end_str = rows[-1]["date"] if rows else "empty"
    filename = f"feature_matrix_{start_str}_{end_str}.csv"
    return buf.getvalue(), filename


async def get_feature_matrix_page(
    db: AsyncSession,
    start: Optional[datetime.date],
    end: Optional[datetime.date],
    page: int,
    size: int,
) -> FeatureMatrixPage:
    rows, columns = await build_feature_matrix(db, start, end)
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
