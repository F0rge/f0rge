"""Staff forgot-password flow. Fake SMTP only — no customer data."""

from __future__ import annotations

import datetime
import re
import time

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.password_reset_token import PasswordResetToken
from app.services.auth import JWT_COOKIE_NAME
from app.services.password_reset import (
    CONFIRM_MESSAGE,
    CONFIRM_PER_IP,
    NEUTRAL_MESSAGE,
    NEUTRAL_MIN_SECONDS,
    REQUEST_PER_EMAIL,
    hash_reset_token,
    limiter,
)
from tests.conftest import OWNER_EMAIL, OWNER_PASSWORD
from tests.test_comms_smtp import _FakeSMTP

import app.services.password_reset as password_reset_module
import smtplib


@pytest.fixture(autouse=True)
def _reset_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter.reset()
    monkeypatch.setattr(password_reset_module, "NEUTRAL_MIN_SECONDS", 0)
    monkeypatch.setattr(settings, "settings_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "public_app_url", "https://firstout.test")
    _FakeSMTP.instances = []
    _FakeSMTP.fail_login = False
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTP)
    yield
    limiter.reset()


async def _configure_smtp(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_security": "starttls",
            "smtp_username": "shop@example.com",
            "smtp_password": "not-a-real-secret",
            "smtp_from_address": "shop@example.com",
            "smtp_from_name": "Firstout",
        },
    )
    assert resp.status_code == 200


def _reset_link_token() -> str:
    assert _FakeSMTP.instances, "expected a reset email"
    message = _FakeSMTP.instances[-1].messages[-1]
    body = message.get_content()
    assert "Firstout" in body
    assert message["Subject"] == "Reset your Firstout password"
    match = re.search(r"https://firstout\.test/reset-password\?token=([^\s]+)", body)
    assert match is not None
    return match.group(1)


async def _tokens(db: AsyncSession) -> list[PasswordResetToken]:
    result = await db.execute(select(PasswordResetToken))
    return list(result.scalars().all())


async def test_unknown_and_known_emails_share_a_neutral_response(
    owner_client: AsyncClient,
) -> None:
    await _configure_smtp(owner_client)
    missing = await owner_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    known = await owner_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": OWNER_EMAIL.upper()},
    )
    assert missing.status_code == 200
    assert known.status_code == 200
    assert missing.json() == known.json() == {"message": NEUTRAL_MESSAGE}
    assert _reset_link_token()


async def test_disabled_user_gets_the_same_response_and_no_email(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    await _configure_smtp(owner_client)
    created = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "disabled-reset@example.com",
            "password": "disabled-user",
            "role": "buyer",
        },
    )
    assert created.status_code == 201
    disabled = await owner_client.patch(
        f"/api/v1/users/{created.json()['id']}",
        json={"is_disabled": True},
    )
    assert disabled.status_code == 200

    before = len(_FakeSMTP.instances)
    resp = await owner_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "disabled-reset@example.com"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == NEUTRAL_MESSAGE
    assert len(_FakeSMTP.instances) == before
    assert await _tokens(async_db) == []


async def test_token_is_hashed_single_use_and_replaced(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    await _configure_smtp(owner_client)
    first = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": OWNER_EMAIL},
    )
    assert first.status_code == 200
    old_token = _reset_link_token()
    second = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": OWNER_EMAIL},
    )
    assert second.status_code == 200
    new_token = _reset_link_token()
    assert old_token != new_token

    stored = await _tokens(async_db)
    hashes = {row.token_hash for row in stored}
    assert old_token not in hashes
    assert new_token not in hashes
    assert hash_reset_token(old_token) in hashes
    assert hash_reset_token(new_token) in hashes
    assert all(len(row.token_hash) == 64 for row in stored)

    stale = await async_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": old_token,
            "password": "replaced-password",
            "password_confirm": "replaced-password",
        },
    )
    assert stale.status_code == 400
    assert stale.json()["detail"] == "This reset link has already been used."

    updated = await async_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": new_token,
            "password": "replaced-password",
            "password_confirm": "replaced-password",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["message"] == CONFIRM_MESSAGE

    again = await async_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": new_token,
            "password": "another-password",
            "password_confirm": "another-password",
        },
    )
    assert again.status_code == 400
    assert again.json()["detail"] == "This reset link has already been used."

    async_client.cookies.clear()
    old_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert old_login.status_code == 401
    new_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": "replaced-password"},
    )
    assert new_login.status_code == 200


async def test_expired_and_invalid_tokens(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    await _configure_smtp(owner_client)
    requested = await owner_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": OWNER_EMAIL},
    )
    assert requested.status_code == 200
    token = _reset_link_token()
    row = (await _tokens(async_db))[0]
    row.expires_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
    await async_db.flush()

    expired = await owner_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": "fresh-password",
            "password_confirm": "fresh-password",
        },
    )
    assert expired.status_code == 400
    assert expired.json()["detail"] == "This reset link has expired."

    invalid = await owner_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "not-a-real-token",
            "password": "fresh-password",
            "password_confirm": "fresh-password",
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "This reset link is invalid."


