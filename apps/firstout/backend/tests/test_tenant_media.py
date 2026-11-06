"""Authenticated media bytes remain usable with fresh Clerk bearer tokens."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select
from f0rge_db.organisation import tenant_id_ctx
from app.config import settings
from app.models.sku import Sku
from app.models.team import Team
from app.models.team_settings import TeamSettings
from app.models.user import User
from app.services.clerk import ClerkIdentity
from app.services import object_storage
from tests.conftest import OWNER_EMAIL
from tests.test_settings_logo import _tiny_jpeg


@pytest.mark.parametrize("asset", ["sku", "logo"])
async def test_remote_media_returns_authenticated_bytes_without_redirect(
    owner_client, async_db, monkeypatch, asset
):
    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    team = await async_db.get(Team, user.team_id)
    user.clerk_user_id = "user_media_synthetic"
    team.clerk_org_id = "org_media_synthetic"
    key = f"tenants/{team.id}/synthetic/{asset}.jpg"
    if asset == "sku":
        created = await owner_client.post(
            "/api/v1/skus",
            json={
                "our_ref": "MEDIA-REMOTE",
                "our_barcode": "MEDIA-REMOTE",
                "name": "Synthetic media SKU",
                "design": "Synthetic media design",
                "fabric": "Synthetic media fabric",
            },
        )
        assert created.status_code == 201
        sku = await async_db.get(Sku, uuid.UUID(created.json()["id"]))
        sku.photo_storage_key = key
        endpoint = f"/api/v1/skus/{sku.id}/photo"
    else:
        team_settings = await async_db.scalar(
            select(TeamSettings).where(TeamSettings.team_id == team.id)
        )
        team_settings.logo_storage_key = key
        endpoint = "/api/v1/settings/logo"
    await async_db.flush()
    image = _tiny_jpeg()

    def read_remote(storage_key):
        assert storage_key == key
        # asyncio.to_thread must carry request organisation context to storage.
        assert tenant_id_ctx.get() == team.id
        return image

    remote = Mock(side_effect=read_remote)
    monkeypatch.setattr(settings, "bucket_name", "synthetic-media-bucket")
    monkeypatch.setattr(settings, "aws_access_key_id", "synthetic-only-id")
    monkeypatch.setattr(settings, "aws_secret_access_key", "synthetic-only-secret")
    monkeypatch.setattr(settings, "aws_endpoint_url_s3", "https://storage.synthetic.invalid")
    assert object_storage.is_remote_storage_ref(key)
    monkeypatch.setattr(object_storage._storage, "read_bytes", remote)
    monkeypatch.setattr(
        object_storage._storage,
        "presigned_get_url",
        Mock(side_effect=AssertionError("Media must not redirect to S3")),
    )
    monkeypatch.setattr(
        "app.middleware.auth.verify_clerk_token",
        AsyncMock(
            return_value=ClerkIdentity(user.clerk_user_id, team.clerk_org_id, team.slug, "member")
        ),
    )
    owner_client.cookies.clear()
    response = await owner_client.get(
        endpoint,
        headers={"Authorization": "Bearer synthetic-fresh-media-token"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.content == image
    assert response.headers["content-type"].startswith("image/jpeg")
    assert "location" not in response.headers
    remote.assert_called_once_with(key)
    assert (await owner_client.get(endpoint)).status_code == 401
    remote.assert_called_once_with(key)
