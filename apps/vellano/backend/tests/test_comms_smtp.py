"""SMTP mailbox settings and test-send."""

from __future__ import annotations

import smtplib

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient

from app.config import settings


@pytest.fixture(autouse=True)
def _comms_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "settings_encryption_key", Fernet.generate_key().decode())


class _FakeSMTP:
    instances: list["_FakeSMTP"] = []
    fail_login = False

    def __init__(self, host, port, timeout=None, context=None) -> None:
        self.host = host
        self.port = port
        self.user = None
        self.password = None
        self.started_tls = False
        self.messages: list[object] = []
        _FakeSMTP.instances.append(self)

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def ehlo(self) -> tuple[int, bytes]:
        return (250, b"ok")

    def starttls(self, context=None) -> None:
        self.started_tls = True

    def login(self, user: str, password: str) -> None:
        if _FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication failed")
        self.user = user
        self.password = password

    def send_message(self, msg: object) -> dict:
        self.messages.append(msg)
        return {}


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSMTP]:
    _FakeSMTP.instances = []
    _FakeSMTP.fail_login = False
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTP)
    return _FakeSMTP


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


async def test_patch_password_then_get_redacts_secret(owner_client: AsyncClient) -> None:
    patch = await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_security": "starttls",
            "smtp_username": "shop@example.com",
            "smtp_password": "super-secret",
            "smtp_from_address": "shop@example.com",
            "smtp_from_name": "Vellano",
        },
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["has_smtp_password"] is True
    assert body["smtp_configured"] is True
    assert "smtp_password" not in body
    assert "smtp_password_encrypted" not in body
    dumped = str(body)
    assert "super-secret" not in dumped

    fetched = await owner_client.get("/api/v1/settings/comms")
    assert fetched.status_code == 200
    assert fetched.json()["has_smtp_password"] is True
    assert "smtp_password" not in fetched.json()


async def test_second_patch_without_password_keeps_existing(owner_client: AsyncClient) -> None:
    first = await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_from_address": "shop@example.com",
            "smtp_password": "keep-me",
        },
    )
    assert first.status_code == 200
    second = await owner_client.patch(
        "/api/v1/settings/comms",
        json={"smtp_from_name": "Shop"},
    )
    assert second.status_code == 200
    assert second.json()["has_smtp_password"] is True
    assert second.json()["smtp_from_name"] == "Shop"


async def test_empty_password_clears_and_test_send_unconfigured(
    owner_client: AsyncClient,
) -> None:
    await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_from_address": "shop@example.com",
            "smtp_password": "temp",
        },
    )
    cleared = await owner_client.patch(
        "/api/v1/settings/comms",
        json={"smtp_password": "", "smtp_host": "", "smtp_from_address": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["has_smtp_password"] is False
    assert cleared.json()["smtp_configured"] is False
    probe = await owner_client.post(
        "/api/v1/settings/comms/test-email",
        json={"to": "leo@example.com"},
    )
    assert probe.status_code == 503
    assert probe.json()["detail"]["code"] == "comms_smtp_unconfigured"


async def test_test_send_mocked_success(
    owner_client: AsyncClient,
    fake_smtp: type[_FakeSMTP],
) -> None:
    await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_security": "starttls",
            "smtp_username": "shop@example.com",
            "smtp_password": "pw",
            "smtp_from_address": "shop@example.com",
        },
    )
    resp = await owner_client.post(
        "/api/v1/settings/comms/test-email",
        json={"to": "leo@example.com"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert len(fake_smtp.instances) == 1
    sent = fake_smtp.instances[0]
    assert sent.started_tls is True
    assert sent.user == "shop@example.com"
    assert sent.password == "pw"
    assert len(sent.messages) == 1


async def test_test_send_mocked_535(
    owner_client: AsyncClient,
    fake_smtp: type[_FakeSMTP],
) -> None:
    fake_smtp.fail_login = True
    await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_from_address": "shop@example.com",
            "smtp_username": "shop@example.com",
            "smtp_password": "bad",
        },
    )
    resp = await owner_client.post(
        "/api/v1/settings/comms/test-email",
        json={"to": "leo@example.com"},
    )
    assert resp.status_code == 502
    assert resp.json()["detail"]["code"] == "comms_smtp_failed"
    assert "bad" not in str(resp.json())


async def test_warehouse_can_get_but_not_patch(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_from_address": "shop@example.com",
        },
    )
    await _login(async_client, "warehouse@example.com", settings.seed_warehouse_password)
    got = await async_client.get("/api/v1/settings/comms")
    assert got.status_code == 200
    assert got.json()["smtp_configured"] is True
    denied = await async_client.patch(
        "/api/v1/settings/comms",
        json={"smtp_from_name": "Nope"},
    )
    assert denied.status_code == 403
    test_denied = await async_client.post(
        "/api/v1/settings/comms/test-email",
        json={"to": "leo@example.com"},
    )
    assert test_denied.status_code == 403
