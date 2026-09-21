"""Team-configurable session TTL (#679)."""

from __future__ import annotations

import re

from httpx import AsyncClient

from tests.conftest import OWNER_EMAIL, OWNER_PASSWORD


def _parse_cookie_max_age(set_cookie: str) -> int:
    match = re.search(r"Max-Age=(\d+)", set_cookie, flags=re.IGNORECASE)
    assert match is not None, set_cookie
    return int(match.group(1))


async def test_get_settings_default_session_ttl_hours(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/settings")
    assert resp.status_code == 200
    assert resp.json()["session_ttl_hours"] == 12


async def test_patch_session_ttl_hours_valid(owner_client: AsyncClient) -> None:
    for hours in (1, 720):
        resp = await owner_client.patch(
            "/api/v1/settings",
            json={"session_ttl_hours": hours},
        )
        assert resp.status_code == 200
        assert resp.json()["session_ttl_hours"] == hours


async def test_patch_session_ttl_hours_invalid(owner_client: AsyncClient) -> None:
    for hours in (0, 721):
        resp = await owner_client.patch(
            "/api/v1/settings",
            json={"session_ttl_hours": hours},
        )
        assert resp.status_code == 422


async def test_login_cookie_max_age_matches_default_ttl(async_client: AsyncClient) -> None:
    async_client.cookies.clear()
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert resp.status_code == 200
    max_age = _parse_cookie_max_age(resp.headers.get("set-cookie", ""))
    assert max_age == 12 * 3600


async def test_login_uses_updated_session_ttl(
    owner_client: AsyncClient,
    async_client: AsyncClient,
) -> None:
    patch_resp = await owner_client.patch(
        "/api/v1/settings",
        json={"session_ttl_hours": 2},
    )
    assert patch_resp.status_code == 200

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert login_resp.status_code == 200
    max_age = _parse_cookie_max_age(login_resp.headers.get("set-cookie", ""))
    assert max_age == 2 * 3600
