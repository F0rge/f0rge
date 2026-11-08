from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.models.account import Account
from app.models.location import Location
from app.models.membership import Membership
from app.models.role import Role
from app.models.team import Team
from app.models.team_settings import TeamSettings
from app.models.tenant_onboarding import TenantProvisioningAttempt
from app.models.user import User
from app.schemas.tenant_signup import OrganisationInvitationCreate, SignupIntent
from app.services.clerk import ClerkSession
from app.services.staff_identity import StaffIdentity, staff_identity_ctx
from app.services.tenant_signup import OrganisationService, TenantSignupService
from f0rge_core.exceptions import ConflictError, ValidationError
from f0rge_db.organisation import tenant_id_ctx


@pytest.fixture(autouse=True)
def signup_enabled(monkeypatch):
    monkeypatch.setattr(settings, "tenant_signup_enabled", True)
    monkeypatch.setattr(settings, "tenant_isolation_mode", "enforced")
    monkeypatch.setattr(settings, "clerk_enabled", True)
    monkeypatch.setattr(settings, "public_app_url", "https://app.firstout.co.za")
    monkeypatch.setattr(settings, "clerk_secret_key", "")


def profile(subject="user_new", email="new-business-owner@example.com"):
    return {
        "id": subject,
        "first_name": "New",
        "last_name": "Owner",
        "primary_email_address_id": "em_verified",
        "email_addresses": [
            {"id": "em_verified", "email_address": email, "verification": {"status": "verified"}},
        ],
    }


def provider(subject="user_new", email="new-business-owner@example.com"):
    return SimpleNamespace(
        user=AsyncMock(return_value=profile(subject, email)),
        ensure_organisation=AsyncMock(return_value="org_new_business"),
        memberships_for_user=AsyncMock(return_value=[]),
        members=AsyncMock(return_value=[]),
        invite=AsyncMock(return_value={"id": "orginv_new"}),
        revoke_invitation=AsyncMock(),
    )


async def test_no_org_signup_is_idempotent_and_bootstraps_empty_business(async_db):
    remote = provider()
    service = TenantSignupService(async_db, remote)
    token = tenant_id_ctx.set(None)
    try:
        body = SignupIntent(name="New business", slug="new-business", location_name="My showroom")
        first = await service.create(ClerkSession("user_new"), body)
        second = await service.create(ClerkSession("user_new"), body)
        assert first == second
        remote.ensure_organisation.assert_awaited_once()
        assert first["url"] == "https://app.firstout.co.za/"
        team_id = first["id"]
        assert (
            await async_db.scalar(
                select(func.count()).select_from(Role).where(Role.team_id == team_id)
            )
            == 5
        )
        assert (
            await async_db.scalar(
                select(func.count()).select_from(Account).where(Account.team_id == team_id)
            )
            > 20
        )
        location = await async_db.scalar(select(Location).where(Location.team_id == team_id))
        assert location.name == "My showroom"
        company = await async_db.scalar(select(TeamSettings).where(TeamSettings.team_id == team_id))
        assert company.legal_name == "New business"
        assert company.address == "" and company.vat_number == ""
        user = await async_db.scalar(select(User).where(User.clerk_user_id == "user_new"))
        assert user.password_hash == "!clerk-only"
        assert (
            await async_db.scalar(
                select(Membership.role).where(
                    Membership.user_id == user.id, Membership.team_id == team_id
                )
            )
            == "owner"
        )
    finally:
        tenant_id_ctx.reset(token)


