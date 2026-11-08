from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import pytest
from sqlalchemy import func, select

from app.dependencies.tenant_signup import get_clerk_api
from app.main import app
from app.models.customer_portal_user import CustomerPortalUser
from app.models.membership import Membership
from app.models.portal_identity import PortalAccess, PortalInvitation
from app.models.user import User
from app.services.customer_portal import CUSTOMER_COOKIE_NAME
from tests.conftest import legacy_portal_token
from tests.conftest import independent_request_sessions, signed_clerk_token


@pytest.fixture
async def portal_provider():
    remote = SimpleNamespace(
        user=AsyncMock(
            return_value={
                "id": "user_customer",
                "primary_email_address_id": "email_verified",
                "email_addresses": [
                    {
                        "id": "email_verified",
                        "email_address": "customer@example.com",
                        "verification": {"status": "verified"},
                    }
                ],
            }
        )
    )
    app.dependency_overrides[get_clerk_api] = lambda: remote
    try:
        yield remote
    finally:
        app.dependency_overrides.pop(get_clerk_api, None)


async def invitation(client, *, email="customer@example.com", name="Approved trade customer"):
    customer = await client.post("/api/v1/customers", json={"name": name, "customer_type": "trade"})
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    response = await client.post(
        f"/api/v1/customers/{customer_id}/portal-invitations", json={"email": email}
    )
    assert response.status_code == 201
    data = response.json()
    url = urlsplit(data["invitation_url"])
    assert not url.query and url.fragment.startswith("token=")
    return customer_id, data, url.fragment.split("=", 1)[1]


def personal_headers(subject="user_customer", access=None, **claims):
    headers = {"Authorization": "Bearer " + signed_clerk_token(subject, **claims)}
    if access:
        headers["X-Firstout-Portal-Access"] = str(access)
    return headers


async def test_customer_enrollment_is_scoped_one_use_and_creates_no_staff(
    owner_client, async_db, portal_provider
):
    before = (
        await async_db.scalar(select(func.count()).select_from(User)),
        await async_db.scalar(select(func.count()).select_from(Membership)),
    )
    async with independent_request_sessions(async_db):
        customer_id, invite, raw = await invitation(owner_client)
        accepted = await owner_client.post(
            "/api/v1/portal/invitations/accept", headers=personal_headers(), json={"token": raw}
        )
        assert accepted.status_code == 201
        access = accepted.json()
        assert access["customer_id"] == customer_id
        headers = personal_headers(access=access["id"])
        me = await owner_client.get("/api/v1/portal/me", headers=headers)
        assert me.status_code == 200 and me.json()["customer_id"] == customer_id
        assert (
            await owner_client.get("/api/v1/portal/catalogue", headers=headers)
        ).status_code == 200
        assert (await owner_client.get("/api/v1/portal/orders", headers=headers)).json() == []
        assert (await owner_client.get("/api/v1/auth/me", headers=headers)).status_code == 401
        assert (await owner_client.get("/api/v1/users", headers=headers)).status_code == 401
        assert (
            await owner_client.get("/api/v1/portal/organisations", headers=personal_headers())
        ).json()[0]["id"] == access["id"]
        assert (
            await owner_client.post(
                "/api/v1/portal/invitations/accept", headers=personal_headers(), json={"token": raw}
            )
        ).status_code == 400
        # Email is enrollment evidence only; later authorization is immutable subject.
        portal_provider.user.return_value["email_addresses"][0]["email_address"] = (
            "changed-after-enrollment@example.com"
        )
        assert (await owner_client.get("/api/v1/portal/me", headers=headers)).status_code == 200
        listed = await owner_client.get(f"/api/v1/customers/{customer_id}/portal-invitations")
        assert listed.status_code == 200 and listed.json()[0]["status"] == "accepted"
        assert "invitation_url" not in listed.json()[0]
    after = (
        await async_db.scalar(select(func.count()).select_from(User)),
        await async_db.scalar(select(func.count()).select_from(Membership)),
    )
    assert after == before
    row = await async_db.scalar(
        select(CustomerPortalUser).where(CustomerPortalUser.customer_id == uuid.UUID(customer_id))
    )
    assert row.password_hash == "!clerk-only"
    approved = await async_db.scalar(
        select(PortalInvitation).where(PortalInvitation.id == uuid.UUID(invite["id"]))
    )
    assert approved.token_hash != raw and approved.accepted_by_clerk_user_id == "user_customer"


