"""HTTP-level tests for the supplement catalog router."""

from __future__ import annotations

from httpx import AsyncClient


async def test_list_supplements_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/supplements/catalog")
    assert resp.status_code == 401


async def test_list_supplements_authenticated_returns_list(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/supplements/catalog")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
