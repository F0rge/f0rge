"""Historical session settings never issue or extend a local login session."""

from __future__ import annotations

import time

import jwt
from httpx import AsyncClient

from tests.conftest import OWNER_EMAIL, OWNER_PASSWORD, signed_clerk_token


async def test_historical_session_ttl_setting_remains_readable(owner_client: AsyncClient) -> None:
    response = await owner_client.get("/api/v1/settings")
    assert response.status_code == 200
    assert response.json()["session_ttl_hours"] == 12


async def test_historical_session_ttl_values_remain_validated(owner_client: AsyncClient) -> None:
    for hours in (1, 720):
        response = await owner_client.patch("/api/v1/settings", json={"session_ttl_hours": hours})
        assert response.status_code == 400 and "Clerk" in response.json()["detail"]
        assert (await owner_client.get("/api/v1/settings")).json()["session_ttl_hours"] == 12
    for hours in (0, 721):
        assert (
            await owner_client.patch("/api/v1/settings", json={"session_ttl_hours": hours})
        ).status_code == 422


async def test_local_ttl_does_not_restore_password_login_or_issue_cookie(
    owner_client: AsyncClient,
) -> None:
    assert (
        await owner_client.patch("/api/v1/settings", json={"session_ttl_hours": 720})
    ).status_code == 400
    response = await owner_client.post(
        "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}
    )
    assert response.status_code == 400
    assert "set-cookie" not in response.headers


async def test_local_ttl_cannot_extend_an_expired_signed_clerk_token(
    owner_client: AsyncClient,
) -> None:
    assert (
        await owner_client.patch("/api/v1/settings", json={"session_ttl_hours": 720})
    ).status_code == 400
    original = owner_client.headers["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(original, options={"verify_signature": False})
    now = int(time.time())
    expired = signed_clerk_token(
        claims["sub"],
        org_id=claims["o"]["id"],
        org_slug=claims["o"]["slg"],
        iat=now - 120,
        nbf=now - 120,
        exp=now - 60,
    )
    response = await owner_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer " + expired}
    )
    assert response.status_code == 401
    assert (await owner_client.get("/api/v1/auth/me")).status_code == 200