async def test_password_rules_and_mismatch_do_not_consume_the_token(
    owner_client: AsyncClient,
) -> None:
    await _configure_smtp(owner_client)
    await owner_client.post("/api/v1/auth/forgot-password", json={"email": OWNER_EMAIL})
    token = _reset_link_token()

    short = await owner_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "short", "password_confirm": "short"},
    )
    assert short.status_code == 422

    mismatch = await owner_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": "long-enough",
            "password_confirm": "different-one",
        },
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"] == "Passwords do not match."

    ok = await owner_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": "long-enough",
            "password_confirm": "long-enough",
        },
    )
    assert ok.status_code == 200


async def test_reset_invalidates_existing_session(async_client: AsyncClient) -> None:
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert login.status_code == 200
    await _configure_smtp(async_client)
    old_cookie = async_client.cookies.get(JWT_COOKIE_NAME)
    assert old_cookie

    await async_client.post("/api/v1/auth/forgot-password", json={"email": OWNER_EMAIL})
    token = _reset_link_token()
    reset = await async_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": "session-password",
            "password_confirm": "session-password",
        },
    )
    assert reset.status_code == 200

    async_client.cookies.clear()
    async_client.cookies.set(JWT_COOKIE_NAME, old_cookie)
    me = await async_client.get("/api/v1/auth/me")
    assert me.status_code == 401

    async_client.cookies.clear()
    fresh = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": "session-password"},
    )
    assert fresh.status_code == 200
    assert (await async_client.get("/api/v1/auth/me")).status_code == 200


async def test_disabled_user_cannot_finish_a_reset(owner_client: AsyncClient) -> None:
    await _configure_smtp(owner_client)
    created = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "later-disabled@example.com",
            "password": "starting-password",
            "role": "buyer",
        },
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    owner_client.cookies.clear()
    await owner_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    await _configure_smtp(owner_client)
    await owner_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "later-disabled@example.com"},
    )
    token = _reset_link_token()
    disabled = await owner_client.patch(
        f"/api/v1/users/{user_id}",
        json={"is_disabled": True},
    )
    assert disabled.status_code == 200

    reset = await owner_client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": "should-not-apply",
            "password_confirm": "should-not-apply",
        },
    )
    assert reset.status_code == 400
    assert reset.json()["detail"] == "This account is disabled."

    enabled = await owner_client.patch(
        f"/api/v1/users/{user_id}",
        json={"is_disabled": False},
    )
    assert enabled.status_code == 200
    owner_client.cookies.clear()
    old_login = await owner_client.post(
        "/api/v1/auth/login",
        json={"email": "later-disabled@example.com", "password": "starting-password"},
    )
    assert old_login.status_code == 200
    owner_client.cookies.clear()
    new_login = await owner_client.post(
        "/api/v1/auth/login",
        json={"email": "later-disabled@example.com", "password": "should-not-apply"},
    )
    assert new_login.status_code == 401


async def test_request_and_confirm_rate_limits(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(password_reset_module, "REQUEST_PER_EMAIL", 2)
    first = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "limit@example.com"},
    )
    second = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "limit@example.com"},
    )
    third = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "limit@example.com"},
    )
    assert first.status_code == second.status_code == 200
    assert third.status_code == 429
    assert third.json()["detail"] == "Too many attempts. Try again later."

    other = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "other-limit@example.com"},
    )
    assert other.status_code == 200

    monkeypatch.setattr(password_reset_module, "REQUEST_PER_IP", 1)
    limiter.reset()
    monkeypatch.setattr(password_reset_module, "REQUEST_PER_EMAIL", REQUEST_PER_EMAIL)
    ip_first = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ip-one@example.com"},
        headers={"X-Forwarded-For": "203.0.113.10"},
    )
    ip_second = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ip-two@example.com"},
        headers={"X-Forwarded-For": "203.0.113.10"},
    )
    assert ip_first.status_code == 200
    assert ip_second.status_code == 429

    monkeypatch.setattr(password_reset_module, "CONFIRM_PER_IP", 2)
    bad = {
        "token": "missing-token",
        "password": "long-enough",
        "password_confirm": "long-enough",
    }
    assert (await async_client.post("/api/v1/auth/reset-password", json=bad)).status_code == 400
    assert (await async_client.post("/api/v1/auth/reset-password", json=bad)).status_code == 400
    blocked = await async_client.post("/api/v1/auth/reset-password", json=bad)
    assert blocked.status_code == 429


async def test_neutral_responses_take_about_the_same_time(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(password_reset_module, "NEUTRAL_MIN_SECONDS", 0.2)
    started = time.monotonic()
    missing = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "timing-missing@example.com"},
    )
    missing_elapsed = time.monotonic() - started
    started = time.monotonic()
    known = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": OWNER_EMAIL},
    )
    known_elapsed = time.monotonic() - started
    assert missing.status_code == known.status_code == 200
    assert missing.json() == known.json()
    assert missing_elapsed >= 0.2
    assert known_elapsed >= 0.2
    assert abs(missing_elapsed - known_elapsed) < 0.25


def test_limit_constants_are_the_documented_defaults() -> None:
    assert REQUEST_PER_EMAIL == 5
    assert CONFIRM_PER_IP == 10
    assert NEUTRAL_MIN_SECONDS == 0.3
