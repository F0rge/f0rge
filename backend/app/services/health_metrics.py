from __future__ import annotations

import datetime
import json
import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_context import user_id_ctx
from app.config import settings
from app.crud.health_metrics import HealthMetricsCRUD
from app.exceptions import NotFoundError, UnauthorizedError
from app.models.health_metrics import HealthMetric
from app.services.auth import decode_access_token
from app.services.health_import import parse_health_auto_export
from app.tenant import apply_session_user_id, current_user_id

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
            user_id = uuid.UUID(settings.default_storage_user_id)
            user_id_ctx.set(user_id)
            await apply_session_user_id(_db, user_id)
            return

    # Try session cookie (JWT)
    if ht_session:
        try:
            user_id = decode_access_token(ht_session)
            user_id_ctx.set(user_id)
            await apply_session_user_id(_db, user_id)
            return
        except UnauthorizedError:
            pass

    raise UnauthorizedError("Not authenticated")


class HealthMetricsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = HealthMetricsCRUD(db)

    async def import_health_data(self, body: dict) -> dict:
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
        user_id = current_user_id()

        for date_key, metric_create in parsed.items():
            existing = await self.crud.get_by_date_owned(metric_create.date)
            if existing:
                update_data = metric_create.model_dump(exclude={"date"}, exclude_none=True)
                for field, value in update_data.items():
                    setattr(existing, field, value)
            else:
                record = HealthMetric(user_id=user_id, **metric_create.model_dump())
                self.crud.add(record)
            upserted += 1

        await self.crud.commit()
        return {"status": "ok", "dates_upserted": upserted}

    async def get_health_metric(self, date: datetime.date) -> HealthMetric:
        metric = await self.crud.get_by_date(date)
        if not metric:
            raise NotFoundError(f"No health metrics for {date}")
        return metric
