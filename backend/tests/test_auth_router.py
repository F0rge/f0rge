"""HTTP-level tests for the auth router (login/logout/me).

No mocks of app code: PIN hashing uses real bcrypt, sessions are real DB rows
via async_db, and auth state is proven through real login->authed-call
round-trips rather than dependency overrides. Per
feedback_no_mocks_at_seam_under_test.md, this is the seam under test, so it
must not be bypassed.
"""

from __future__ import annotations

import datetime

import bcrypt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.session import AuthSession

TEST_PIN = "1234"


@pytest.fixture(autouse=True)
def known_pin(monkeypatch: pytest.MonkeyPatch) -> str:
    """Seed settings.pin_hash with a real bcrypt hash of TEST_PIN.

    monkeypatch.setattr on a config *value* the service reads (settings.pin_hash)
    is the allowed pattern -- it is not mocking the auth service or its
    collaborators, just the config it consults.
    """
    hashed = bcrypt.hashpw(TEST_PIN.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    monkeypatch.setattr(settings, "pin_hash", hashed)
    return TEST_PIN


async def test_login_correct_pin_returns_200_and_sets_cookie(async_client: AsyncClient) -> None:
    resp = await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": True}
    assert "ht_session" in resp.cookies
    assert resp.cookies["ht_session"]


async def test_login_wrong_pin_returns_401_no_cookie(async_client: AsyncClient) -> None:
    resp = await async_client.post("/api/v1/auth/login", json={"pin": "0000"})
    assert resp.status_code == 401
    assert "ht_session" not in resp.cookies


async def test_login_wrong_pin_does_not_create_session_row(
    async_client: AsyncClient, async_db: AsyncSession
) -> None:
    await async_client.post("/api/v1/auth/login", json={"pin": "0000"})
    rows = (await async_db.execute(select(AuthSession))).scalars().all()
    assert rows == []


async def test_login_unconfigured_pin_returns_400(
    async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "pin_hash", "")
    resp = await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})
    assert resp.status_code == 400


async def test_me_unauthenticated_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_authenticated_after_login_returns_200(async_client: AsyncClient) -> None:
    await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": True}


async def test_logout_unauthenticated_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.post("/api/v1/auth/logout")
    assert resp.status_code == 401


async def test_logout_clears_session_and_subsequent_call_401s(async_client: AsyncClient) -> None:
    await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})

    logout_resp = await async_client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {"authenticated": False}

    me_resp = await async_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401


async def test_logout_deletes_session_row(
    async_client: AsyncClient, async_db: AsyncSession
) -> None:
    await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})
    await async_client.post("/api/v1/auth/logout")

    rows = (await async_db.execute(select(AuthSession))).scalars().all()
    assert rows == []


async def test_expired_session_returns_401(
    async_client: AsyncClient, async_db: AsyncSession
) -> None:
    await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})

    # Real DB write in test setup -- not a mock of app code, just moving the
    # clock on a row so the middleware's expiry check has something to catch.
    session = (await async_db.execute(select(AuthSession))).scalar_one()
    session.expires_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    await async_db.commit()

    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_expired_session_row_is_deleted_by_middleware(
    async_client: AsyncClient, async_db: AsyncSession
) -> None:
    await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})

    session = (await async_db.execute(select(AuthSession))).scalar_one()
    session.expires_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    await async_db.commit()

    await async_client.get("/api/v1/auth/me")

    rows = (await async_db.execute(select(AuthSession))).scalars().all()
    assert rows == []