@pytest.mark.parametrize("invalid", ["recipient", "unverified", "pending", "expired", "revoked"])
async def test_invite_requires_active_verified_recipient_and_current_approval(
    owner_client, async_db, portal_provider, invalid
):
    async with independent_request_sessions(async_db):
        customer_id, invite, raw = await invitation(owner_client)
        if invalid == "recipient":
            portal_provider.user.return_value["email_addresses"][0]["email_address"] = (
                "other@example.com"
            )
        elif invalid == "unverified":
            portal_provider.user.return_value["email_addresses"][0]["verification"]["status"] = (
                "unverified"
            )
        elif invalid == "expired":
            row = await async_db.get(PortalInvitation, uuid.UUID(invite["id"]))
            row.expires_at = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
            await async_db.flush()
        elif invalid == "revoked":
            assert (
                await owner_client.delete(
                    f"/api/v1/customers/{customer_id}/portal-invitations/{invite['id']}"
                )
            ).status_code == 204
        response = await owner_client.post(
            "/api/v1/portal/invitations/accept",
            headers=personal_headers(status="pending" if invalid == "pending" else "active"),
            json={"token": raw},
        )
        assert (
            response.status_code
            == {
                "recipient": 403,
                "unverified": 400,
                "pending": 401,
                "expired": 400,
                "revoked": 400,
            }[invalid]
        )
    assert await async_db.scalar(select(func.count()).select_from(PortalAccess)) == 0


async def test_portal_selector_revocation_and_old_credentials_cannot_bypass_clerk(
    owner_client, async_db, portal_provider
):
    async with independent_request_sessions(async_db):
        customer_id, _invite, raw = await invitation(owner_client)
        accepted = await owner_client.post(
            "/api/v1/portal/invitations/accept", headers=personal_headers(), json={"token": raw}
        )
        assert accepted.status_code == 201
        access = accepted.json()
        own = personal_headers(access=access["id"])
        for headers in (
            personal_headers(),
            personal_headers("user_other", access["id"]),
            personal_headers(access=uuid.uuid4()),
            personal_headers(access=access["id"], status="pending"),
        ):
            assert (await owner_client.get("/api/v1/portal/me", headers=headers)).status_code == 401
        old = legacy_portal_token(uuid.uuid4(), 1)
        owner_client.cookies.set(CUSTOMER_COOKIE_NAME, old)
        assert (
            await owner_client.get(
                "/api/v1/portal/me",
                headers={
                    "Authorization": "Bearer " + old,
                    "X-Firstout-Portal-Access": access["id"],
                },
            )
        ).status_code == 401
        assert (
            await owner_client.post(
                "/api/v1/portal/login",
                json={"email": "customer@example.com", "password": "old-password"},
            )
        ).status_code == 400
        assert (
            await owner_client.post(
                f"/api/v1/customers/{customer_id}/portal-users",
                json={"email": "customer@example.com", "password": "new-password"},
            )
        ).status_code == 400
        revoked = await owner_client.delete(
            f"/api/v1/customers/{customer_id}/portal-access/{access['id']}"
        )
        assert revoked.status_code == 204
        assert (await owner_client.get("/api/v1/portal/me", headers=own)).status_code == 401
        assert (
            await owner_client.get("/api/v1/portal/organisations", headers=personal_headers())
        ).json() == []


