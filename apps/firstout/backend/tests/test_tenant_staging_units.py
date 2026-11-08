from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.config import Settings, settings
from app.runtime_database import verify_isolation_stage
from app.services.tenant_host import request_tenant_slug

pytestmark = pytest.mark.no_db


def request(host="api.firstout.co.za", **headers):
    return Request(
        {
            "type": "http",
            "headers": [(k.encode(), v.encode()) for k, v in {"host": host, **headers}.items()],
        }
    )


def test_compatibility_ignores_unsigned_frontend_host(monkeypatch):
    monkeypatch.setattr(settings, "tenant_isolation_mode", "single_home")
    monkeypatch.setattr(settings, "frontend_proxy_secret", "")
    monkeypatch.setattr(settings, "cookie_secure", True)
    assert request_tenant_slug(request(**{"x-firstout-frontend-host": "firstout.co.za"})) is None
    assert (
        request_tenant_slug(request(**{"x-firstout-frontend-host": "attacker.app.firstout.co.za"}))
        is None
    )
    with pytest.raises(HTTPException):
        request_tenant_slug(request(host="attacker.app.firstout.co.za"))


def test_proxy_secret_set_never_accepts_unsigned_header(monkeypatch):
    monkeypatch.setattr(settings, "tenant_isolation_mode", "single_home")
    monkeypatch.setattr(settings, "frontend_proxy_secret", "synthetic")
    with pytest.raises(HTTPException):
        request_tenant_slug(request(**{"x-firstout-frontend-host": "firstout.co.za"}))


def test_invalid_stage_cannot_fall_back():
    with pytest.raises(ValueError):
        Settings(tenant_isolation_mode="enforce")


@pytest.mark.asyncio
@pytest.mark.parametrize("second_team,active_rls", [(True, False), (False, True)])
async def test_single_home_refuses_inconsistent_database(monkeypatch, second_team, active_rls):
    monkeypatch.setattr(settings, "tenant_isolation_mode", "single_home")
    monkeypatch.setattr(settings, "clerk_enabled", False)
    monkeypatch.setattr(settings, "tenant_signup_enabled", False)
    monkeypatch.setattr(settings, "clerk_import_enabled", False)
    db = SimpleNamespace(scalar=AsyncMock(side_effect=[second_team, active_rls]))
    with pytest.raises(RuntimeError):
        await verify_isolation_stage(db)


@pytest.mark.asyncio
async def test_enforced_stage_requires_secret_even_on_http(monkeypatch):
    monkeypatch.setattr(settings, "tenant_isolation_mode", "enforced")
    monkeypatch.setattr(settings, "cookie_secure", False)
    monkeypatch.setattr(settings, "frontend_proxy_secret", "")
    with pytest.raises(RuntimeError, match="FRONTEND_PROXY_SECRET"):
        await verify_isolation_stage(AsyncMock())
