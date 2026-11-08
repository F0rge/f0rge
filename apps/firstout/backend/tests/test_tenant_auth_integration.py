from __future__ import annotations

import base64
import datetime
import json
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from sqlalchemy import select
from svix.webhooks import Webhook
from app.config import settings
from app.models.membership import Membership
from app.models.team import Team
from app.models.user import User
from app.models.clerk_webhook_event import ClerkWebhookEvent
from tests.conftest import OWNER_EMAIL, independent_request_sessions


async def test_signed_host_mismatch_preserves_permissions(owner_client):
    before = await owner_client.get("/api/v1/auth/me")
    assert before.status_code == 200
    mismatch = await owner_client.get(
        "/api/v1/auth/me", headers={"host": "other.app.firstout.co.za"}
    )
    assert mismatch.status_code == 403
    after = await owner_client.get("/api/v1/auth/me")
    assert after.status_code == 200
    assert before.json()["permissions"] == after.json()["permissions"]


async def test_clerk_membership_and_bad_bearer_never_falls_back(owner_client, async_db):
    from app.services.auth import JWT_COOKIE_NAME
    from tests.conftest import legacy_staff_token

    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    response = await owner_client.get("/api/v1/auth/me")
    assert response.status_code == 200 and "users.manage" in response.json()["permissions"]
    # Fixture's signed coarse org:member claim must preserve the local owner grant.
    owner_client.cookies.set(
        JWT_COOKIE_NAME, legacy_staff_token(user.id, token_version=user.token_version)
    )
    rejected = await owner_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer forged-token"}
    )
    assert rejected.status_code == 401
    assert (await owner_client.get("/api/v1/auth/me")).status_code == 200


async def test_disabled_user_rejected_by_clerk(owner_client, async_db):
    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    user.is_disabled = True
    await async_db.flush()
    assert (await owner_client.get("/api/v1/auth/me")).status_code == 401


@pytest.fixture
async def legacy_staff_in_two_organisations(owner_client, async_db):
    import uuid
    from tests.conftest import create_test_staff

    created = await create_test_staff(
        owner_client, email="cross-org-staff@example.com", role="buyer"
    )
    staff = await async_db.get(User, uuid.UUID(created["id"]))
    home = await async_db.get(Team, staff.team_id)
    other = Team(
        name="Independent organisation", slug="independent-org", clerk_org_id="org_cross_other"
    )
    async_db.add(other)
    await async_db.flush()
    async_db.add(
        Membership(
            user_id=staff.id,
            team_id=other.id,
            role="owner",
            is_legacy_home=False,
            is_disabled=False,
        )
    )
    await async_db.commit()
    return staff, home, other


