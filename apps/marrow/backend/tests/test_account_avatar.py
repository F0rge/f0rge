"""Tests for account avatar upload, serve, and delete."""

from __future__ import annotations

import io

from httpx import AsyncClient
from PIL import Image

from conftest import TEST_EMAIL
from tests.helpers import signup_payload


def _make_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (64, 64), color=(120, 180, 220))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def test_get_account_includes_avatar_fields(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/account")
    assert resp.status_code == 200
    body = resp.json()
    assert 0 <= body["avatar_default_index"] < 32
    assert body["has_custom_avatar"] is False


async def test_custom_avatar_round_trip(authed_client: AsyncClient) -> None:
    files = {"file": ("avatar.jpg", _make_jpeg_bytes(), "image/jpeg")}
    upload = await authed_client.post("/api/v1/account/avatar", files=files)
    assert upload.status_code == 200
    assert upload.json()["has_custom_avatar"] is True

    get_avatar = await authed_client.get("/api/v1/account/avatar")
    assert get_avatar.status_code == 200
    assert get_avatar.headers["content-type"].startswith("image/jpeg")

    delete = await authed_client.delete("/api/v1/account/avatar")
    assert delete.status_code == 200
    assert delete.json()["has_custom_avatar"] is False

    missing = await authed_client.get("/api/v1/account/avatar")
    assert missing.status_code == 404


async def test_upload_avatar_rejects_non_image(authed_client: AsyncClient) -> None:
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    resp = await authed_client.post("/api/v1/account/avatar", files=files)
    assert resp.status_code == 400


async def test_signup_assigns_stable_default_avatar_index(async_client: AsyncClient) -> None:
    email = "avatar-test@example.com"
    password = "test-password-12"
    signup = await async_client.post(
        "/api/v1/auth/signup",
        json=signup_payload(email, password),
    )
    assert signup.status_code == 200

    account = await async_client.get("/api/v1/account")
    assert account.status_code == 200
    index = account.json()["avatar_default_index"]
    assert 0 <= index < 32

    # Idempotent on repeat fetch
    again = await async_client.get("/api/v1/account")
    assert again.json()["avatar_default_index"] == index

    assert account.json()["email"] == email
    assert email != TEST_EMAIL
