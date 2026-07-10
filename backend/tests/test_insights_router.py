"""HTTP-level tests for the insights router."""

from __future__ import annotations

from httpx import AsyncClient


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
