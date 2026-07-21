from __future__ import annotations

import datetime
import json
import logging
import uuid
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from f0rge_db.auth_context import user_id_ctx
from app.config import settings
from app.crud.base import unit_of_work
from app.crud.health_metrics import HealthMetricsCRUD
from f0rge_core.exceptions import NotFoundError, UnauthorizedError
from app.models.health_metrics import HealthMetric
from app.schemas.health_metrics import (
    HealthAutoExportPayload,
    HealthImportResponse,
    HealthMetricCreate,
)
from app.services.auth import decode_access_token
from app.services.health_import import parse_health_auto_export
from f0rge_db.tenant import apply_session_user_id, current_user_id

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

    async def import_health_data(self, body: HealthAutoExportPayload) -> HealthImportResponse:
        """Parse and upsert Health Auto Export metrics. Returns upserted count."""
        payload = body.model_dump()
        # Log raw sleep metrics for debugging
        for m in payload.get("data", {}).get("metrics", []):
            name = m.get("name", "")
            samples = m.get("data", [])
            if "sleep" in name.lower() and samples:
                _logger.warning(
                    "RAW SLEEP METRIC: name=%s, sample_count=%d, first_sample=%s",
                    name,
                    len(samples),
                    json.dumps(samples[0], default=str)[:500],
                )

        parsed = parse_health_auto_export(payload)
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

        await self.crud.save()
        return HealthImportResponse(status="ok", dates_upserted=upserted)

    async def ingest_samples(self, samples: list[HealthMetricCreate]) -> HealthImportResponse:
        """Upsert per-user daily HealthKit aggregates posted by the iOS app.

        Each sample only updates the columns it actually provides, so partial
        batches never null out previously synced fields.
        """
        user_id = current_user_id()
        now = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            for sample in samples:
                fields = sample.model_dump(exclude={"date"}, exclude_unset=True, exclude_none=True)
                if not fields:
                    stmt = (
                        pg_insert(HealthMetric)
                        .values(
                            user_id=user_id,
                            date=sample.date,
                            source="ios_healthkit",
                        )
                        .on_conflict_do_nothing(constraint="uq_health_metrics_user_id_date")
                    )
                else:
                    stmt = pg_insert(HealthMetric).values(
                        user_id=user_id,
                        date=sample.date,
                        source="ios_healthkit",
                        **fields,
                    )
                    set_ = {name: getattr(stmt.excluded, name) for name in fields}
                    set_["source"] = stmt.excluded.source
                    set_["updated_at"] = now
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_health_metrics_user_id_date", set_=set_
                    )
                await self.db.execute(stmt)
        return HealthImportResponse(
            status="ok", dates_upserted=len({sample.date for sample in samples})
        )

    async def get_health_metric(self, date: datetime.date) -> HealthMetric:
        metric = await self.crud.get_by_date(date)
        if not metric:
            raise NotFoundError(f"No health metrics for {date}")
        return metric
