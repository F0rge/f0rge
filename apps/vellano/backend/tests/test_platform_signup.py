from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.main import app
from app.platform.crud import SignupCRUD
from app.platform.database import platform_sessionmaker
from app.platform.models import SIGNUP_STATUS_PENDING_VERIFY, SIGNUP_STATUS_READY, Signup
from app.platform.provisioning import ProvisioningService
from app.services.auth import hash_password
from f0rge_db.crud import unit_of_work
from tests.conftest import TENANT_HOST_HEADER


def _platform_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


def _signup_body(**overrides: object) -> dict:
    body: dict = {
        "legal_name": "Acme (Pty) Ltd",
        "trading_name": "Acme",
        "slug": "acmeqa",
        "owner_name": "Ada Owner",
        "email": "ada@acme.example",
        "password": "correct horse battery staple",
        "authorised": True,
        "privacy_accepted": True,
        "privacy_version": "2026-09-draft",
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_reserved_slug_unavailable(platform_registry: str) -> None:
    async with _platform_client() as client:
        resp = await client.get("/api/v1/platform/slugs/vellano/availability")
    assert resp.status_code == 200
    assert resp.json()["available"] is False
    assert resp.json()["reason"] == "reserved"


async def _fake_ready_provision(_self: ProvisioningService, signup_id: uuid.UUID):
    maker = platform_sessionmaker()
    async with maker() as db:
        signup = await SignupCRUD(db).get_by_id(signup_id)
        assert signup is not None
        signup.status = SIGNUP_STATUS_READY
        await db.commit()
    return signup


@pytest.mark.asyncio
async def test_create_log_mode_auto_provisions_without_session(
    platform_registry: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.platform.signup_service.send_verify_email", AsyncMock())
    monkeypatch.setattr(ProvisioningService, "provision", _fake_ready_provision)

    async with _platform_client() as client:
        created = await client.post("/api/v1/platform/signups", json=_signup_body())
        assert created.status_code == 202
        assert created.json()["status"] == "provisioning"
        assert "set-cookie" not in {k.lower() for k in created.headers}
        signup_id = created.json()["signup_id"]
        status_resp = await client.get(f"/api/v1/platform/signups/{signup_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "ready"
        assert status_resp.json()["workspace_url"] == "http://acmeqa.localhost:3003"


@pytest.mark.asyncio
async def test_create_smtp_verify_status_no_auto_login(
    platform_registry: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tokens: list[str] = []

    async def capture_mail(*, to: str, token: str) -> None:
        tokens.append(token)

    monkeypatch.setattr(settings, "platform_mail_mode", "smtp")
    monkeypatch.setattr(settings, "platform_smtp_host", "smtp.example.com")
    monkeypatch.setattr("app.platform.signup_service.send_verify_email", capture_mail)
    monkeypatch.setattr(ProvisioningService, "provision", _fake_ready_provision)

    async with _platform_client() as client:
        created = await client.post("/api/v1/platform/signups", json=_signup_body())
        assert created.status_code == 202
        assert created.json()["status"] == "pending_verify"
        assert "set-cookie" not in {k.lower() for k in created.headers}
        signup_id = created.json()["signup_id"]
        assert tokens
        verify = await client.post(
            "/api/v1/platform/signups/verify",
            json={"token": tokens[0]},
        )
        assert verify.status_code == 200
        assert verify.json()["status"] in {"verified", "provisioning"}
        assert "set-cookie" not in {k.lower() for k in verify.headers}
        again = await client.post(
            "/api/v1/platform/signups/verify",
            json={"token": tokens[0]},
        )
        assert again.status_code == 400
        status_resp = await client.get(f"/api/v1/platform/signups/{signup_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "ready"
        assert status_resp.json()["workspace_url"] == "http://acmeqa.localhost:3003"


@pytest.mark.asyncio
async def test_ip_rate_limit_returns_429(
    platform_registry: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.platform.signup_service.send_verify_email",
        AsyncMock(),
    )
    monkeypatch.setattr(ProvisioningService, "provision", _fake_ready_provision)
    async with _platform_client() as client:
        for index in range(10):
            resp = await client.post(
                "/api/v1/platform/signups",
                json=_signup_body(slug=f"ipqa{index:02d}", email=f"ip{index}@acme.example"),
                headers={"X-Forwarded-For": "203.0.113.9"},
            )
            assert resp.status_code == 202
        eleventh = await client.post(
            "/api/v1/platform/signups",
            json=_signup_body(slug="ipqa10", email="ip10@acme.example"),
            headers={"X-Forwarded-For": "203.0.113.9"},
        )
    assert eleventh.status_code == 429


@pytest.mark.asyncio
async def test_branding_requires_tenant_header(platform_registry: str) -> None:
    async with _platform_client() as client:
        missing = await client.get("/api/v1/branding")
        assert missing.status_code == 404
        ok = await client.get("/api/v1/branding", headers=TENANT_HOST_HEADER)
        assert ok.status_code == 200
        assert ok.json()["slug"] == "vellano"


@pytest.mark.asyncio
async def test_taken_slug_returns_409(
    platform_registry: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "platform_mail_mode", "smtp")
    monkeypatch.setattr(settings, "platform_smtp_host", "smtp.example.com")
    monkeypatch.setattr("app.platform.signup_service.send_verify_email", AsyncMock())
    async with _platform_client() as client:
        first = await client.post("/api/v1/platform/signups", json=_signup_body())
        assert first.status_code == 202
        second = await client.post(
            "/api/v1/platform/signups",
            json=_signup_body(email="other@acme.example"),
        )
    assert second.status_code == 409
    assert second.json()["detail"] == "taken"


@pytest.mark.asyncio
async def test_inflight_slug_is_unique(
    platform_registry: str,
) -> None:
    maker = platform_sessionmaker()

    def _row(email: str) -> Signup:
        return Signup(
            email=email,
            legal_name="Dup (Pty) Ltd",
            slug="dupslug",
            owner_name="Ada",
            password_hash=hash_password("correct horse battery staple"),
            status=SIGNUP_STATUS_PENDING_VERIFY,
            privacy_version="2026-09-draft",
            authorised_confirmed_at=datetime.datetime.utcnow(),
        )

    async with maker() as db:
        async with unit_of_work(db):
            db.add(_row("one@dup.example"))
            await db.flush()
        db.add(_row("two@dup.example"))
        with pytest.raises(IntegrityError):
            await db.commit()
