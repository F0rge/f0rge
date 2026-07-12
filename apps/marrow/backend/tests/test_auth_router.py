"""HTTP-level tests for the auth router (signup/login/logout/me).

No mocks of app code: password hashing uses real bcrypt, JWTs are real signed
tokens, and auth state is proven through real signup/login->authed-call
round-trips rather than dependency overrides.
"""

from __future__ import annotations

import datetime
import uuid

import jwt
import pytest
from httpx import AsyncClient

from tests.helpers import signup_payload
from app.config import settings
from app.services.auth import JWT_ALGORITHM, JWT_COOKIE_NAME, create_access_token

TEST_EMAIL = "auth-test@example.com"
TEST_PASSWORD = "test-password-12"
OTHER_EMAIL = "other@example.com"


async def test_signup_creates_user_and_sets_cookie(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    assert body["email"] == TEST_EMAIL
    assert uuid.UUID(body["user_id"])
    assert JWT_COOKIE_NAME in resp.cookies
    assert resp.cookies[JWT_COOKIE_NAME]


async def test_signup_duplicate_email_returns_409(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    assert resp.status_code == 409


async def test_signup_short_password_returns_422(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, "short"),
    )
    assert resp.status_code == 422


async def test_login_correct_credentials_returns_200_and_sets_cookie(
    async_client: AsyncClient,
) -> None:
    await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    async_client.cookies.clear()

    resp = await async_client.post(
        "/api/v1/auth/login",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True
    assert JWT_COOKIE_NAME in resp.cookies


async def test_login_wrong_password_returns_401_no_cookie(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    async_client.cookies.clear()

    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert JWT_COOKIE_NAME not in resp.cookies


async def test_login_unconfigured_jwt_secret_returns_400(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    async_client.cookies.clear()
    monkeypatch.setattr(settings, "jwt_secret", "")

    resp = await async_client.post(
        "/api/v1/auth/login",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    assert resp.status_code == 400


async def test_me_unauthenticated_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_authenticated_after_signup_returns_200(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    assert body["email"] == TEST_EMAIL


async def test_logout_clears_cookie_and_subsequent_call_401s(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )

    logout_resp = await async_client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {
        "authenticated": False,
        "user_id": None,
        "email": None,
        "handle": None,
    }

    me_resp = await async_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401


async def test_expired_jwt_returns_401(async_client: AsyncClient) -> None:
    signup_resp = await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    user_id = uuid.UUID(signup_resp.json()["user_id"])

    expired = jwt.encode(
        {
            "sub": str(user_id),
            "iat": datetime.datetime.utcnow() - datetime.timedelta(days=2),
            "exp": datetime.datetime.utcnow() - datetime.timedelta(days=1),
        },
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )
    async_client.cookies.clear()
    async_client.cookies.set(JWT_COOKIE_NAME, expired)

    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_logout_without_session_still_returns_200(async_client: AsyncClient) -> None:
    resp = await async_client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is False


async def test_create_access_token_round_trips_user_id() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == str(user_id)
