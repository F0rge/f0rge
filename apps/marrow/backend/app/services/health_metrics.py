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
from f0rge_core.exceptions import NotFoundError, UnauthorizedError, ValidationError
from app.cache.invalidation import invalidate_feature_matrix_cache, invalidate_signals_cache
from app.models.health_metrics import HealthMetric
from app.schemas.health_metrics import (
    HEALTH_METRIC_SOURCES,
    HealthAutoExportPayload,
    HealthImportResponse,
    HealthMetricCreate,
)
from app.services.auth import decode_access_token
from app.services.health_import import parse_health_auto_export
from f0rge_db.tenant import apply_session_user_id, current_user_id

DEFAULT_SAMPLE_SOURCE = "ios_healthkit"
_MAX_RANGE_DAYS = 366

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
            fields = metric_create.model_dump(exclude={"date", "source"}, exclude_none=True)
            if existing:
                for field, value in fields.items():
                    setattr(existing, field, value)
            else:
                record = HealthMetric(
                    user_id=user_id,
                    source="health_auto_export",
                    **metric_create.model_dump(exclude={"source"}, exclude_none=True),
                )
                self.crud.add(record)
            upserted += 1

        await self.crud.save()
        await _invalidate_health_caches(user_id)
        return HealthImportResponse(status="ok", dates_upserted=upserted)

    async def ingest_samples(self, samples: list[HealthMetricCreate]) -> HealthImportResponse:
        """Upsert per-user daily health aggregates (iOS HealthKit or manual import).

        Each sample only updates the columns it actually provides, so partial
        batches never null out previously synced fields.
        """
        user_id = current_user_id()
        now = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            for sample in samples:
                source = _resolve_source(sample.source)
                fields = sample.model_dump(
                    exclude={"date", "source"}, exclude_unset=True, exclude_none=True
                )
                if not fields:
                    stmt = (
                        pg_insert(HealthMetric)
                        .values(
                            user_id=user_id,
                            date=sample.date,
                            source=source,
                        )
                        .on_conflict_do_nothing(constraint="uq_health_metrics_user_id_date")
                    )
                else:
                    stmt = pg_insert(HealthMetric).values(
                        user_id=user_id,
                        date=sample.date,
                        source=source,
                        **fields,
                    )
                    set_ = {name: getattr(stmt.excluded, name) for name in fields}
                    set_["source"] = stmt.excluded.source
                    set_["updated_at"] = now
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_health_metrics_user_id_date", set_=set_
                    )
                await self.db.execute(stmt)
        await _invalidate_health_caches(user_id)
        return HealthImportResponse(
            status="ok", dates_upserted=len({sample.date for sample in samples})
        )

    async def get_health_metric(self, date: datetime.date) -> HealthMetric:
        metric = await self.crud.get_by_date(date)
        if not metric:
            raise NotFoundError(f"No health metrics for {date}")
        return metric

    async def list_range(self, start: datetime.date, end: datetime.date) -> list[HealthMetric]:
        if start > end:
            raise ValidationError("start must be on or before end")
        if (end - start).days > _MAX_RANGE_DAYS:
            raise ValidationError(f"range cannot exceed {_MAX_RANGE_DAYS} days")
        return await self.crud.list_in_range(start, end)


def _resolve_source(source: Optional[str]) -> str:
    resolved = source or DEFAULT_SAMPLE_SOURCE
    if resolved not in HEALTH_METRIC_SOURCES:
        allowed = ", ".join(HEALTH_METRIC_SOURCES)
        raise ValidationError(
            f"unknown health metric source {resolved!r}; expected one of: {allowed}"
        )
    return resolved


async def _invalidate_health_caches(user_id: uuid.UUID) -> None:
    await invalidate_feature_matrix_cache(user_id)
    await invalidate_signals_cache(user_id)
