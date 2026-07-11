"""HTTP-level tests for the export router."""

from __future__ import annotations

from httpx import AsyncClient


async def test_export_csv_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/export/feature-matrix.csv")
    assert resp.status_code == 401


async def test_analytics_matrix_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/analytics/feature-matrix")
    assert resp.status_code == 401


async def test_analytics_matrix_authenticated_returns_page(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/analytics/feature-matrix")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "total" in body
