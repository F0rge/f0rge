"""Tests for social handles (issue #303)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _signup(
    async_client: AsyncClient,
    *,
    email: str,
    handle: str,
    password: str = "secure-pass-12",
) -> dict:
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "handle": handle},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_signup_with_handle_persists(authed_client: AsyncClient):
    handle = f"user_{uuid.uuid4().hex[:8]}"
    data = await _signup(authed_client, email=f"{handle}@example.com", handle=handle)
    assert data["handle"] == handle

    me = await authed_client.get("/api/v1/auth/me")
    assert me.json()["handle"] == handle


async def test_duplicate_handle_returns_409(async_client: AsyncClient):
    handle = f"dup_{uuid.uuid4().hex[:8]}"
    await _signup(async_client, email=f"a_{handle}@example.com", handle=handle)
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": f"b_{handle}@example.com", "password": "secure-pass-12", "handle": handle},
    )
    assert resp.status_code == 409


async def test_case_collision_returns_409(async_client: AsyncClient):
    base = f"case_{uuid.uuid4().hex[:8]}"
    await _signup(async_client, email=f"{base}@example.com", handle=base)
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"{base}_b@example.com",
            "password": "secure-pass-12",
            "handle": base.upper(),
        },
    )
    assert resp.status_code == 409


@pytest.mark.parametrize(
    "handle",
    ["ab", "a" * 31, "has space", "emoji😀"],
)
async def test_invalid_handle_format_rejected(async_client: AsyncClient, handle: str):
    email = f"bad_{uuid.uuid4().hex[:8]}@example.com"
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secure-pass-12", "handle": handle},
    )
    assert resp.status_code in (400, 422)


async def test_uppercase_handle_stored_lowercase(async_client: AsyncClient):
    suffix = uuid.uuid4().hex[:8]
    handle = f"leo_{suffix}"
    await _signup(async_client, email=f"{handle}@example.com", handle=handle.upper())
    me = await async_client.get("/api/v1/auth/me")
    assert me.json()["handle"] == handle


async def test_patch_account_claims_handle(authed_client: AsyncClient):
    handle = f"claim_{uuid.uuid4().hex[:8]}"
    resp = await authed_client.patch("/api/v1/account", json={"handle": handle})
    assert resp.status_code == 200
    assert resp.json()["handle"] == handle


async def test_changing_handle_releases_old(authed_client: AsyncClient, async_client: AsyncClient):
    old = f"old_{uuid.uuid4().hex[:8]}"
    new = f"new_{uuid.uuid4().hex[:8]}"
    await authed_client.patch("/api/v1/account", json={"handle": old})
    await authed_client.patch("/api/v1/account", json={"handle": new})

    avail = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"reuse_{uuid.uuid4().hex[:6]}@example.com",
            "password": "secure-pass-12",
            "handle": old,
        },
    )
    assert avail.status_code == 200


async def test_lookup_returns_whitelisted_fields_only(authed_client: AsyncClient):
    handle = f"lookup_{uuid.uuid4().hex[:8]}"
    await authed_client.patch(
        "/api/v1/account", json={"handle": handle, "display_name": "Test User"}
    )

    resp = await authed_client.get(f"/api/v1/social/users/lookup?handle={handle}")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"handle", "display_name", "avatar_default_index"}
    assert body["handle"] == handle
    assert "email" not in body
    assert "id" not in body
    assert "user_id" not in body


async def test_lookup_unknown_handle_404(authed_client: AsyncClient):
    resp = await authed_client.get("/api/v1/social/users/lookup?handle=nonexistent_xyz")
    assert resp.status_code == 404


async def test_lookup_unauthenticated_401(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/social/users/lookup?handle=anyone")
    assert resp.status_code == 401


async def test_handle_available_taken_and_free(
    async_client: AsyncClient, authed_client: AsyncClient
):
    handle = f"avail_{uuid.uuid4().hex[:8]}"
    free = await async_client.get(f"/api/v1/social/handle-available?handle={handle}")
    assert free.status_code == 200
    assert free.json()["available"] is True

    await authed_client.patch("/api/v1/account", json={"handle": handle})
    taken = await async_client.get(f"/api/v1/social/handle-available?handle={handle}")
    assert taken.json()["available"] is False


async def test_handle_available_invalid_format_false(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/social/handle-available?handle=!!")
    assert resp.status_code == 200
    assert resp.json()["available"] is False
