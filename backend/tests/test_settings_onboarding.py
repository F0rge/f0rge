from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_service import SettingsService


async def test_get_settings_includes_onboarding_completed_false(
    async_client: AsyncClient,
) -> None:
    resp = await async_client.get("/api/v1/settings")
    assert resp.status_code == 200
    assert resp.json()["onboarding_completed"] is False


async def test_complete_onboarding_sets_flag(async_client: AsyncClient) -> None:
    resp = await async_client.post("/api/v1/settings/onboarding/complete")
    assert resp.status_code == 200
    assert resp.json()["onboarding_completed"] is True

    get_resp = await async_client.get("/api/v1/settings")
    assert get_resp.json()["onboarding_completed"] is True


async def test_complete_onboarding_is_idempotent(async_client: AsyncClient) -> None:
    first = await async_client.post("/api/v1/settings/onboarding/complete")
    second = await async_client.post("/api/v1/settings/onboarding/complete")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["onboarding_completed"] is True
    assert second.json()["onboarding_completed"] is True


async def test_complete_onboarding_service(async_db: AsyncSession) -> None:
    svc = SettingsService(async_db)
    before = await svc.get()
    assert before.onboarding_completed is False

    after = await svc.complete_onboarding()
    assert after.onboarding_completed is True

    again = await svc.complete_onboarding()
    assert again.onboarding_completed is True
