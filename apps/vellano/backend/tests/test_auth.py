"""HTTP-level auth tests for Vellano S1."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.auth import JWT_COOKIE_NAME
from tests.conftest import OWNER_EMAIL, OWNER_PASSWORD, assert_vellano_session_cookie


async def test_login_returns_200_and_sets_cookie(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == OWNER_EMAIL
    assert_vellano_session_cookie(resp)
    assert JWT_COOKIE_NAME in resp.cookies


async def test_me_unauthenticated_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_authenticated_returns_200_with_team(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == OWNER_EMAIL
    assert body["role"] == "owner"
    assert body["team"]["name"] == "Vellano"
    assert body["team"]["id"]
    assert "default_location_id" in body
    assert isinstance(body["permissions"], list)
    assert "users.manage" in body["permissions"]
    assert "till.sell" in body["permissions"]


async def test_logout_clears_session(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    logout_resp = await async_client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204
    me_resp = await async_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401


async def test_login_wrong_password_returns_401_no_cookie(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert JWT_COOKIE_NAME not in resp.cookies
    assert JWT_COOKIE_NAME not in resp.headers.get("set-cookie", "")


async def test_disabled_user_cannot_login(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_resp = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "disabled@example.com",
            "password": "disabled-user",
            "role": "buyer",
        },
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    disable_resp = await owner_client.patch(
        f"/api/v1/users/{user_id}",
        json={"is_disabled": True},
    )
    assert disable_resp.status_code == 200

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@example.com", "password": "disabled-user"},
    )
    assert login_resp.status_code == 401
    assert JWT_COOKIE_NAME not in login_resp.cookies


@pytest.mark.no_db
def test_no_ht_session_string_in_implementation() -> None:
    """Vellano must not reuse Marrow's ht_session cookie name."""
    backend_root = Path(__file__).resolve().parents[1]
    app_roots = [
        backend_root / "app",
        backend_root.parent / "frontend" / "src",
    ]
    hits: list[str] = []
    for root in app_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "ht_session" in content:
                hits.append(str(path.relative_to(backend_root.parent.parent.parent)))
    assert hits == [], f"ht_session found in: {hits}"
