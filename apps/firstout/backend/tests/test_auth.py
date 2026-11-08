"""HTTP staff authentication uses signed Clerk sessions only."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.auth import JWT_COOKIE_NAME
from tests.conftest import (
    OWNER_EMAIL,
    OWNER_PASSWORD,
    authenticate_as,
    create_test_staff,
    legacy_staff_token,
)


@pytest.mark.parametrize("password", [OWNER_PASSWORD, "wrong-password"])
async def test_password_login_is_retired_without_issuing_a_cookie(
    async_client: AsyncClient, password: str
) -> None:
    response = await async_client.post(
        "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": password}
    )
    assert response.status_code == 400
    assert "Clerk" in response.json()["detail"]
    assert JWT_COOKIE_NAME not in response.cookies
    assert JWT_COOKIE_NAME not in response.headers.get("set-cookie", "")
    assert (await async_client.get("/api/v1/auth/me")).status_code == 401


async def test_me_unauthenticated_returns_401(async_client: AsyncClient) -> None:
    assert (await async_client.get("/api/v1/auth/me")).status_code == 401


async def test_signed_clerk_me_returns_preserved_team_role_and_permissions(
    async_client: AsyncClient,
) -> None:
    response = await authenticate_as(async_client, OWNER_EMAIL)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == OWNER_EMAIL
    assert body["role"] == "owner"
    assert body["team"]["name"] == "Firstout" and body["team"]["id"]
    assert "default_location_id" in body
    assert {"users.manage", "till.sell"} <= set(body["permissions"])
    assert JWT_COOKIE_NAME not in response.cookies


async def test_logout_only_deletes_stale_cookie_and_clerk_signout_clears_bearer(
    owner_client: AsyncClient,
) -> None:
    owner_client.cookies.set(JWT_COOKIE_NAME, "stale-local-cookie")
    response = await owner_client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers.get("set-cookie", "")
    # The local endpoint cannot invalidate an externally issued Clerk token.
    assert (await owner_client.get("/api/v1/auth/me")).status_code == 200
    owner_client.headers.pop("Authorization", None)
    assert (await owner_client.get("/api/v1/auth/me")).status_code == 401


async def test_valid_legacy_staff_cookie_and_hs_bearer_are_both_rejected(
    async_client: AsyncClient, async_db: AsyncSession
) -> None:
    owner = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    token = legacy_staff_token(owner.id, token_version=owner.token_version)
    async_client.cookies.set(JWT_COOKIE_NAME, token)
    assert (await async_client.get("/api/v1/auth/me")).status_code == 401
    async_client.cookies.clear()
    assert (
        await async_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
    ).status_code == 401


async def test_disabled_member_cannot_use_a_signed_clerk_session(
    owner_client: AsyncClient,
) -> None:
    user = await create_test_staff(owner_client, email="disabled@example.com", role="buyer")
    disabled = await owner_client.patch(f"/api/v1/users/{user['id']}", json={"is_disabled": True})
    assert disabled.status_code == 200 and disabled.json()["is_disabled"] is True
    assert (await authenticate_as(owner_client, user["email"])).status_code == 401


@pytest.mark.no_db
def test_no_ht_session_string_in_implementation() -> None:
    """Firstout must not reuse Marrow's private cookie name."""
    backend_root = Path(__file__).resolve().parents[1]
    roots = [backend_root / "app", backend_root.parent / "frontend" / "src"]
    hits = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".mjs",
                ".cjs",
            }:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "ht_session" in content:
                hits.append(str(path.relative_to(backend_root.parent.parent.parent)))
    assert hits == [], f"ht_session found in: {hits}"
