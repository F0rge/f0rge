"""HTTP-level tests for bearer-token auth for mobile clients (#388).

Same stateless JWT as the ``ht_session`` cookie, accepted via
``Authorization: Bearer <jwt>`` so native clients skip cookie jars.
"""

from __future__ import annotations

import datetime
import uuid

import jwt
from httpx import AsyncClient

from tests.helpers import signup_payload
from app.config import settings
from app.services.auth import JWT_ALGORITHM

TEST_EMAIL = "bearer-test@example.com"
TEST_PASSWORD = "test-password-12"


async def _signup_and_login(client: AsyncClient) -> tuple[uuid.UUID, str]:
    signup = await client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    assert signup.status_code == 200
    client.cookies.clear()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["token"]
    return uuid.UUID(body["user_id"]), body["token"]


async def test_login_token_grants_bearer_only_access(async_client: AsyncClient) -> None:
    user_id, token = await _signup_and_login(async_client)
    async_client.cookies.clear()

    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["authenticated"] is True
    assert uuid.UUID(body["user_id"]) == user_id
    assert body["email"] == TEST_EMAIL


async def test_garbage_bearer_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert resp.status_code == 401


async def test_expired_bearer_returns_401(async_client: AsyncClient) -> None:
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "iat": datetime.datetime.utcnow() - datetime.timedelta(days=2),
            "exp": datetime.datetime.utcnow() - datetime.timedelta(days=1),
        },
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )

    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert resp.status_code == 401


async def test_cookie_only_flow_still_works(async_client: AsyncClient) -> None:
    signup = await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(TEST_EMAIL, TEST_PASSWORD),
    )
    assert signup.status_code == 200

    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == TEST_EMAIL


async def test_stale_cookie_falls_back_to_valid_bearer(async_client: AsyncClient) -> None:
    """A stale cookie must not shadow a valid bearer token (mixed-credential clients)."""
    user_id, token = await _signup_and_login(async_client)
    async_client.cookies.set("ht_session", "not-a-jwt")

    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert uuid.UUID(resp.json()["user_id"]) == user_id


async def test_stale_cookie_and_bad_bearer_still_401(async_client: AsyncClient) -> None:
    async_client.cookies.set("ht_session", "not-a-jwt")

    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer also-not-a-jwt"},
    )
    assert resp.status_code == 401
