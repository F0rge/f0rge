from __future__ import annotations

import datetime
import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import NotFoundError, UnauthorizedError
from app.models.health_metrics import HealthMetric
from app.services.auth import decode_access_token
from app.services.health_import import parse_health_auto_export

_logger = logging.getLogger("health_import_debug")


async def validate_health_import_auth(
    authorization: Optional[str],
    ht_session: Optional[str],
    _db: AsyncSession,
) -> None:
    """Validate bearer token or session cookie for the health import endpoint.

    Raises UnauthorizedError when neither credential is valid.
    """
    # Try Bearer token first
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if settings.health_import_token and token == settings.health_import_token:
            return

    # Try session cookie (JWT)
    if ht_session:
        try:
            decode_access_token(ht_session)
            return
        except UnauthorizedError:
            pass

    raise UnauthorizedError("Not authenticated")


async def import_health_data(db: AsyncSession, body: dict) -> dict:
    """Parse and upsert Health Auto Export metrics. Returns upserted count."""
    # Log raw sleep metrics for debugging
    for m in body.get("data", {}).get("metrics", []):
        name = m.get("name", "")
        samples = m.get("data", [])
        if "sleep" in name.lower() and samples:
            _logger.warning(
                "RAW SLEEP METRIC: name=%s, sample_count=%d, first_sample=%s",
                name,
                len(samples),
                json.dumps(samples[0], default=str)[:500],
            )

    parsed = parse_health_auto_export(body)
    upserted = 0

    for date_key, metric_create in parsed.items():
        existing = (
            await db.execute(select(HealthMetric).where(HealthMetric.date == metric_create.date))
        ).scalar_one_or_none()
        if existing:
            update_data = metric_create.model_dump(exclude={"date"}, exclude_none=True)
            for field, value in update_data.items():
                setattr(existing, field, value)
        else:
            record = HealthMetric(**metric_create.model_dump())
            db.add(record)
        upserted += 1

    await db.commit()
    return {"status": "ok", "dates_upserted": upserted}


async def get_health_metric(db: AsyncSession, date: datetime.date) -> HealthMetric:
    metric = (
        await db.execute(select(HealthMetric).where(HealthMetric.date == date))
    ).scalar_one_or_none()
    if not metric:
        raise NotFoundError(f"No health metrics for {date}")
    return metric


class HealthMetricsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def import_health_data(self, body: dict) -> dict:
        return await import_health_data(self.db, body)

    async def get_health_metric(self, date: datetime.date) -> HealthMetric:
        return await get_health_metric(self.db, date)
