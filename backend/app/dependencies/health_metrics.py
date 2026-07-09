from __future__ import annotations

from typing import Optional

from fastapi import Cookie, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import health_metrics as hm_service
from app.services.health_metrics import HealthMetricsService


async def require_health_import_auth(
    authorization: Optional[str] = Header(default=None),
    ht_session: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    await hm_service.validate_health_import_auth(authorization, ht_session, db)


def get_health_metrics_service(db: AsyncSession = Depends(get_db)) -> HealthMetricsService:
    return HealthMetricsService(db)