async def test_home_disable_preserves_other_org_and_reenable(
    owner_client, async_db, legacy_staff_in_two_organisations
):
    from app.main import app
    from app.services.permissions import PermissionService
    from tests.conftest import signed_clerk_token

    staff, home, other = legacy_staff_in_two_organisations
    home_header = {
        "Authorization": "Bearer "
        + signed_clerk_token(staff.clerk_user_id, org_id=home.clerk_org_id, org_slug=home.slug)
    }
    other_header = {
        "Authorization": "Bearer "
        + signed_clerk_token(staff.clerk_user_id, org_id=other.clerk_org_id, org_slug=other.slug)
    }
    async with independent_request_sessions(async_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/v1/auth/me", headers=home_header)).status_code == 200
            disabled = await owner_client.patch(
                f"/api/v1/users/{staff.id}", json={"is_disabled": True}
            )
            assert disabled.status_code == 200 and disabled.json()["is_disabled"] is True
            await async_db.refresh(staff)
            member = await async_db.scalar(
                select(Membership).where(
                    Membership.user_id == staff.id, Membership.team_id == home.id
                )
            )
            assert member.is_disabled is True and staff.is_disabled is False
            assert await PermissionService(async_db).keys_for_user(staff.id) == []
            assert (await client.get("/api/v1/auth/me", headers=home_header)).status_code == 401
            other_me = await client.get("/api/v1/auth/me", headers=other_header)
            assert other_me.status_code == 200
            assert other_me.json()["team"]["id"] == str(other.id)
            assert "users.manage" in other_me.json()["permissions"]
            other_users = await client.get("/api/v1/users", headers=other_header)
            assert other_users.status_code == 200
            assert (
                next(row for row in other_users.json() if row["id"] == str(staff.id))["is_disabled"]
                is False
            )
            own_disable = await client.patch(
                f"/api/v1/users/{staff.id}", json={"is_disabled": True}, headers=other_header
            )
            assert own_disable.status_code == 409
            enabled = await owner_client.patch(
                f"/api/v1/users/{staff.id}", json={"is_disabled": False}
            )
            assert enabled.status_code == 200 and enabled.json()["is_disabled"] is False
            assert (await client.get("/api/v1/auth/me", headers=home_header)).status_code == 200
            assert (await client.get("/api/v1/auth/me", headers=other_header)).status_code == 200


async def test_org_reenable_cannot_clear_global_disabled_identity(
    owner_client, async_db, legacy_staff_in_two_organisations
):
    from app.main import app
    from app.services.permissions import PermissionService
    from tests.conftest import signed_clerk_token

    staff, home, other = legacy_staff_in_two_organisations
    member = await async_db.scalar(
        select(Membership).where(Membership.user_id == staff.id, Membership.team_id == home.id)
    )
    staff.is_disabled = True
    member.is_disabled = True
    await async_db.commit()
    async with independent_request_sessions(async_db):
        enabled = await owner_client.patch(f"/api/v1/users/{staff.id}", json={"is_disabled": False})
        assert enabled.status_code == 200 and enabled.json()["is_disabled"] is True
        await async_db.refresh(staff)
        await async_db.refresh(member)
        assert staff.is_disabled is True and member.is_disabled is False
        assert await PermissionService(async_db).keys_for_user(staff.id) == []
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for team in (home, other):
                token = signed_clerk_token(
                    staff.clerk_user_id, org_id=team.clerk_org_id, org_slug=team.slug
                )
                assert (
                    await client.get(
                        "/api/v1/auth/me", headers={"Authorization": "Bearer " + token}
                    )
                ).status_code == 401


async def test_signed_delete_webhook_is_idempotent_and_preserves_home(
    owner_client, async_db, monkeypatch
):
    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    home = await async_db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.is_legacy_home.is_(True))
    )
    secret = "whsec_" + base64.b64encode(b"synthetic-webhook-key").decode()
    monkeypatch.setattr(settings, "clerk_webhook_secret", secret)
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = json.dumps({"type": "organizationMembership.deleted", "data": {"id": "om_fake"}})
    headers = {
        "svix-id": "msg_synthetic_delete",
        "svix-timestamp": str(int(now.timestamp())),
        "svix-signature": Webhook(secret).sign("msg_synthetic_delete", now, payload),
        "content-type": "application/json",
    }
    first = await owner_client.post("/api/v1/webhooks/clerk", content=payload, headers=headers)
    assert first.status_code == 200
    second = await owner_client.post("/api/v1/webhooks/clerk", content=payload, headers=headers)
    assert second.json()["status"] == "duplicate"
    assert await async_db.get(Membership, home.id) is not None
    assert (await owner_client.get("/api/v1/auth/me")).status_code == 200
    forged = await owner_client.post(
        "/api/v1/webhooks/clerk", content=payload + " ", headers=headers
    )
    assert forged.status_code == 400
    assert await async_db.get(ClerkWebhookEvent, "msg_synthetic_delete") is not None


