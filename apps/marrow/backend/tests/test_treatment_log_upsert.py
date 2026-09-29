from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.treatment_log import TreatmentLogService
from tests.test_mcp_tools import _seed_treatment


@pytest.mark.asyncio
async def test_upsert_respects_doses_when_not_tracked_per_day(async_db: AsyncSession) -> None:
    """Treatments without doses_per_day must still persist MCP/API dose logs."""
    treatment = await _seed_treatment(async_db, active=True)
    treatment.doses_per_day = None
    await async_db.flush()
    target = datetime.date(2026, 9, 30)
    service = TreatmentLogService(async_db)
    result = await service.upsert(treatment.id, target, 2)
    assert result.log.doses_taken == 2

    again = await service.upsert(treatment.id, target, 1)
    assert again.log.doses_taken == 1