async def test_new_organisation_can_save_and_clear_optional_business_details(
    async_client, async_db, monkeypatch
):
    from app.services.clerk import ClerkIdentity
    from tests.conftest import independent_request_sessions

    token = tenant_id_ctx.set(None)
    try:
        team = await TenantSignupService(async_db, provider()).create(
            ClerkSession("user_new"), SignupIntent(name="New business", slug="settings-business")
        )
    finally:
        tenant_id_ctx.reset(token)
    monkeypatch.setattr(
        "app.middleware.auth.verify_clerk_token",
        AsyncMock(
            return_value=ClerkIdentity("user_new", "org_new_business", team["slug"], "member")
        ),
    )
    headers = {"Authorization": "Bearer synthetic-business-settings-token"}
    async with independent_request_sessions(async_db):
        initial = await async_client.get("/api/v1/settings", headers=headers)
        assert initial.status_code == 200
        assert initial.json()["address"] == initial.json()["vat_number"] == ""
        saved = await async_client.patch(
            "/api/v1/settings",
            headers=headers,
            json={
                "legal_name": "New legal business",
                "trading_name": "New trading business",
                "address": "Synthetic business address",
                "vat_number": "",
            },
        )
        assert saved.status_code == 200 and saved.json()["vat_number"] == ""
        persisted = await async_client.get("/api/v1/settings", headers=headers)
        assert persisted.status_code == 200
        assert persisted.json()["legal_name"] == "New legal business"
        assert persisted.json()["address"] == "Synthetic business address"
        assert persisted.json()["vat_number"] == ""

        populated = await async_client.patch(
            "/api/v1/settings", headers=headers, json={"vat_number": "4123456789"}
        )
        assert populated.status_code == 200 and populated.json()["vat_number"] == "4123456789"
        cleared = await async_client.patch(
            "/api/v1/settings", headers=headers, json={"address": "", "vat_number": ""}
        )
        assert cleared.status_code == 200
        persisted = await async_client.get("/api/v1/settings", headers=headers)
        assert persisted.status_code == 200
        assert persisted.json()["address"] == persisted.json()["vat_number"] == ""
        assert persisted.json()["legal_name"] == "New legal business"
        blank_name = await async_client.patch(
            "/api/v1/settings",
            headers=headers,
            json={"legal_name": "", "address": "", "vat_number": ""},
        )
        assert blank_name.status_code == 422
        assert [error["loc"] for error in blank_name.json()["detail"]] == [["body", "legal_name"]]


async def test_signup_rejects_existing_email_without_immutable_clerk_link(async_db):
    existing = await async_db.scalar(select(User).limit(1))
    remote = provider(email=existing.email)
    with pytest.raises(ConflictError, match="existing staff account"):
        await TenantSignupService(async_db, remote).create(
            ClerkSession("user_unlinked"), SignupIntent(name="Attack", slug="cannot-link-existing")
        )
    remote.ensure_organisation.assert_not_called()
    assert existing.clerk_user_id is None


async def test_signup_rejects_unverified_primary_email_before_side_effect(async_db):
    remote = provider()
    remote.user.return_value["email_addresses"][0]["verification"]["status"] = "unverified"
    with pytest.raises(ValidationError, match="Verify your primary"):
        await TenantSignupService(async_db, remote).create(
            ClerkSession("user_new"), SignupIntent(name="Unverified", slug="unverified")
        )
    remote.ensure_organisation.assert_not_called()


async def test_signup_attempt_is_persisted_before_provider_failure(async_db):
    remote = provider()
    remote.ensure_organisation.side_effect = RuntimeError("synthetic provider timeout")
    body = SignupIntent(name="Retry", slug="retry-business")
    service = TenantSignupService(async_db, remote)
    with pytest.raises(RuntimeError):
        await service.create(ClerkSession("user_new"), body)
    attempt = await async_db.scalar(
        select(TenantProvisioningAttempt).where(TenantProvisioningAttempt.slug == body.slug)
    )
    assert attempt.clerk_user_id == "user_new"
    assert attempt.result_team_id is None
    with pytest.raises(ConflictError, match="another signup"):
        await service.create(ClerkSession("user_other"), body)