async def test_staff_membership_disable_is_separate_but_global_identity_blocks_portal(
    owner_client, async_db, portal_provider
):
    buyer = await async_db.scalar(select(User).where(User.email == "buyer@example.com"))
    buyer.clerk_user_id = "user_customer"
    member = await async_db.scalar(
        select(Membership).where(
            Membership.user_id == buyer.id, Membership.is_legacy_home.is_(True)
        )
    )
    member.is_disabled = True
    await async_db.flush()
    async with independent_request_sessions(async_db):
        _customer_id, _invite, raw = await invitation(owner_client)
        accepted = await owner_client.post(
            "/api/v1/portal/invitations/accept", headers=personal_headers(), json={"token": raw}
        )
        assert accepted.status_code == 201
        headers = personal_headers(access=accepted.json()["id"])
        assert (await owner_client.get("/api/v1/portal/me", headers=headers)).status_code == 200
        buyer.is_disabled = True
        await async_db.flush()
        assert (await owner_client.get("/api/v1/portal/me", headers=headers)).status_code == 401
        assert (
            await owner_client.get("/api/v1/portal/organisations", headers=personal_headers())
        ).status_code == 401
        _other_customer, _other_invite, other_raw = await invitation(
            owner_client, name="Another approved customer"
        )
        blocked = await owner_client.post(
            "/api/v1/portal/invitations/accept",
            headers=personal_headers(),
            json={"token": other_raw},
        )
        assert blocked.status_code == 401


async def test_portal_directories_reject_foreign_organisation_references(owner_client, async_db):
    from app.models.team import Team
    from app.models.customer import Customer
    from tests.conftest import OWNER_EMAIL
    from sqlalchemy.exc import IntegrityError

    customer = await owner_client.post(
        "/api/v1/customers", json={"name": "Scoped customer", "customer_type": "trade"}
    )
    assert customer.status_code == 201
    own = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    foreign = Team(name="Foreign business", slug="foreign-portal-business")
    async_db.add(foreign)
    await async_db.flush()
    portal = CustomerPortalUser(
        team_id=own.team_id,
        customer_id=uuid.UUID(customer.json()["id"]),
        email="scoped@example.com",
        password_hash="!clerk-only",
        is_disabled=False,
    )
    async_db.add(portal)
    foreign_customer = Customer(
        team_id=foreign.id, name="Foreign scoped customer", customer_type="trade"
    )
    async_db.add(foreign_customer)
    await async_db.flush()
    # Both independent directory links must agree with the business row tenant.
    for row in (
        PortalInvitation(
            organisation_id=foreign.id,
            customer_id=portal.customer_id,
            email="scoped@example.com",
            token_hash="a" * 64,
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            invited_by_user_id=own.id,
        ),
        PortalAccess(
            clerk_user_id="user_scoped",
            organisation_id=foreign.id,
            portal_user_id=portal.id,
            customer_id=portal.customer_id,
            customer_name="Scoped customer",
            email="scoped@example.com",
        ),
        PortalAccess(
            clerk_user_id="user_foreign_portal_pair",
            organisation_id=foreign.id,
            portal_user_id=portal.id,
            customer_id=foreign_customer.id,
            customer_name="Foreign scoped customer",
            email="scoped@example.com",
        ),
    ):
        with pytest.raises(IntegrityError):
            async with async_db.begin_nested():
                async_db.add(row)
                await async_db.flush()


