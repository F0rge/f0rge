"""HTTP-level tests for the weather router."""

from __future__ import annotations

from httpx import AsyncClient


async def test_get_weather_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/weather/2026-01-01")
    assert resp.status_code == 401


async def test_fetch_weather_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.post("/api/v1/weather/fetch")
    assert resp.status_code == 401


async def test_get_weather_authenticated_not_found_404(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/weather/2026-01-01")
    assert resp.status_code == 404