async def test_bootstrap_failure_keeps_external_org_for_safe_retry(async_db):
    from sqlalchemy.exc import IntegrityError
    from f0rge_db.crud import unit_of_work

    remote = provider(email="retry-bootstrap@example.com")
    service = TenantSignupService(async_db, remote)
    collision_id = None

    async def create_provider_org(**kwargs):
        nonlocal collision_id
        # A real DB uniqueness failure after the remote side effect succeeds.
        collision = Team(
            name="Synthetic conflicting mapping",
            slug="conflicting-mapping",
            clerk_org_id="org_new_business",
        )
        async_db.add(collision)
        await async_db.flush()
        collision_id = collision.id
        return "org_new_business"

    remote.ensure_organisation.side_effect = create_provider_org
    body = SignupIntent(name="Bootstrap", slug="retry-bootstrap")
    token = tenant_id_ctx.set(None)
    try:
        with pytest.raises(IntegrityError):
            await service.create(ClerkSession("user_bootstrap"), body)
        attempt = await async_db.scalar(
            select(TenantProvisioningAttempt).where(TenantProvisioningAttempt.slug == body.slug)
        )
        assert attempt.clerk_org_id == "org_new_business"
        assert attempt.result_team_id is None
        assert await async_db.scalar(select(Team.id).where(Team.slug == body.slug)) is None
        # A failed transaction's session remains pinned; a retry is a fresh request.
        async_db.info.clear()
        async with unit_of_work(async_db):
            await async_db.delete(await async_db.get(Team, collision_id))
        result = await service.create(ClerkSession("user_bootstrap"), body)
        assert result["clerk_org_id"] == "org_new_business"
        remote.ensure_organisation.assert_awaited_once()
    finally:
        tenant_id_ctx.reset(token)


async def test_invitation_cap_role_validation_revoke_and_idempotency(owner_client, async_db):
    from tests.conftest import OWNER_EMAIL

    owner = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    owner.clerk_user_id = "user_owner"
    team = await async_db.get(Team, owner.team_id)
    team.clerk_org_id = "org_home"
    await async_db.flush()
    from f0rge_db.crud import unit_of_work

    async with unit_of_work(async_db):
        pass
    identity = StaffIdentity(owner.id, team.id, team.name, team.slug, "owner", None, True)
    token = staff_identity_ctx.set(identity)
    try:
        remote = provider()
        service = OrganisationService(async_db, remote)
        with pytest.raises(ValidationError, match="existing Firstout role"):
            await service.invite(
                OrganisationInvitationCreate(email="staff-new@example.com", role="unknown-role")
            )
        # Role seed has five existing role accounts plus owner: cap must refuse.
        remote.members.return_value = [{"id": str(index)} for index in range(5)]
        with pytest.raises(ValidationError, match="supports 5 staff"):
            await service.invite(
                OrganisationInvitationCreate(email="staff-new@example.com", role="till")
            )
    finally:
        staff_identity_ctx.reset(token)


async def test_business_apis_still_reject_unknown_clerk_subject(async_client, monkeypatch):
    from app.services.clerk import ClerkIdentity

    monkeypatch.setattr(
        "app.middleware.auth.verify_clerk_token",
        AsyncMock(return_value=ClerkIdentity("unknown_new", "org_new", "new", "admin")),
    )
    response = await async_client.get(
        "/api/v1/locations", headers={"Authorization": "Bearer verified-but-unprovisioned"}
    )
    assert response.status_code == 401