async def test_readonly_cutover_gate_refuses_new_legacy_portal_account(
    owner_client, async_db, monkeypatch
):
    from contextlib import asynccontextmanager
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.database import TenantSession
    from f0rge_db.organisation import organisation_session
    from app.commands import clerk_only_preflight
    from tests.conftest import _link_test_staff

    users = list(
        await async_db.scalars(
            select(User).where(User.is_disabled.is_(False), User.role != "system")
        )
    )
    profiles = {}
    for user in users:
        await _link_test_staff(async_db, user)
        profiles[user.clerk_user_id] = {
            "id": user.clerk_user_id,
            "external_id": str(user.id),
            "password_enabled": True,
            "primary_email_address_id": "verified",
            "email_addresses": [
                {
                    "id": "verified",
                    "email_address": user.email,
                    "verification": {"status": "verified"},
                }
            ],
        }
    maker = async_sessionmaker(
        async_db.bind,
        expire_on_commit=False,
        sync_session_class=TenantSession,
        join_transaction_mode="create_savepoint",
    )

    @asynccontextmanager
    async def scoped(team_id=None):
        async with organisation_session(maker, team_id) as session:
            yield session

    monkeypatch.setattr(clerk_only_preflight, "tenant_session", scoped)
    provider = SimpleNamespace(
        user=AsyncMock(side_effect=lambda subject: profiles[subject]),
        membership=AsyncMock(return_value={"id": "om_verified"}),
    )
    baseline = await clerk_only_preflight.check_readiness(provider)
    assert baseline["ready"] is True and baseline["unbound_portal_accounts"] == 0
    first = users[0]
    for flag in ("banned", "locked"):
        profiles[first.clerk_user_id][flag] = True
        blocked_staff = await clerk_only_preflight.check_readiness(provider)
        assert blocked_staff["ready"] is False and blocked_staff["unready_staff"] == 1
        del profiles[first.clerk_user_id][flag]
    from app.models.team import Team

    other = Team(
        name="Second enabled staff organisation",
        slug="preflight-second-org",
        clerk_org_id="org_preflight_second",
    )
    async_db.add(other)
    await async_db.flush()
    async_db.add(
        Membership(
            user_id=first.id,
            team_id=other.id,
            role="buyer",
            is_legacy_home=False,
            is_disabled=False,
        )
    )
    await async_db.flush()
    provider.membership.side_effect = lambda org, subject: (
        None if org == other.clerk_org_id else {"id": "om_verified"}
    )
    blocked_other = await clerk_only_preflight.check_readiness(provider)
    assert blocked_other["ready"] is False and blocked_other["unready_staff"] == 1
    home = await async_db.scalar(
        select(Membership).where(
            Membership.user_id == first.id, Membership.is_legacy_home.is_(True)
        )
    )
    home.is_disabled = True
    await async_db.flush()
    assert (await clerk_only_preflight.check_readiness(provider))["ready"] is False
    provider.membership.side_effect = None
    assert (await clerk_only_preflight.check_readiness(provider))["ready"] is True
    await async_db.refresh(home)
    assert home.is_disabled is True  # Readiness never re-enables a disabled membership.
    home.is_disabled = False
    await async_db.flush()
    customer = await owner_client.post(
        "/api/v1/customers", json={"name": "Late legacy portal customer", "customer_type": "trade"}
    )
    assert customer.status_code == 201
    owner = users[0]
    portal = CustomerPortalUser(
        team_id=owner.team_id,
        customer_id=uuid.UUID(customer.json()["id"]),
        email="late-legacy@example.com",
        password_hash="preserved-old-hash",
        is_disabled=False,
    )
    async_db.add(portal)
    await async_db.flush()
    blocked = await clerk_only_preflight.check_readiness(provider)
    assert blocked["ready"] is False and blocked["unbound_portal_accounts"] == 1
    await async_db.refresh(portal)
    assert portal.password_hash == "preserved-old-hash" and portal.is_disabled is False


@pytest.mark.parametrize("change", ["disabled", "retail", "wrong_customer"])
async def test_portal_choices_and_authorization_hide_unavailable_business_rows(
    owner_client, async_db, portal_provider, change
):
    from app.models.customer import Customer

    async with independent_request_sessions(async_db):
        customer_id, _invite, raw = await invitation(owner_client)
        accepted = await owner_client.post(
            "/api/v1/portal/invitations/accept", headers=personal_headers(), json={"token": raw}
        )
        assert accepted.status_code == 201
        access = await async_db.get(PortalAccess, uuid.UUID(accepted.json()["id"]))
        portal = await async_db.get(CustomerPortalUser, access.portal_user_id)
        if change == "disabled":
            portal.is_disabled = True
        elif change == "retail":
            customer = await async_db.get(Customer, uuid.UUID(customer_id))
            customer.customer_type = "retail"
        else:
            wrong = Customer(
                team_id=access.organisation_id,
                name="Other same-tenant customer",
                customer_type="trade",
            )
            async_db.add(wrong)
            await async_db.flush()
            access.customer_id = wrong.id
        await async_db.flush()
        assert (
            await owner_client.get("/api/v1/portal/organisations", headers=personal_headers())
        ).json() == []
        assert (
            await owner_client.get("/api/v1/portal/me", headers=personal_headers(access=access.id))
        ).status_code == 401


