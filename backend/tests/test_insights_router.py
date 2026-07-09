"""HTTP-level tests for the insights router."""

from __future__ import annotations

import bcrypt
import pytest
from httpx import AsyncClient

from app.config import settings

TEST_PIN = "1234"


@pytest.fixture(autouse=True)
def known_pin(monkeypatch: pytest.MonkeyPatch) -> str:
    hashed = bcrypt.hashpw(TEST_PIN.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    monkeypatch.setattr(settings, "pin_hash", hashed)
    return TEST_PIN


@pytest.fixture
async def authed_client(async_client: AsyncClient) -> AsyncClient:
    resp = await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})
    assert resp.status_code == 200
    return async_client


async def test_trends_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/insights/trends")
    assert resp.status_code == 401


async def test_correlates_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/insights/correlates", params={"outcome": "overall"})
    assert resp.status_code == 401


async def test_trends_authenticated_returns_series(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/insights/trends")
    assert resp.status_code == 200
    body = resp.json()
    assert "series" in body
