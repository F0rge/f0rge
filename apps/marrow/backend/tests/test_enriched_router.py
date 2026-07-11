"""HTTP-level tests for the enriched router."""

from __future__ import annotations

from httpx import AsyncClient


async def test_get_enriched_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/enriched/2026-01-01")
    assert resp.status_code == 401


async def test_get_enriched_authenticated_returns_shape(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/enriched/2026-01-01")
    assert resp.status_code == 200
    body = resp.json()
    assert "entry" in body
    assert "weather" in body
    assert "health_metrics" in body
