"""Slow-request logging."""

from __future__ import annotations

import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app.middleware.slow_request import SlowRequestMiddleware


async def _ok(scope, receive, send):
    if scope["type"] != "http":
        return
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"ok"})


@pytest.mark.no_db
async def test_slow_request_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    app = SlowRequestMiddleware(_ok, threshold_seconds=0)
    transport = ASGITransport(app=app)
    with caplog.at_level(logging.WARNING, logger="app.http"):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/inventory")
    assert response.status_code == 200
    assert any(
        "Slow request GET /api/v1/inventory status=200" in record.message
        for record in caplog.records
    )


@pytest.mark.no_db
async def test_fast_request_stays_quiet(caplog: pytest.LogCaptureFixture) -> None:
    app = SlowRequestMiddleware(_ok, threshold_seconds=60)
    transport = ASGITransport(app=app)
    with caplog.at_level(logging.WARNING, logger="app.http"):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert not any(record.name == "app.http" for record in caplog.records)
