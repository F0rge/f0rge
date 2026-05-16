from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.health_metrics import HealthMetricResponse
from app.services import health_metrics as hm_service

router = APIRouter(
    prefix="/api/v1/health-metrics",
    tags=["health-metrics"],
)


async def _require_health_import_auth(
    authorization: Optional[str] = Header(default=None),
    ht_session: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    await hm_service.validate_health_import_auth(authorization, ht_session, db)


@router.post("/import", status_code=status.HTTP_200_OK)
async def import_health_data(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_health_import_auth),
):
    return await hm_service.import_health_data(db, body)


@router.get(
    "/{date}",
    response_model=HealthMetricResponse,
    dependencies=[Depends(get_current_session)],
)
async def get_health_metric(date: datetime.date, db: AsyncSession = Depends(get_db)):
    return await hm_service.get_health_metric(db, date)