async def test_fake_provisioning_clones_roles_without_locations_or_home_changes(
    async_db, monkeypatch
):
    from app.services.tenant_provisioning import provision_tenant, provision_invited_membership
    from app.models.location import Location
    from app.models.role import Role
    from f0rge_db.organisation import tenant_id_ctx
    from types import SimpleNamespace
    from sqlalchemy import func

    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    user.clerk_user_id = "user_provision_owner"
    home = user.team_id
    provider = SimpleNamespace(create_organisation=AsyncMock(return_value="org_new_test"))
    monkeypatch.setattr(settings, "tenant_signup_enabled", True)
    token = tenant_id_ctx.set(None)
    try:
        team = await provision_tenant(
            async_db,
            owner=user,
            name="Synthetic tenant",
            slug="synthetic-tenant",
            provider=provider,
        )
        assert user.team_id == home
        assert team.clerk_org_id == "org_new_test"
        assert (
            await async_db.scalar(
                select(func.count()).select_from(Role).where(Role.team_id == team.id)
            )
            == 5
        )
        assert (
            await async_db.scalar(
                select(func.count()).select_from(Location).where(Location.team_id == team.id)
            )
            == 0
        )
        existing = await provision_invited_membership(
            async_db, user=user, team=team, clerk_role="org:member", local_role="till"
        )
        assert existing.role == "owner"  # A coarse event/invite can never demote.
    finally:
        tenant_id_ctx.reset(token)


async def test_legacy_trade_cookie_and_hs_bearer_are_rejected(owner_client, async_db):
    import uuid
    from app.models.customer_portal_user import CustomerPortalUser
    from app.services.customer_portal import CUSTOMER_COOKIE_NAME
    from tests.conftest import legacy_portal_token
    from f0rge_db.organisation import tenant_id_ctx

    customer = await owner_client.post(
        "/api/v1/customers", json={"name": "Synthetic retired trade", "customer_type": "trade"}
    )
    assert customer.status_code == 201
    portal = CustomerPortalUser(
        team_id=tenant_id_ctx.get(),
        customer_id=uuid.UUID(customer.json()["id"]),
        email="legacy-trade@example.com",
        password_hash="retained-unused-digest",
        is_disabled=False,
    )
    async_db.add(portal)
    await async_db.flush()
    token = legacy_portal_token(portal.id, team_id=portal.team_id)
    owner_client.headers.pop("Authorization", None)
    owner_client.cookies.clear()
    owner_client.cookies.set(CUSTOMER_COOKIE_NAME, token)
    assert (await owner_client.get("/api/v1/portal/me")).status_code == 401
    assert (await owner_client.get("/api/v1/auth/me")).status_code == 401
    owner_client.cookies.clear()
    assert (
        await owner_client.get("/api/v1/portal/me", headers={"Authorization": "Bearer " + token})
    ).status_code == 401


async def test_role_seed_does_not_reduce_existing_grants(async_db):
    from app.models.role import Role, RolePermission
    from app.services.roles import RoleSeedService

    role = await async_db.scalar(select(Role).where(Role.slug == "buyer"))
    role.permissions.append(RolePermission(role_id=role.id, key="till.sell"))
    await async_db.flush()
    await RoleSeedService(async_db).seed()
    await async_db.refresh(role, ["permissions"])
    assert "till.sell" in {permission.key for permission in role.permissions}


async def test_unknown_clerk_subject_cannot_link_existing_email(owner_client, async_db):
    from tests.conftest import signed_clerk_token

    user = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    team = await async_db.get(Team, user.team_id)
    original_subject = user.clerk_user_id
    unknown = signed_clerk_token(
        "user_unknown_subject", org_id=team.clerk_org_id, org_slug=team.slug, email=user.email
    )
    response = await owner_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer " + unknown}
    )
    assert response.status_code == 401
    assert user.clerk_user_id == original_subject
    assert (await owner_client.get("/api/v1/auth/me")).status_code == 200


@pytest.fixture(autouse=True)
def enforced_tenant_mode(monkeypatch):
    monkeypatch.setattr(settings, "tenant_isolation_mode", "enforced")
