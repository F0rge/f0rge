"""HTTP-level tests for the account router (get/update/password/delete).

No mocks of app code: password hashing uses real bcrypt, session auth is
proven through real signup/login round-trips, and account deletion exercises
the real filesystem via a redirected ``photo_dir`` -- same no-mocks-at-the-
storage-seam pattern as ``test_photos_upload_integration.py``'s
``real_storage`` fixture.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from fastapi import Response
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from f0rge_core.exceptions import ValidationError
from app.models.entry import Entry
from app.models.lab import Lab
from app.models.photo import Photo
from app.models.user import User
from app.schemas.account import AccountDeleteRequest
from app.services import object_storage
from app.services.account import AccountService
from app.services.auth import JWT_COOKIE_NAME, hash_password
from app.services.photo_storage import save_photo
from conftest import TEST_EMAIL, TEST_PASSWORD

NEW_PASSWORD = "new-password-99"

_ENTRY_PAYLOAD = {
    "overall": 3,
    "bloating": 1,
    "stool_status": "normal",
    "joint_pain": 0,
    "neuro": 0,
    "sleep_quality": 4,
    "stress": 2,
    "diet_risk": "",
    "supplements": "",
    "sick": False,
}


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------


async def test_get_account_returns_signup_email_and_null_display_name(
    authed_client: AsyncClient,
) -> None:
    resp = await authed_client.get("/api/v1/account")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == TEST_EMAIL
    assert body["display_name"] is None
    assert uuid.UUID(body["user_id"])


# ---------------------------------------------------------------------------
# PATCH
# ---------------------------------------------------------------------------


async def test_patch_account_sets_display_name_and_persists(
    authed_client: AsyncClient,
) -> None:
    resp = await authed_client.patch("/api/v1/account", json={"display_name": "Leo"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Leo"

    get_resp = await authed_client.get("/api/v1/account")
    assert get_resp.json()["display_name"] == "Leo"


async def test_patch_account_empty_string_normalizes_to_null(
    authed_client: AsyncClient,
) -> None:
    await authed_client.patch("/api/v1/account", json={"display_name": "Leo"})

    resp = await authed_client.patch("/api/v1/account", json={"display_name": "   "})
    assert resp.status_code == 200
    assert resp.json()["display_name"] is None

    get_resp = await authed_client.get("/api/v1/account")
    assert get_resp.json()["display_name"] is None


async def test_patch_account_persists_display_name_with_unchanged_handle(
    authed_client: AsyncClient,
) -> None:
    account = await authed_client.get("/api/v1/account")
    current_handle = account.json()["handle"]
    assert current_handle

    resp = await authed_client.patch(
        "/api/v1/account",
        json={"display_name": "Bob", "handle": current_handle},
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Bob"

    get_resp = await authed_client.get("/api/v1/account")
    assert get_resp.json()["display_name"] == "Bob"
    assert get_resp.json()["handle"] == current_handle


async def test_patch_account_rejects_handle_change_once_set(
    authed_client: AsyncClient,
) -> None:
    account = await authed_client.get("/api/v1/account")
    current_handle = account.json()["handle"]
    assert current_handle

    resp = await authed_client.patch("/api/v1/account", json={"handle": "new_handle"})
    assert resp.status_code == 400
    assert "cannot be changed" in resp.json()["detail"].lower()

    get_resp = await authed_client.get("/api/v1/account")
    assert get_resp.json()["handle"] == current_handle


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------


async def test_change_password_wrong_current_returns_400(
    authed_client: AsyncClient,
) -> None:
    resp = await authed_client.post(
        "/api/v1/account/password",
        json={"current_password": "wrong-password", "new_password": NEW_PASSWORD},
    )
    assert resp.status_code == 400


async def test_change_password_correct_then_new_password_logs_in_old_fails(
    authed_client: AsyncClient,
) -> None:
    resp = await authed_client.post(
        "/api/v1/account/password",
        json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert resp.status_code == 204

    authed_client.cookies.clear()
    new_login = await authed_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": NEW_PASSWORD},
    )
    assert new_login.status_code == 200

    authed_client.cookies.clear()
    old_login = await authed_client.post(
        "/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert old_login.status_code == 401


async def test_session_stays_valid_after_password_change(
    authed_client: AsyncClient,
) -> None:
    resp = await authed_client.post(
        "/api/v1/account/password",
        json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert resp.status_code == 204

    # Same cookie, no re-login: the JWT carries no password version.
    me_resp = await authed_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def test_delete_account_wrong_password_returns_400_and_user_persists(
    authed_client: AsyncClient, async_db: AsyncSession
) -> None:
    me = await authed_client.get("/api/v1/auth/me")
    user_id = uuid.UUID(me.json()["user_id"])

    resp = await authed_client.request(
        "DELETE", "/api/v1/account", json={"password": "wrong-password"}
    )
    assert resp.status_code == 400

    row = (await async_db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    assert row is not None


async def test_delete_account_correct_password_clears_cookie_and_cascades(
    authed_client: AsyncClient, async_db: AsyncSession
) -> None:
    me = await authed_client.get("/api/v1/auth/me")
    user_id = uuid.UUID(me.json()["user_id"])

    entry_resp = await authed_client.post(
        "/api/v1/entries", json={**_ENTRY_PAYLOAD, "date": "2026-07-01"}
    )
    assert entry_resp.status_code == 201
    entry_id = entry_resp.json()["id"]

    resp = await authed_client.request(
        "DELETE", "/api/v1/account", json={"password": TEST_PASSWORD}
    )
    assert resp.status_code == 204
    assert JWT_COOKIE_NAME not in authed_client.cookies

    me_after = await authed_client.get("/api/v1/auth/me")
    assert me_after.status_code == 401

    user_row = (await async_db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    assert user_row is None

    entry_row = (
        await async_db.execute(select(Entry).where(Entry.id == entry_id))
    ).scalar_one_or_none()
    assert entry_row is None


async def test_delete_refuses_default_storage_user(async_db: AsyncSession) -> None:
    """The seed/reference-catalog user can't be deleted -- new-user provisioning
    copies its catalogs (migration 022). HTTP login as that user isn't practical
    in this fixture setup, so this exercises the service directly (already the
    identity ``async_db`` authenticates as by default -- see conftest)."""
    default_id = uuid.UUID(settings.default_storage_user_id)
    known_password = "default-user-password"

    user = (await async_db.execute(select(User).where(User.id == default_id))).scalar_one()
    user.password_hash = hash_password(known_password)
    await async_db.commit()

    service = AccountService(async_db)
    with pytest.raises(ValidationError, match="cannot be deleted"):
        await service.delete(AccountDeleteRequest(password=known_password), Response())

    still_there = (
        await async_db.execute(select(User).where(User.id == default_id))
    ).scalar_one_or_none()
    assert still_there is not None


async def test_delete_account_purges_photo_files(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))

    me = await authed_client.get("/api/v1/auth/me")
    user_id = uuid.UUID(me.json()["user_id"])

    entry_resp = await authed_client.post(
        "/api/v1/entries", json={**_ENTRY_PAYLOAD, "date": "2026-07-02"}
    )
    assert entry_resp.status_code == 201
    entry_id = entry_resp.json()["id"]

    filename = "2026-07-02_photo-1.jpg"
    save_photo(b"fake-jpeg-bytes", filename, user_id=str(user_id))
    file_path = photo_dir / filename
    assert file_path.exists()

    async_db.add(
        Photo(
            user_id=user_id,
            entry_id=entry_id,
            filename=filename,
            original_filename="lunch.jpg",
            created_at=datetime.datetime.utcnow(),
        )
    )
    await async_db.commit()

    resp = await authed_client.request(
        "DELETE", "/api/v1/account", json={"password": TEST_PASSWORD}
    )
    assert resp.status_code == 204

    assert not file_path.exists()


async def test_delete_account_purges_remote_lab_attachments_only(
    authed_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lab attachments under the user's object-storage prefix are purged;
    absolute local paths survive (content-addressed, shared across users).
    The stub replaces the boto3 client -- the S3 trust boundary."""
    monkeypatch.setattr(settings, "bucket_name", "test-bucket")
    monkeypatch.setattr(settings, "aws_access_key_id", "test-key")
    monkeypatch.setattr(settings, "aws_secret_access_key", "test-secret")
    monkeypatch.setattr(settings, "aws_endpoint_url_s3", "http://storage.test")

    deleted_keys: list[str] = []

    class _StubS3:
        def delete_object(self, Bucket: str, Key: str) -> None:  # noqa: N803
            deleted_keys.append(Key)

    monkeypatch.setattr(object_storage, "_s3_client", lambda: _StubS3())

    me = await authed_client.get("/api/v1/auth/me")
    user_id = uuid.UUID(me.json()["user_id"])

    remote_key = f"{user_id}/lab_attachments/2026-07/abc123.pdf"
    local_path = "/var/data/lab_attachments/2026-07/def456.pdf"
    async_db.add_all(
        [
            Lab(
                user_id=user_id,
                lab_date=datetime.date(2026, 7, 1),
                name="Blood panel",
                type="blood",
                source_kind="upload",
                attachment_path=remote_key,
            ),
            Lab(
                user_id=user_id,
                lab_date=datetime.date(2026, 7, 2),
                name="Stool panel",
                type="stool",
                source_kind="upload",
                attachment_path=local_path,
            ),
        ]
    )
    await async_db.commit()

    resp = await authed_client.request(
        "DELETE", "/api/v1/account", json={"password": TEST_PASSWORD}
    )
    assert resp.status_code == 204

    assert deleted_keys == [remote_key]