async def test_revoked_invite_can_be_reissued_with_a_new_marker_and_role(async_db):
    from app.models.tenant_onboarding import TenantInvitation
    from app.permissions import ROLE_PRESETS, ROLE_PRESET_NAMES
    from app.models.role import RolePermission
    from f0rge_db.organisation import apply_tenant_context
    from f0rge_db.crud import unit_of_work

    team = Team(name="Invite lifecycle", slug="invite-lifecycle", clerk_org_id="org_lifecycle")
    async_db.add(team)
    await async_db.flush()
    await apply_tenant_context(async_db, team.id)
    tenant_token = tenant_id_ctx.set(team.id)
    try:
        owner = User(
            team_id=team.id,
            email="lifecycle-owner@example.com",
            clerk_user_id="user_lifecycle",
            password_hash="!clerk-only",
            role="owner",
        )
        async_db.add(owner)
        await async_db.flush()
        async_db.add(
            Membership(
                team_id=team.id,
                user_id=owner.id,
                role="owner",
                is_legacy_home=False,
                is_disabled=False,
            )
        )
        for slug, keys in ROLE_PRESETS.items():
            async_db.add(
                Role(
                    team_id=team.id,
                    slug=slug,
                    name=ROLE_PRESET_NAMES[slug],
                    is_system=True,
                    is_owner_preset=slug == "owner",
                    permissions=[RolePermission(team_id=team.id, key=key) for key in keys],
                )
            )
        async with unit_of_work(async_db):
            pass
        identity_token = staff_identity_ctx.set(
            StaffIdentity(owner.id, team.id, team.name, team.slug, "owner", None, True)
        )
        try:
            remote = provider()
            service = OrganisationService(async_db, remote)
            first = await service.invite(
                OrganisationInvitationCreate(email="new-invite@example.com", role="till")
            )
            duplicate = await service.invite(
                OrganisationInvitationCreate(email="new-invite@example.com", role="till")
            )
            assert duplicate == first
            remote.invite.assert_awaited_once()
            await service.revoke(first["id"])
            remote.revoke_invitation.assert_awaited_once_with(
                team.clerk_org_id, "orginv_new", owner.clerk_user_id
            )
            second = await service.invite(
                OrganisationInvitationCreate(email="new-invite@example.com", role="buyer")
            )
            assert second["id"] != first["id"]
            assert second["role"] == "buyer" and second["status"] == "pending"
            original = await async_db.get(TenantInvitation, first["id"])
            assert original.status == "revoked"
            assert remote.invite.await_count == 2
        finally:
            staff_identity_ctx.reset(identity_token)
    finally:
        tenant_id_ctx.reset(tenant_token)


async def test_staff_import_dryrun_and_all_seven_legacy_users_keep_hashes_and_roles(
    async_db, monkeypatch
):
    from app.services.auth import hash_password
    from app.services.staff_import import StaffImportService

    users = list(await async_db.scalars(select(User).where(User.role != "system")))
    team_id = users[0].team_id
    count_before = len(users)
    for index in range(7 - count_before):
        async_db.add(
            User(
                team_id=team_id,
                email=f"extra-legacy-{index}@example.com",
                password_hash=hash_password("preserved-password"),
                role="owner",
            )
        )
    await async_db.flush()
    users = list(
        await async_db.scalars(select(User).where(User.team_id == team_id, User.role != "system"))
    )
    before = {
        user.id: (user.password_hash, user.role, user.token_version, user.is_disabled)
        for user in users
    }
    remote_users = {}

    async def create(payload):
        key = "user_" + payload["external_id"]
        remote_users[key] = {"id": key, "external_id": payload["external_id"]}
        return key

    remote = SimpleNamespace(
        create_user=AsyncMock(side_effect=create),
        user=AsyncMock(side_effect=lambda subject: remote_users[subject]),
        ensure_organisation=AsyncMock(return_value="org_legacy_seven"),
        ban_user=AsyncMock(),
        create_membership=AsyncMock(),
    )
    service = StaffImportService(async_db, remote)
    preview = await service.run(team_id)
    assert preview["dry_run"] and preview["staff_count"] == 7
    remote.create_user.assert_not_called()
    monkeypatch.setattr(settings, "clerk_import_enabled", True)
    report = await service.run(team_id, commit=True)
    assert report["imported_count"] == 7
    assert remote.ensure_organisation.call_args.kwargs["max_members"] == 7
    imported = {str(user.id): user for user in users}
    # Includes the initial owner creation before organisation creation, then all
    # seven member imports. Both paths must satisfy required-username instances.
    payloads = [call.args[0] for call in remote.create_user.call_args_list]
    assert len(payloads) == 8
    for payload in payloads:
        original = imported[payload["external_id"]]
        assert payload["username"] == "fo_" + original.id.hex
        assert payload["email_address"] == [original.email]
        assert payload["password_digest"] == before[original.id][0]
        assert payload["password_hasher"] == "bcrypt"
    assert payloads[0] == next(
        payload for payload in payloads[1:] if payload["external_id"] == payloads[0]["external_id"]
    )
    for user in users:
        assert (user.password_hash, user.role, user.token_version, user.is_disabled) == before[
            user.id
        ]
        assert user.clerk_user_id == "user_" + str(user.id)


