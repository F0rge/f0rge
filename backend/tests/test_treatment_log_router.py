from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.treatment_log import TreatmentLog
from app.schemas.treatment import TreatmentCreate
from app.services.treatment_log import TreatmentLogService
from app.services.treatments import TreatmentService
from app.tenant import apply_session_user_id, clear_tenant_session

_LOG_DATE = datetime.date(2026, 7, 10)
_TREATMENT_PAYLOAD = {
    "name": "Test Protocol",
    "type": "protocol",
    "start_date": "2026-07-01",
    "doses_per_day": 3,
}


@pytest.mark.asyncio
async def test_empty_user_id_guc_breaks_uuid_cast(async_db: AsyncSession) -> None:
    """Document the prod failure mode: '' poisons RLS uuid casts."""
    await async_db.execute(sa.text("SELECT set_config('app.user_id', '', false)"))
    with pytest.raises(DBAPIError):
        await async_db.execute(sa.text("SELECT current_setting('app.user_id', true)::uuid"))


@pytest.mark.asyncio
async def test_clear_tenant_session_allows_reapply(async_db: AsyncSession) -> None:
    """After pool cleanup + re-apply, RLS uuid cast must work again."""
    uid = uuid.UUID(settings.default_storage_user_id)
    await apply_session_user_id(async_db, uid)
    await clear_tenant_session(async_db)
    await apply_session_user_id(async_db, uid)
    casted = (
        await async_db.execute(sa.text("SELECT current_setting('app.user_id', true)::uuid"))
    ).scalar_one()
    assert casted == uid


@pytest.mark.asyncio
async def test_put_treatment_log_updates_existing_row(authed_client: AsyncClient) -> None:
    """PUT /treatments/{id}/log must update an existing log row (not only insert)."""
    create = await authed_client.post("/api/v1/treatments", json=_TREATMENT_PAYLOAD)
    assert create.status_code == 201
    treatment_id = create.json()["id"]

    first = await authed_client.put(
        f"/api/v1/treatments/{treatment_id}/log",
        json={"date": _LOG_DATE.isoformat(), "doses_taken": 1},
    )
    assert first.status_code == 200
    assert first.json()["doses_taken"] == 1

    second = await authed_client.put(
        f"/api/v1/treatments/{treatment_id}/log",
        json={"date": _LOG_DATE.isoformat(), "doses_taken": 2},
    )
    assert second.status_code == 200
    assert second.json()["doses_taken"] == 2


@pytest.mark.asyncio
async def test_treatment_log_upsert_after_session_clear(async_db: AsyncSession) -> None:
    """Simulate pooled-connection cleanup then update an existing treatment log."""
    uid = uuid.UUID(settings.default_storage_user_id)
    treatments = TreatmentService(async_db)
    logs = TreatmentLogService(async_db)

    treatment = await treatments.create(
        TreatmentCreate(
            name="Pooled GUC Test",
            type="protocol",
            start_date=datetime.date(2026, 7, 1),
            doses_per_day=3,
        )
    )
    await logs.upsert(treatment.id, _LOG_DATE, 1)
    await clear_tenant_session(async_db)
    await apply_session_user_id(async_db, uid)

    updated = await logs.upsert(treatment.id, _LOG_DATE, 2)
    assert updated.doses_taken == 2
    assert isinstance(updated, TreatmentLog)
