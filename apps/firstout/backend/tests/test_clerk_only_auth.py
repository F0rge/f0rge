from __future__ import annotations

import uuid

from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.models.team import Team
from app.services.auth import JWT_COOKIE_NAME
from tests.conftest import legacy_staff_token
from tests.conftest import OWNER_EMAIL, OWNER_PASSWORD, authenticate_as, signed_clerk_token


async def test_staff_password_and_old_sessions_are_never_authentication(async_client, async_db):
    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    old = legacy_staff_token(user.id, 1, token_version=user.token_version)
    before = (user.password_hash, user.token_version)
    for path, body in [
        ("/api/v1/auth/login", {"email": OWNER_EMAIL, "password": OWNER_PASSWORD}),
        ("/api/v1/auth/forgot-password", {"email": OWNER_EMAIL}),
        (
            "/api/v1/auth/reset-password",
            {
                "token": "owned-old-token",
                "password": "new-password",
                "password_confirm": "new-password",
            },
        ),
    ]:
        response = await async_client.post(path, json=body)
        assert response.status_code == 400 and "Clerk" in response.json()["detail"]
        assert "set-cookie" not in response.headers
    async_client.cookies.set(JWT_COOKIE_NAME, old)
    assert (await async_client.get("/api/v1/auth/me")).status_code == 401
    assert (
        await async_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + old})
    ).status_code == 401
    await async_db.refresh(user)
    assert (user.password_hash, user.token_version) == before


async def test_clerk_unavailable_does_not_restore_legacy_login(async_client, async_db, monkeypatch):
    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    old = legacy_staff_token(user.id, 1)
    monkeypatch.setattr(settings, "clerk_enabled", False)
    async_client.cookies.set(JWT_COOKIE_NAME, old)
    for headers in ({}, {"Authorization": "Bearer " + old}):
        assert (await async_client.get("/api/v1/auth/me", headers=headers)).status_code == 401
    assert (
        await async_client.post(
            "/api/v1/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}
        )
    ).status_code == 400


async def test_clerk_subject_preserves_local_owner_without_email_authority(owner_client, async_db):
    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    # A coarse provider role and an unrelated token email cannot rewrite or
    # transfer the exact subject/UUID link or the existing local owner grants.
    team = await async_db.get(Team, user.team_id)
    token = signed_clerk_token(
        user.clerk_user_id,
        org_id=team.clerk_org_id,
        org_slug=team.slug,
        email="changed-at-provider@example.com",
    )
    response = await owner_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer " + token}
    )
    assert response.status_code == 200
    assert "users.manage" in response.json()["permissions"]
    unknown = signed_clerk_token(
        "user_unlinked_" + uuid.uuid4().hex,
        org_id=team.clerk_org_id,
        org_slug=team.slug,
        email=OWNER_EMAIL,
    )
    assert (
        await owner_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + unknown})
    ).status_code == 401


async def test_local_account_credentials_cannot_change_or_issue_session(owner_client, async_db):
    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    before = (user.email, user.password_hash, user.token_version)
    for path in ("/api/v1/profile", "/api/v1/users/" + str(user.id)):
        for body in ({"email": "should-not-apply@example.com"}, {"password": "should-not-apply"}):
            assert (await owner_client.patch(path, json=body)).status_code == 422
    changed = await owner_client.patch("/api/v1/profile", json={"display_name": "Local preference"})
    assert changed.status_code == 200 and "set-cookie" not in changed.headers
    await async_db.refresh(user)
    assert (user.email, user.password_hash, user.token_version) == before
    assert (await authenticate_as(owner_client, OWNER_EMAIL)).status_code == 200


async def test_only_active_no_org_sessions_can_reach_onboarding(async_client, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.dependencies.tenant_signup import get_clerk_api
    from app.main import app

    remote = SimpleNamespace(
        user=AsyncMock(
            return_value={
                "id": "user_onboarding",
                "primary_email_address_id": "email_verified",
                "email_addresses": [
                    {
                        "id": "email_verified",
                        "email_address": "onboarding@example.com",
                        "verification": {"status": "verified"},
                    }
                ],
            }
        ),
        memberships_for_user=AsyncMock(return_value=[]),
    )
    app.dependency_overrides[get_clerk_api] = lambda: remote
    monkeypatch.setattr(settings, "tenant_signup_enabled", True)
    try:
        pending = signed_clerk_token("user_onboarding", status="pending")
        response = await async_client.get(
            "/api/v1/tenant-signup/me", headers={"Authorization": "Bearer " + pending}
        )
        assert response.status_code == 401
        remote.user.assert_not_called()
        active = signed_clerk_token("user_onboarding", status="active")
        response = await async_client.get(
            "/api/v1/tenant-signup/me", headers={"Authorization": "Bearer " + active}
        )
        assert response.status_code == 200 and response.json()["organisations"] == []
    finally:
        app.dependency_overrides.pop(get_clerk_api, None)