async def test_clerk_only_home_staff_role_and_disabled_changes_are_membership_scoped(async_db):
    from app.schemas.user import UserUpdate
    from app.services.permissions import PermissionService
    from app.services.users import UserService
    from f0rge_db.crud import unit_of_work

    remote = provider(email="role-owner@example.com")
    token = tenant_id_ctx.set(None)
    try:
        team = await TenantSignupService(async_db, remote).create(
            ClerkSession("user_role_owner"),
            SignupIntent(name="Role business", slug="role-business"),
        )
        tenant_id_ctx.set(team["id"])
        staff = User(
            team_id=team["id"],
            email="role-staff@example.com",
            clerk_user_id="user_role_staff",
            password_hash="!clerk-only",
            role="buyer",
        )
        async_db.add(staff)
        await async_db.flush()
        membership = Membership(
            team_id=team["id"],
            user_id=staff.id,
            role="buyer",
            is_legacy_home=False,
            is_disabled=False,
        )
        async_db.add(membership)
        async with unit_of_work(async_db):
            pass
        assert "po.raise" in await PermissionService(async_db).keys_for_user(staff.id)
        await UserService(async_db).update(staff.id, UserUpdate(role="till"))
        assert membership.role == "till"
        assert "po.raise" not in await PermissionService(async_db).keys_for_user(staff.id)
        assert "till.sell" in await PermissionService(async_db).keys_for_user(staff.id)
        await UserService(async_db).update(staff.id, UserUpdate(is_disabled=True))
        assert membership.is_disabled is True
        assert staff.is_disabled is False  # One business cannot disable the global identity.
        assert await PermissionService(async_db).keys_for_user(staff.id) == []
    finally:
        tenant_id_ctx.reset(token)


async def test_clerk_enabled_legacy_create_user_cannot_bypass_verified_invitation(owner_client):
    response = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "unverified-reservation@example.com",
            "password": "synthetic-password",
            "role": "buyer",
        },
    )
    assert response.status_code == 400
    assert "Invite staff" in response.json()["detail"]


async def test_no_org_me_route_accepts_only_signed_identity_boundary(async_client, monkeypatch):
    from app.dependencies.tenant_signup import get_clerk_api
    from app.main import app

    remote = provider()
    app.dependency_overrides[get_clerk_api] = lambda: remote
    monkeypatch.setattr(
        "app.dependencies.tenant_signup.verify_clerk_session",
        AsyncMock(return_value=ClerkSession("user_new")),
    )
    try:
        response = await async_client.get(
            "/api/v1/tenant-signup/me", headers={"Authorization": "Bearer pending-signed-session"}
        )
        assert response.status_code == 200
        assert response.json()["email"] == "new-business-owner@example.com"
        assert response.json()["organisations"] == []
        assert (await async_client.get("/api/v1/tenant-signup/me")).status_code == 401
    finally:
        app.dependency_overrides.pop(get_clerk_api, None)


