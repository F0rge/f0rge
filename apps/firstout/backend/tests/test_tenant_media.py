"""Authenticated media bytes remain usable with fresh Clerk bearer tokens."""

from __future__ import annotations

import uuid
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from f0rge_db.organisation import tenant_id_ctx
from app.config import settings
from app.models.sku import Sku
from app.models.team import Team
from app.models.team_settings import TeamSettings
from app.models.user import User
from app.services import object_storage
from tests.conftest import OWNER_EMAIL, signed_clerk_token
from tests.test_settings_logo import _tiny_jpeg


@pytest.mark.parametrize("asset", ["sku", "logo"])
async def test_remote_media_returns_authenticated_bytes_without_redirect(
    owner_client, async_db, monkeypatch, asset
):
    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    team = await async_db.get(Team, user.team_id)
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
        if team_settings is None:
            team_settings = TeamSettings(team_id=team.id)
            async_db.add(team_settings)
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
    owner_client.cookies.clear()
    owner_client.headers.pop("Authorization", None)
    response = await owner_client.get(
        endpoint,
        headers={
            "Authorization": "Bearer "
            + signed_clerk_token(user.clerk_user_id, org_id=team.clerk_org_id, org_slug=team.slug)
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.content == image
    assert response.headers["content-type"].startswith("image/jpeg")
    assert "location" not in response.headers
    remote.assert_called_once_with(key)
    assert (await owner_client.get(endpoint)).status_code == 401
    remote.assert_called_once_with(key)


@pytest.fixture(autouse=True)
def enforced_tenant_mode(monkeypatch):
    monkeypatch.setattr(settings, "tenant_isolation_mode", "enforced")
