"""Parametrized HTTP 401 contract tests for protected API routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# (method, path) — unauthenticated requests must return 401.
PROTECTED_ROUTES: list[tuple[str, str]] = [
    ("GET", "/api/v1/entries"),
    ("GET", "/api/v1/entries/2026-05-01"),
    ("GET", "/api/v1/entries/stats"),
    ("GET", "/api/v1/export/feature-matrix.csv"),
    ("GET", "/api/v1/enriched/2026-05-01"),
    ("GET", "/api/v1/weather/2026-05-01"),
    ("GET", "/api/v1/health-metrics/2026-05-01"),
    ("GET", "/api/v1/supplements/catalog"),
    ("GET", "/api/v1/symptoms/catalog"),
    ("GET", "/api/v1/trackers"),
    ("GET", "/api/v1/treatments"),
    ("GET", "/api/v1/labs"),
    ("GET", "/api/v1/settings"),
    ("GET", "/api/v1/catalog/suggestions"),
    ("GET", "/api/v1/notifications"),
    ("GET", "/api/v1/account"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
async def test_protected_route_requires_auth(
    async_client: AsyncClient,
    method: str,
    path: str,
) -> None:
    response = await async_client.request(method, path)
    assert response.status_code == 401, f"{method} {path} should require auth"