@pytest.mark.parametrize("billing_disabled", [True, False])
async def test_existing_org_selection_works_when_creation_is_disabled(
    async_client, async_db, monkeypatch, billing_disabled
):
    from app.dependencies.tenant_signup import get_clerk_api
    from app.main import app
    from tests.conftest import OWNER_EMAIL

    owner = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    owner.clerk_user_id = "user_existing_selection"
    team = await async_db.get(Team, owner.team_id)
    team.clerk_org_id = "org_existing_selection"
    await async_db.flush()
    remote = provider(subject=owner.clerk_user_id, email=owner.email)
    app.dependency_overrides[get_clerk_api] = lambda: remote
    monkeypatch.setattr(settings, "tenant_signup_enabled", False)
    monkeypatch.setattr(settings, "billing_disabled", billing_disabled)
    monkeypatch.setattr(
        "app.dependencies.tenant_signup.verify_clerk_session",
        AsyncMock(return_value=ClerkSession(owner.clerk_user_id)),
    )
    headers = {"Authorization": "Bearer existing-signed-session"}
    try:
        response = await async_client.get("/api/v1/tenant-signup/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["organisations"][0]["id"] == str(team.id)
        assert (await async_client.get("/api/v1/tenant-signup/me")).status_code == 401
        for path in ("/api/v1/tenant-signup", "/api/v1/tenant-signup/preview"):
            blocked = await async_client.post(
                path, headers=headers, json={"name": "Blocked business", "slug": "blocked-business"}
            )
            assert blocked.status_code == 400
        remote.ensure_organisation.assert_not_called()

        remote.user.return_value["email_addresses"][0]["verification"]["status"] = "unverified"
        assert (
            await async_client.get("/api/v1/tenant-signup/me", headers=headers)
        ).status_code == 400
        remote.user.return_value["email_addresses"][0]["verification"]["status"] = "verified"
        owner.is_disabled = True
        await async_db.flush()
        assert (
            await async_client.get("/api/v1/tenant-signup/me", headers=headers)
        ).status_code == 401
    finally:
        app.dependency_overrides.pop(get_clerk_api, None)


async def test_canonical_webhook_state_wins_over_event_order_and_preserves_home(
    async_client, async_db, monkeypatch
):
    import base64
    import datetime
    import json
    from svix.webhooks import Webhook
    from app.dependencies.tenant_signup import get_clerk_api
    from app.main import app
    from f0rge_db.crud import unit_of_work

    user = await async_db.scalar(select(User).limit(1))
    user.clerk_user_id = "user_webhook"
    home = await async_db.get(Team, user.team_id)
    home.clerk_org_id = "org_webhook_home"
    other = Team(name="Other membership", slug="webhook-other", clerk_org_id="org_webhook_other")
    async_db.add(other)
    await async_db.flush()
    member = Membership(
        team_id=other.id, user_id=user.id, role="buyer", is_legacy_home=False, is_disabled=False
    )
    async_db.add(member)
    async with unit_of_work(async_db):
        pass
    secret = "whsec_" + base64.b64encode(b"synthetic-canonical-hook-key").decode()
    monkeypatch.setattr(settings, "clerk_webhook_secret", secret)
    monkeypatch.setattr(settings, "clerk_webhook_reconcile_enabled", True)
    remote = provider()
    remote.membership = AsyncMock(return_value={"id": "om_live"})
    app.dependency_overrides[get_clerk_api] = lambda: remote

    async def send(event_id, kind, org):
        now = datetime.datetime.now(datetime.timezone.utc)
        payload = json.dumps(
            {
                "type": kind,
                "data": {
                    "organization": {"id": org},
                    "public_user_data": {"user_id": user.clerk_user_id},
                },
            }
        )
        return await async_client.post(
            "/api/v1/webhooks/clerk",
            content=payload,
            headers={
                "svix-id": event_id,
                "svix-timestamp": str(int(now.timestamp())),
                "svix-signature": Webhook(secret).sign(event_id, now, payload),
                "content-type": "application/json",
            },
        )

    try:
        response = await send(
            "msg_old_delete", "organizationMembership.deleted", other.clerk_org_id
        )
        assert response.status_code == 200 and response.json()["status"] == "processed"
        assert (
            not member.is_disabled
        )  # Stale deletion cannot revoke an existing provider membership.
        remote.membership.return_value = None
        response = await send(
            "msg_new_delete", "organizationMembership.updated", other.clerk_org_id
        )
        assert response.status_code == 200
        assert member.is_disabled
        response = await send(
            "msg_home_delete", "organizationMembership.deleted", home.clerk_org_id
        )
        assert response.status_code == 200
        local_home = await async_db.scalar(
            select(Membership).where(Membership.user_id == user.id, Membership.team_id == home.id)
        )
        assert local_home.is_legacy_home and not local_home.is_disabled
        duplicate = await send(
            "msg_home_delete", "organizationMembership.deleted", home.clerk_org_id
        )
        assert duplicate.json()["status"] == "duplicate"
        assert not user.is_disabled
    finally:
        app.dependency_overrides.pop(get_clerk_api, None)
