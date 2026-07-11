from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.settings_service import SettingsService


@pytest.fixture(autouse=True)
def auth_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass auth middleware for settings onboarding tests."""
    from f0rge_db.auth_context import user_id_ctx
    from app.main import app
    from app.middleware.auth import get_current_user_id

    fake_user_id = uuid.UUID(settings.default_storage_user_id)
    token = user_id_ctx.set(fake_user_id)

    async def _fake_user_id() -> uuid.UUID:
        user_id_ctx.set(fake_user_id)
        return fake_user_id

    app.dependency_overrides[get_current_user_id] = _fake_user_id
    try:
        yield
    finally:
        user_id_ctx.reset(token)
        app.dependency_overrides.pop(get_current_user_id, None)


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
