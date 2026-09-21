"""Nia health endpoint and permission seeds."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.permissions import NIA_ADMIN, NIA_USE


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("till@example.com", settings.seed_till_password),
        ("warehouse@example.com", settings.seed_warehouse_password),
        ("buyer@example.com", settings.seed_buyer_password),
        ("books@example.com", settings.seed_books_password),
    ],
)
async def test_shop_floor_roles_have_nia_use_only(
    async_client: AsyncClient,
    email: str,
    password: str,
) -> None:
    await _login(async_client, email, password)
    me = await async_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    permissions = set(me.json()["permissions"])
    assert NIA_USE in permissions
    assert NIA_ADMIN not in permissions


async def test_owner_has_nia_permissions(owner_client: AsyncClient) -> None:
    me = await owner_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    permissions = set(me.json()["permissions"])
    assert NIA_USE in permissions
    assert NIA_ADMIN in permissions


async def test_nia_health_logged_in_no_key(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    resp = await owner_client.get("/api/v1/nia/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"ok": True, "llm": False}
    assert "OPENROUTER" not in resp.text.upper()
    assert "sk-" not in resp.text


async def test_nia_health_logged_out(async_client: AsyncClient) -> None:
    async_client.cookies.clear()
    resp = await async_client.get("/api/v1/nia/health")
    assert resp.status_code == 401