async def test_same_customer_identity_selects_only_approved_organisation_bindings(
    owner_client, async_db, portal_provider
):
    from app.models.team import Team
    from tests.conftest import OWNER_EMAIL

    owner = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    other = Team(
        name="Other portal business", slug="other-portal-business", clerk_org_id="org_other_portal"
    )
    async_db.add(other)
    await async_db.flush()
    async_db.add(
        Membership(
            user_id=owner.id,
            team_id=other.id,
            role="owner",
            is_legacy_home=False,
            is_disabled=False,
        )
    )
    await async_db.flush()
    other_staff = {
        "Authorization": "Bearer "
        + signed_clerk_token(owner.clerk_user_id, org_id=other.clerk_org_id, org_slug=other.slug)
    }
    async with independent_request_sessions(async_db):
        own_customer, _invite, own_raw = await invitation(owner_client)
        own = await owner_client.post(
            "/api/v1/portal/invitations/accept", headers=personal_headers(), json={"token": own_raw}
        )
        assert own.status_code == 201
        other_customer = await owner_client.post(
            "/api/v1/customers",
            headers=other_staff,
            json={"name": "Other approved customer", "customer_type": "trade"},
        )
        assert other_customer.status_code == 201
        invited = await owner_client.post(
            f"/api/v1/customers/{other_customer.json()['id']}/portal-invitations",
            headers=other_staff,
            json={"email": "customer@example.com"},
        )
        assert invited.status_code == 201
        raw = urlsplit(invited.json()["invitation_url"]).fragment.split("=", 1)[1]
        accepted = await owner_client.post(
            "/api/v1/portal/invitations/accept", headers=personal_headers(), json={"token": raw}
        )
        assert accepted.status_code == 201
        choices = await owner_client.get("/api/v1/portal/organisations", headers=personal_headers())
        assert choices.status_code == 200 and len(choices.json()) == 2
        for access, expected_customer in (
            (own.json(), own_customer),
            (accepted.json(), other_customer.json()["id"]),
        ):
            me = await owner_client.get(
                "/api/v1/portal/me", headers=personal_headers(access=access["id"])
            )
            assert me.status_code == 200 and me.json()["customer_id"] == expected_customer


async def test_concurrent_invite_claims_create_one_customer_binding(
    second_postgres_url, portal_provider
):
    import asyncio
    import hashlib
    import secrets
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from httpx import ASGITransport, AsyncClient
    from app.database import Base, TenantSession, get_db
    from app.models.customer import Customer
    from app.models.team import Team

    engine = create_async_engine(second_postgres_url)
    maker = async_sessionmaker(engine, expire_on_commit=False, sync_session_class=TenantSession)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)
    raw = secrets.token_urlsafe(32)
    async with maker() as db:
        team = Team(name="Owned concurrent business", slug="owned-concurrent-business")
        db.add(team)
        await db.flush()
        actor = User(
            team_id=team.id,
            email="owned-concurrent-approver@example.com",
            password_hash="retained-test-hash",
            role="owner",
            is_disabled=False,
        )
        customer = Customer(
            team_id=team.id, name="Owned concurrent customer", customer_type="trade"
        )
        db.add_all([actor, customer])
        await db.flush()
        db.add(
            PortalInvitation(
                organisation_id=team.id,
                customer_id=customer.id,
                email="customer@example.com",
                token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
                invited_by_user_id=actor.id,
            )
        )
        await db.commit()

    async def database():
        async with maker() as db:
            yield db

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = database
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            results = await asyncio.gather(
                *[
                    client.post(
                        "/api/v1/portal/invitations/accept",
                        headers=personal_headers(),
                        json={"token": raw},
                    )
                    for _ in range(2)
                ]
            )
        assert sorted(response.status_code for response in results) == [201, 400]
        async with maker() as db:
            assert await db.scalar(select(func.count()).select_from(PortalAccess)) == 1
            assert await db.scalar(select(func.count()).select_from(CustomerPortalUser)) == 1
            assert await db.scalar(select(func.count()).select_from(Membership)) == 0
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        await engine.dispose()
