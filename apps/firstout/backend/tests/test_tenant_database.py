"""Non-owner isolation proof on an explicitly disposable local PostgreSQL database."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import TenantSession
from app.models.account import Account
from f0rge_db.organisation import apply_tenant_context, organisation_session, tenant_id_ctx

pytestmark = pytest.mark.no_db
BACKEND = Path(__file__).resolve().parents[1]


def migrate(url: str, target: str, command: str = "upgrade") -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", command, target],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": url, "MIGRATION_DATABASE_URL": url},
        check=True,
        capture_output=True,
    )


@pytest_asyncio.fixture(scope="module")
async def rls_database_url(request):
    """CI always runs this matrix in an independent database on its testcontainer.

    A local override is optional; absence never silently skips the security gate.
    The pure storage test does not request this fixture or start a container.
    """
    explicit = os.environ.get("FIRSTOUT_RLS_TEST_DATABASE_URL")
    if explicit:
        parsed = make_url(explicit)
        assert parsed.host in (None, "localhost", "127.0.0.1")
        assert parsed.database == "firstout_astra_rls"
        yield explicit
        return
    from f0rge_testing import async_url

    container = request.getfixturevalue("postgres_container")
    parsed = make_url(async_url(container))
    database = "firstout_rls_test_" + uuid.uuid4().hex
    admin = create_async_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(sa.text(f'CREATE DATABASE "{database}"'))
    try:
        yield parsed.set(database=database).render_as_string(hide_password=False)
    finally:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        await admin.dispose()


@pytest_asyncio.fixture
async def tenant_database(rls_database_url, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "tenant_isolation_mode", "enforced")
    monkeypatch.setattr(settings, "frontend_proxy_secret", "synthetic-proxy-secret")
    url = rls_database_url
    parsed = make_url(url)
    migrate(url, "head")
    admin = create_async_engine(url)
    role = "firstout_astra_runtime_" + uuid.uuid4().hex[:12]
    runtime_password = "synthetic-" + uuid.uuid4().hex
    async with admin.begin() as conn:
        exists = await conn.scalar(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}
        )
        if not exists:
            await conn.execute(sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS"))
        # Generated synthetic secret only for this disposable role, never logged.
        await conn.execute(sa.text(f"ALTER ROLE {role} PASSWORD '{runtime_password}'"))
        await conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))
        await conn.execute(
            sa.text(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}")
        )
        await conn.execute(
            sa.text(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        )
    runtime = create_async_engine(
        parsed.set(username=role, password=runtime_password), pool_size=1, max_overflow=0
    )
    maker = async_sessionmaker(runtime, expire_on_commit=False, sync_session_class=TenantSession)
    from app.commands.tenant_cutover import activate_rls
    from app.runtime_database import verify_isolation_stage, verify_runtime_role

    async with async_sessionmaker(admin)() as owner, maker() as runtime_session:
        await activate_rls(owner, runtime_session)
        await owner.commit()
        await runtime_session.rollback()
        await verify_runtime_role(runtime_session)
        await verify_isolation_stage(runtime_session)
    a, b = uuid.uuid4(), uuid.uuid4()
    async with admin.begin() as conn:
        for team in (a, b):
            await conn.execute(
                sa.text(
                    "INSERT INTO teams(id,name,slug,clerk_org_id,status,created_at,updated_at) VALUES (:id,'Synthetic',:slug,:clerk_org,'active',now(),now())"
                ),
                {"id": team, "slug": f"proof-{team.hex}", "clerk_org": f"org-proof-{team.hex}"},
            )
    try:
        yield admin, runtime, maker, a, b
    finally:
        await runtime.dispose()
        async with admin.begin() as conn:
            for table in ("portal_access", "portal_invitations"):
                await conn.execute(
                    sa.text(f"DELETE FROM {table} WHERE organisation_id IN (:a,:b)"),
                    {"a": a, "b": b},
                )
            for table in (
                "tax_invoices",
                "skus",
                "customer_portal_users",
                "customers",
                "memberships",
                "cin7_import_runs",
                "document_sequences",
                "team_settings",
                "location_bins",
                "accounts",
                "locations",
                "users",
            ):
                await conn.execute(
                    sa.text(f"DELETE FROM {table} WHERE team_id IN (:a,:b)"), {"a": a, "b": b}
                )
            await conn.execute(sa.text("DELETE FROM teams WHERE id IN (:a,:b)"), {"a": a, "b": b})
            await conn.execute(sa.text(f"DROP OWNED BY {role}"))
            await conn.execute(sa.text(f"DROP ROLE {role}"))
        await admin.dispose()


async def test_nonowner_rls_pool_abort_commit_refresh_and_foreign_keys(tenant_database):
    admin, runtime, maker, a, b = tenant_database
    async with runtime.connect() as conn:
        role = (
            await conn.execute(
                sa.text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
            )
        ).one()
        assert role == (False, False)
        assert not await conn.scalar(
            sa.text(
                "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner=current_user"
            )
        )
        assert await conn.scalar(sa.text("SELECT count(*) FROM accounts")) == 0
    ids, pids = {}, []
    for team in (a, b):
        async with organisation_session(maker, team) as session:
            pids.append(await session.scalar(sa.text("SELECT pg_backend_pid()")))
            item = Account(code="PROOF-SAME", name="Synthetic", type="asset", team_id=team)
            session.add(item)
            await session.commit()
            await session.refresh(item)
            assert item.team_id == team
            ids[team] = item.id
    assert pids[0] == pids[1]
    async with organisation_session(maker, a) as session:
        assert await session.get(Account, ids[b]) is None
        for statement in (
            "UPDATE accounts SET name='Forbidden' WHERE id=:id",
            "DELETE FROM accounts WHERE id=:id",
        ):
            assert (await session.execute(sa.text(statement), {"id": ids[b]})).rowcount == 0
        session.add(Account(code="FORBIDDEN", name="Synthetic", type="asset", team_id=b))
        with pytest.raises(DBAPIError):
            await session.commit()
        await session.rollback()
        assert await session.scalar(sa.text("SELECT current_setting('app.tenant_id',true)")) == str(
            a
        )
        with pytest.raises(DBAPIError):
            await session.execute(sa.text("SELECT 1/0"))
    async with runtime.connect() as conn:
        assert (
            await conn.scalar(sa.text("SELECT NULLIF(current_setting('app.tenant_id',true),'')"))
            is None
        )
        assert await conn.scalar(sa.text("SELECT count(*) FROM accounts")) == 0
    async with organisation_session(maker, b) as session:
        assert await session.scalar(sa.select(Account.id)) == ids[b]
        with pytest.raises(Exception, match="Cannot switch tenant"):
            await apply_tenant_context(session, a)
    location = uuid.uuid4()
    async with admin.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO locations(id,team_id,name,type,is_archived,created_at,updated_at) VALUES (:id,:team,'Proof','warehouse',false,now(),now())"
            ),
            {"id": location, "team": b},
        )
    async with organisation_session(maker, a) as session:
        await session.execute(
            sa.text(
                "INSERT INTO location_bins(id,team_id,location_id,code,row_code,bay,level,is_default,is_archived,created_at,updated_at) VALUES (:id,:team,:location,'P-01-1','P',1,1,false,false,now(),now())"
            ),
            {"id": uuid.uuid4(), "team": a, "location": location},
        )
        with pytest.raises(IntegrityError):
            await session.commit()
    assert tenant_id_ctx.get() is None


async def test_migration_roundtrip_preserves_staff_and_grants(rls_database_url):
    url = rls_database_url
    migrate(url, "078_password_reset", "downgrade")
    admin = create_async_engine(url)
    user_id = uuid.uuid4()
    async with admin.begin() as conn:
        team_id = await conn.scalar(sa.text("SELECT id FROM teams LIMIT 1"))
        await conn.execute(
            sa.text(
                "INSERT INTO users(id,team_id,email,password_hash,role,is_disabled,token_version,created_at,updated_at) VALUES (:id,:team,:email,'synthetic-bcrypt-preservation','warehouse',false,7,now(),now())"
            ),
            {"id": user_id, "team": team_id, "email": f"proof-{user_id.hex}@example.com"},
        )
        before = (
            await conn.execute(
                sa.text(
                    "SELECT id,team_id,password_hash,role,is_disabled,token_version FROM users WHERE id=:id"
                ),
                {"id": user_id},
            )
        ).one()
        grants_before = (
            await conn.execute(
                sa.text(
                    "SELECT r.slug,p.key FROM roles r JOIN role_permissions p ON p.role_id=r.id ORDER BY r.slug,p.key"
                )
            )
        ).all()
    migrate(url, "head")
    async with admin.connect() as conn:
        after = (
            await conn.execute(
                sa.text(
                    "SELECT id,team_id,password_hash,role,is_disabled,token_version FROM users WHERE id=:id"
                ),
                {"id": user_id},
            )
        ).one()
        membership = (
            await conn.execute(
                sa.text(
                    "SELECT team_id,role,is_disabled,is_legacy_home FROM memberships WHERE user_id=:id"
                ),
                {"id": user_id},
            )
        ).one()
        grants_after = (
            await conn.execute(
                sa.text(
                    "SELECT r.slug,p.key FROM roles r JOIN role_permissions p ON p.role_id=r.id ORDER BY r.slug,p.key"
                )
            )
        ).all()
        assert before == after
        assert membership == (team_id, "warehouse", False, True)
        assert grants_before == grants_after
        assert (
            await conn.scalar(
                sa.text(
                    "SELECT count(*) FROM pg_class WHERE relkind='r' AND relnamespace='public'::regnamespace AND relrowsecurity AND relforcerowsecurity"
                )
            )
            == 0
        )
    migrate(url, "078_password_reset", "downgrade")
    migrate(url, "head")
    async with admin.begin() as conn:
        await conn.execute(sa.text("DELETE FROM memberships WHERE user_id=:id"), {"id": user_id})
        await conn.execute(sa.text("DELETE FROM users WHERE id=:id"), {"id": user_id})
    await admin.dispose()


async def test_cin7_detached_lock_settings_and_runtime_gate(tenant_database, monkeypatch):
    from app.models.cin7_import_run import Cin7ImportRun
    from app.models.team_settings import TeamSettings
    from app.runtime_database import verify_runtime_role
    from app.services.cin7_import_jobs import Cin7ImportJobService, _run_detached
    from app.services.payment_reminders import PaymentReminderService

    admin, runtime, maker, a, b = tenant_database
    async with async_sessionmaker(admin)() as session:
        with pytest.raises(RuntimeError, match="non-owner"):
            await verify_runtime_role(session)
    users, runs = {}, {}
    async with admin.begin() as conn:
        for team in (a, b):
            users[team] = uuid.uuid4()
            await conn.execute(
                sa.text(
                    "INSERT INTO users(id,team_id,email,password_hash,role,is_disabled,token_version,created_at,updated_at) VALUES (:id,:team,:email,'synthetic','owner',false,0,now(),now())"
                ),
                {"id": users[team], "team": team, "email": f"proof-{users[team]}@example.com"},
            )
    for team in (a, b):
        async with organisation_session(maker, team) as session:
            await verify_runtime_role(session)
            row = Cin7ImportRun(
                user_id=users[team],
                user_email="synthetic@example.com",
                file_sha256="a" * 64,
                file_name="synthetic.zip",
                mode="dry_run",
                status="queued",
                active_lock=True,
            )
            session.add(row)
            session.add(
                TeamSettings(
                    team_id=team,
                    label_width_mm=80 if team == a else 100,
                    payment_reminders_enabled=team == a,
                )
            )
            await session.commit()
            runs[team] = row.id
    async with organisation_session(maker, a) as session:
        session.add(
            Cin7ImportRun(
                user_id=users[a],
                user_email="synthetic@example.com",
                file_sha256="b" * 64,
                file_name="other.zip",
                mode="dry_run",
                status="queued",
                active_lock=True,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
    observed = []

    async def fake_execute(self, job_id):
        observed.append(
            (tenant_id_ctx.get(), await self.db.scalar(sa.select(Cin7ImportRun.id)), job_id)
        )

    monkeypatch.setattr("app.database.async_session_maker", maker)
    monkeypatch.setattr(Cin7ImportJobService, "execute", fake_execute)
    # Deliberately inherited wrong context: detached job must use explicit stored team.
    token = tenant_id_ctx.set(b)
    try:
        await _run_detached(runs[a], a)
    finally:
        tenant_id_ctx.reset(token)
    assert observed == [(a, runs[a], runs[a])]
    for team in (a, b):
        async with organisation_session(maker, team) as session:
            labels = await session.scalar(sa.select(TeamSettings.label_width_mm))
            assert labels == (80 if team == a else 100)
            reminders = await PaymentReminderService(session).get_settings()
            assert reminders.enabled == (team == a)


def test_tenant_storage_branding_and_import_paths(monkeypatch):
    from app.services import object_storage
    from app.config import settings

    monkeypatch.setattr(settings, "bucket_name", "")
    a, b = uuid.uuid4(), uuid.uuid4()
    token = tenant_id_ctx.set(a)
    try:
        ref = object_storage.save_bytes("branding/logo.png", b"synthetic-logo")
        archive = object_storage.save_bytes("cin7-imports/synthetic.zip", b"synthetic-import")
        assert f"tenants/{a}/" in ref
        assert f"tenants/{a}/" in archive
        assert object_storage.read_bytes(ref) == b"synthetic-logo"
        tenant_id_ctx.set(b)
        for action in (
            object_storage.read_bytes,
            object_storage.delete_object,
            object_storage.presigned_get_url,
        ):
            with pytest.raises(PermissionError, match="another tenant"):
                action(ref)
        with pytest.raises(PermissionError, match="another tenant"):
            object_storage.overwrite_bytes(archive, b"forbidden")
        with pytest.raises(ValueError):
            object_storage.save_bytes("../outside", b"forbidden")
    finally:
        tenant_id_ctx.reset(token)


async def test_marrow_user_rls_remains_independent_of_firstout_tenant(tenant_database):
    from f0rge_db.auth_context import user_id_ctx
    from f0rge_db.engine import register_rls_hook
    from f0rge_db.rls import enable_tenant_isolation
    from f0rge_db.tenant import apply_session_user_id, clear_tenant_session

    admin, runtime, _, a, b = tenant_database
    async with admin.begin() as conn:
        await conn.execute(
            sa.text("CREATE TABLE marrow_compat_proof (id uuid PRIMARY KEY, user_id uuid NOT NULL)")
        )
        await enable_tenant_isolation(conn, ["marrow_compat_proof"])
        await conn.execute(
            sa.text(f"GRANT SELECT,INSERT ON marrow_compat_proof TO {runtime.url.username}")
        )
        for user_id in (a, b):
            await conn.execute(
                sa.text("INSERT INTO marrow_compat_proof VALUES (:id,:user)"),
                {"id": uuid.uuid4(), "user": user_id},
            )
    register_rls_hook()
    maker = async_sessionmaker(runtime, expire_on_commit=False)
    user_token, tenant_token = user_id_ctx.set(None), tenant_id_ctx.set(b)
    try:
        async with maker() as session:
            await apply_session_user_id(session, a)
            await session.commit()
            assert await session.scalar(sa.text("SELECT user_id FROM marrow_compat_proof")) == a
            assert tenant_id_ctx.get() == b
            await apply_session_user_id(session, b)
            assert await session.scalar(sa.text("SELECT user_id FROM marrow_compat_proof")) == b
            await session.rollback()
            user_id_ctx.set(None)
            await clear_tenant_session(session)
            await session.commit()
    finally:
        user_id_ctx.reset(user_token)
        tenant_id_ctx.reset(tenant_token)
        async with admin.begin() as conn:
            await conn.execute(sa.text("DROP TABLE marrow_compat_proof"))


async def test_duplicate_sku_invoice_keys_and_authenticated_uuid_idor(tenant_database):
    import datetime
    from httpx import ASGITransport, AsyncClient
    from app.database import get_db
    from app.main import app
    from app.models.customer import Customer
    from app.models.membership import Membership
    from app.models.sku import Sku
    from app.models.tax_invoice import TaxInvoice
    from app.models.user import User
    from tests.conftest import legacy_staff_token, signed_clerk_token

    _, _, maker, a, b = tenant_database
    users, skus, invoices = {}, {}, {}
    for team in (a, b):
        async with organisation_session(maker, team) as session:
            user = User(
                team_id=team,
                clerk_user_id=f"user-proof-{team.hex}",
                email=f"proof-{team}@example.com",
                password_hash="synthetic",
                role="owner",
            )
            customer = Customer(name="Same synthetic customer")
            sku = Sku(
                our_ref="SAME-REF",
                our_barcode="SAME-BARCODE",
                name="Synthetic SKU",
                design="Same design",
                fabric="Same fabric",
            )
            session.add_all([user, customer, sku])
            await session.flush()
            session.add(
                Membership(
                    user_id=user.id,
                    team_id=team,
                    role="owner",
                    permission_source="legacy",
                    is_legacy_home=True,
                )
            )
            invoice = TaxInvoice(
                invoice_number="SAME-INV-0001",
                customer_id=customer.id,
                issue_date=datetime.date.today(),
                subtotal_ex_vat=100,
                vat_amount=15,
                total_inc_vat=115,
                amount_paid=0,
            )
            session.add(invoice)
            await session.commit()
            users[team], skus[team], invoices[team] = user.id, sku.id, invoice.id
    async with organisation_session(maker, a) as session:
        assert await session.scalar(sa.select(Sku.id).where(Sku.our_ref == "SAME-REF")) == skus[a]
        assert (
            await session.scalar(
                sa.select(TaxInvoice.id).where(TaxInvoice.invoice_number == "SAME-INV-0001")
            )
            == invoices[a]
        )
        assert await session.get(TaxInvoice, invoices[b]) is None

    async def runtime_get_db():
        async with organisation_session(maker) as session:
            yield session

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = runtime_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("firstout_session", legacy_staff_token(users[a]))
            assert (await client.get(f"/api/v1/skus/{skus[a]}")).status_code == 401
            client.cookies.clear()
            client.headers["Authorization"] = "Bearer " + signed_clerk_token(
                f"user-proof-{a.hex}", org_id=f"org-proof-{a.hex}", org_slug=f"proof-{a.hex}"
            )
            own = await client.get(f"/api/v1/skus/{skus[a]}")
            assert own.status_code == 200, own.text
            foreign = await client.get(f"/api/v1/skus/{skus[b]}")
            assert foreign.status_code == 404, foreign.text
            assert str(skus[b]) not in foreign.text
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


async def test_http_directory_media_trade_inverse_and_public_isolation(
    tenant_database, monkeypatch
):
    """Signed Clerk HTTP dependencies use migrated FORCE RLS on a non-owner role."""
    import hashlib
    import hmac
    from httpx import ASGITransport, AsyncClient
    from app.config import settings
    from app.database import get_db
    from app.main import app
    from app.models.customer import Customer
    from app.models.customer_portal_user import CustomerPortalUser
    from app.models.portal_identity import PortalAccess
    from app.models.membership import Membership
    from app.models.sku import Sku
    from app.models.user import User
    from app.services import object_storage
    from app.services.customer_portal import CUSTOMER_COOKIE_NAME
    from tests.conftest import legacy_portal_token, signed_clerk_token

    _, _, maker, a, b = tenant_database
    users, skus, accesses, portal_users = {}, {}, {}, {}
    for team in (a, b):
        async with organisation_session(maker, team) as session:
            user = User(
                team_id=team,
                clerk_user_id=f"user-http-{team.hex}",
                email=f"http-{team}@example.com",
                password_hash="synthetic",
                role="owner",
            )
            customer = Customer(name=f"Trade {team}", customer_type="trade")
            sku = Sku(
                our_ref=f"HTTP-{team}",
                our_barcode=f"HTTP-{team}",
                name="HTTP synthetic",
                design="plain",
                fabric="plain",
                retail_ex_vat=100,
                storefront_published=True,
            )
            sku.photo_storage_key = object_storage.save_bytes(
                "http/photo.jpg", b"synthetic-image-" + str(team).encode()
            )
            session.add_all([user, customer, sku])
            await session.flush()
            session.add(
                Membership(
                    user_id=user.id,
                    team_id=team,
                    role="owner",
                    permission_source="legacy",
                    is_legacy_home=True,
                )
            )
            portal = CustomerPortalUser(
                customer_id=customer.id,
                email=f"trade-{team}@example.com",
                password_hash="!clerk-only",
            )
            session.add(portal)
            await session.flush()
            access = PortalAccess(
                clerk_user_id=f"user-trade-{team.hex}",
                organisation_id=team,
                portal_user_id=portal.id,
                customer_id=customer.id,
                customer_name=customer.name,
                email=portal.email,
            )
            session.add(access)
            await session.commit()
            users[team], skus[team], accesses[team], portal_users[team] = (
                user.id,
                sku.id,
                access.id,
                portal.id,
            )

    async def runtime_get_db():
        async with organisation_session(maker) as session:
            yield session

    monkeypatch.setattr(settings, "ops_commerce_token", "synthetic-public-token")
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(a))
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test")
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = runtime_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for own, foreign in ((a, b), (b, a)):
                client.cookies.clear()
                client.headers["Authorization"] = "Bearer " + signed_clerk_token(
                    f"user-http-{own.hex}",
                    org_id=f"org-proof-{own.hex}",
                    org_slug=f"proof-{own.hex}",
                )
                signed_headers = {"x-firstout-frontend-host": f"proof-{own.hex}.app.firstout.co.za"}
                unsigned = await client.get("/api/v1/users", headers=signed_headers)
                assert unsigned.status_code == 400, unsigned.text
                signed_headers["x-firstout-proxy-signature"] = hmac.new(
                    settings.frontend_proxy_secret.encode(),
                    signed_headers["x-firstout-frontend-host"].encode(),
                    hashlib.sha256,
                ).hexdigest()
                directory = await client.get("/api/v1/users", headers=signed_headers)
                assert directory.status_code == 200, directory.text
                assert {row["id"] for row in directory.json()} == {str(users[own])}
                assert "password_hash" not in directory.text
                unknown = signed_clerk_token(
                    "unknown-clerk-subject",
                    org_id=f"org-proof-{own.hex}",
                    org_slug=f"proof-{own.hex}",
                    email=f"http-{own}@example.com",
                )
                mismatched = await client.get(
                    "/api/v1/auth/me", headers={"Authorization": "Bearer " + unknown}
                )
                assert mismatched.status_code == 401, mismatched.text
                assert (await client.get("/api/v1/auth/me")).status_code == 200
                update = await client.patch(
                    f"/api/v1/users/{users[foreign]}", json={"display_name": "Forbidden"}
                )
                assert update.status_code == 404, update.text
                own_media = await client.get(f"/api/v1/skus/{skus[own]}/photo")
                assert own_media.status_code == 200, own_media.text
                assert own_media.content == b"synthetic-image-" + str(own).encode()
                foreign_media = await client.get(f"/api/v1/skus/{skus[foreign]}/photo")
                assert foreign_media.status_code == 404, foreign_media.text

                personal = signed_clerk_token(f"user-trade-{own.hex}", status="active")
                client.headers["Authorization"] = "Bearer " + personal
                selector = {"X-Firstout-Portal-Access": str(accesses[own])}
                assert (await client.get("/api/v1/portal/me", headers=selector)).status_code == 200
                catalogue = await client.get("/api/v1/portal/catalogue", headers=selector)
                assert catalogue.status_code == 200, catalogue.text
                assert {row["id"] for row in catalogue.json()} == {str(skus[own])}
                approved = await client.get("/api/v1/portal/organisations")
                assert approved.status_code == 200
                assert {row["id"] for row in approved.json()} == {str(accesses[own])}
                assert (await client.get("/api/v1/portal/me")).status_code == 401
                assert (
                    await client.get(
                        "/api/v1/portal/me",
                        headers={"X-Firstout-Portal-Access": str(accesses[foreign])},
                    )
                ).status_code == 401
                assert (await client.get("/api/v1/auth/me", headers=selector)).status_code == 401
                pending = signed_clerk_token(f"user-trade-{own.hex}", status="pending")
                assert (
                    await client.get(
                        "/api/v1/portal/me",
                        headers={**selector, "Authorization": "Bearer " + pending},
                    )
                ).status_code == 401
                client.headers.pop("Authorization", None)
                client.cookies.set(
                    CUSTOMER_COOKIE_NAME, legacy_portal_token(portal_users[own], team_id=own)
                )
                assert (await client.get("/api/v1/portal/me", headers=selector)).status_code == 401
                client.cookies.clear()

            headers = {"Authorization": "Bearer synthetic-public-token", "x-ops-company-id": str(a)}
            public = await client.get("/api/v1/ops-commerce/v1/products", headers=headers)
            assert public.status_code == 200, public.text
            assert {row["source_sku_id"] for row in public.json()["products"]} == {str(skus[a])}
            headers["x-ops-company-id"] = str(b)
            rejected = await client.get("/api/v1/ops-commerce/v1/products", headers=headers)
            assert rejected.status_code == 403, rejected.text
            assert (await client.get("/api/v1/ops-commerce/v1/products")).status_code == 401
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


async def test_default_location_cross_tenant_foreign_key(tenant_database):
    from app.models.location import Location
    from app.models.membership import Membership
    from app.models.user import User

    _, _, maker, a, b = tenant_database
    async with organisation_session(maker, b) as session:
        location = Location(name="Foreign warehouse", type="warehouse")
        session.add(location)
        await session.commit()
        foreign_location = location.id
    async with organisation_session(maker, a) as session:
        user = User(
            team_id=a, email=f"location-{a}@example.com", password_hash="synthetic", role="owner"
        )
        session.add(user)
        await session.commit()
        user_id = user.id
        session.add(
            Membership(
                user_id=user_id,
                team_id=a,
                role="owner",
                is_legacy_home=True,
                default_location_id=foreign_location,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        # Legacy profile defaults are also an ownership edge, not just membership defaults.
        await session.execute(
            sa.text("UPDATE users SET default_location_id=:location WHERE id=:id"),
            {"location": foreign_location, "id": user_id},
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_prod_shaped_boot_staff_proxy_and_cutover_rollback(rls_database_url, monkeypatch):
    """Single-home preparation never authenticates; enforced Clerk preserves staff."""
    import hashlib
    import hmac
    from httpx import ASGITransport, AsyncClient
    from app.commands.tenant_cutover import activate_rls, deactivate_rls
    from app.config import settings
    from app.database import get_db
    from app.main import app
    from app.runtime_database import verify_isolation_stage, verify_runtime_role
    from app.services.auth import hash_password
    from tests.conftest import legacy_staff_token, signed_clerk_token

    migrate(rls_database_url, "078_password_reset", "downgrade")
    migrate(rls_database_url, "head")
    engine = create_async_engine(rls_database_url)
    maker = async_sessionmaker(engine, expire_on_commit=False, sync_session_class=TenantSession)
    monkeypatch.setattr(settings, "tenant_isolation_mode", "single_home")
    monkeypatch.setattr(settings, "frontend_proxy_secret", "")
    monkeypatch.setattr(settings, "cookie_secure", True)
    monkeypatch.setattr(settings, "clerk_enabled", False)
    monkeypatch.setattr(settings, "tenant_signup_enabled", False)
    monkeypatch.setattr(settings, "clerk_import_enabled", False)
    monkeypatch.setattr("app.database.async_session_maker", maker)
    monkeypatch.setattr("app.main.async_session_maker", maker)
    user_id = uuid.uuid4()
    subject = "user_compat_" + user_id.hex
    provider_org = "org_compat_" + user_id.hex
    password_hash = hash_password("synthetic-compat-password")
    role = "firstout_boot_runtime_" + uuid.uuid4().hex[:12]
    runtime_password = "synthetic-" + uuid.uuid4().hex
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{runtime_password}'"
            )
        )
        await conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))
        await conn.execute(
            sa.text(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}")
        )
        await conn.execute(
            sa.text(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        )
        home = await conn.scalar(sa.text("SELECT id FROM teams WHERE slug='firstout'"))
        await conn.execute(
            sa.text("UPDATE teams SET clerk_org_id=:org WHERE id=:team"),
            {"org": provider_org, "team": home},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO users(id,team_id,clerk_user_id,email,password_hash,role,is_disabled,token_version,created_at,updated_at) VALUES (:id,:team,:subject,:email,:password,'owner',false,0,now(),now())"
            ),
            {
                "id": user_id,
                "team": home,
                "subject": subject,
                "email": f"compat-{user_id}@example.com",
                "password": password_hash,
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO memberships(id,user_id,team_id,role,permission_source,is_disabled,is_legacy_home,created_at,updated_at) VALUES (:id,:user,:team,'owner','legacy',false,true,now(),now())"
            ),
            {"id": uuid.uuid4(), "user": user_id, "team": home},
        )

    async def prepared_get_db():
        async with organisation_session(maker) as session:
            yield session

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = prepared_get_db
    runtime = None
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="https://api.firstout.co.za"
            ) as client:
                login = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": f"compat-{user_id}@example.com",
                        "password": "synthetic-compat-password",
                    },
                )
                assert login.status_code == 400 and "set-cookie" not in login.headers
                client.cookies.set("firstout_session", legacy_staff_token(user_id))
                assert (await client.get("/api/v1/auth/me")).status_code == 401
        monkeypatch.setattr(settings, "tenant_isolation_mode", "enforced")
        monkeypatch.setattr(settings, "frontend_proxy_secret", "synthetic-proxy-secret")
        async with maker() as owner, maker() as unsafe_runtime:
            with pytest.raises(RuntimeError, match="non-owner"):
                await activate_rls(owner, unsafe_runtime)
            await owner.rollback()
            assert not await owner.scalar(
                sa.text(
                    "SELECT bool_or(relrowsecurity) FROM pg_class WHERE relnamespace='public'::regnamespace"
                )
            )
        runtime = create_async_engine(
            make_url(rls_database_url).set(username=role, password=runtime_password)
        )
        runtime_maker = async_sessionmaker(
            runtime, expire_on_commit=False, sync_session_class=TenantSession
        )
        async with maker() as owner, runtime_maker() as runtime_session:
            await activate_rls(owner, runtime_session)
            await owner.commit()
            await runtime_session.rollback()
            await verify_runtime_role(runtime_session)
        monkeypatch.setattr(settings, "clerk_enabled", True)
        monkeypatch.setattr("app.database.async_session_maker", runtime_maker)
        monkeypatch.setattr("app.main.async_session_maker", runtime_maker)

        async def enforced_get_db():
            async with organisation_session(runtime_maker) as session:
                yield session

        app.dependency_overrides[get_db] = enforced_get_db
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="https://api.firstout.co.za"
            ) as client:
                token = signed_clerk_token(
                    subject,
                    org_id=provider_org,
                    org_slug="firstout",
                    azp="https://app.firstout.co.za",
                )
                client.headers["Authorization"] = "Bearer " + token
                headers = {"x-firstout-frontend-host": "firstout.co.za"}
                assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 400
                headers["x-firstout-proxy-signature"] = "forged"
                assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 400
                headers["x-firstout-proxy-signature"] = hmac.new(
                    settings.frontend_proxy_secret.encode(), b"firstout.co.za", hashlib.sha256
                ).hexdigest()
                authenticated = await client.get("/api/v1/auth/me", headers=headers)
                assert authenticated.status_code == 200, authenticated.text
                assert "users.manage" in authenticated.json()["permissions"]
                client.headers.pop("Authorization", None)
                client.cookies.set("firstout_session", legacy_staff_token(user_id))
                assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401
        monkeypatch.setattr("app.database.async_session_maker", maker)
        monkeypatch.setattr("app.main.async_session_maker", maker)
        monkeypatch.setattr(settings, "tenant_isolation_mode", "single_home")
        monkeypatch.setattr(settings, "clerk_enabled", False)
        async with maker() as owner:
            with pytest.raises(RuntimeError, match="RLS is already active"):
                await verify_isolation_stage(owner)
            await owner.rollback()
            await deactivate_rls(owner)
            await owner.commit()
            await verify_isolation_stage(owner)
        async with engine.connect() as conn:
            preserved = (
                await conn.execute(
                    sa.text(
                        "SELECT password_hash,token_version,role,is_disabled FROM users WHERE id=:id"
                    ),
                    {"id": user_id},
                )
            ).one()
            assert preserved == (password_hash, 0, "owner", False)
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        if runtime is not None:
            await runtime.dispose()
        async with engine.begin() as conn:
            await conn.execute(
                sa.text("DELETE FROM memberships WHERE user_id=:id"), {"id": user_id}
            )
            await conn.execute(sa.text("DELETE FROM users WHERE id=:id"), {"id": user_id})
            await conn.execute(sa.text(f"DROP OWNED BY {role}"))
            await conn.execute(sa.text(f"DROP ROLE {role}"))
        await engine.dispose()


@pytest.mark.parametrize("change", ["missing", "permissive"])
async def test_enforced_startup_rejects_policy_tampering(tenant_database, change):
    from app.runtime_database import verify_runtime_role

    admin, runtime, _, _, _ = tenant_database
    async with async_sessionmaker(admin)() as owner, async_sessionmaker(runtime)() as session:
        if change == "missing":
            await owner.execute(sa.text("DROP POLICY organisation_isolation ON accounts"))
        else:
            await owner.execute(sa.text("CREATE POLICY unwanted_bypass ON accounts USING (true)"))
        await owner.commit()
        try:
            with pytest.raises(RuntimeError, match="sole canonical"):
                await verify_runtime_role(session)
        finally:
            if change == "missing":
                await owner.execute(
                    sa.text(
                        "CREATE POLICY organisation_isolation ON accounts FOR ALL USING (team_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (team_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
                    )
                )
            else:
                await owner.execute(sa.text("DROP POLICY unwanted_bypass ON accounts"))
            await owner.commit()
            await session.rollback()
            await verify_runtime_role(session)


async def test_rollback_refuses_additional_tenants_without_disabling_rls(
    tenant_database, monkeypatch
):
    from app.commands.tenant_cutover import deactivate_rls
    from app.config import settings

    admin, _, _, _, _ = tenant_database
    monkeypatch.setattr(settings, "tenant_isolation_mode", "single_home")
    async with async_sessionmaker(admin)() as owner:
        protected = sa.text(
            "SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace AND relrowsecurity AND relforcerowsecurity"
        )
        before = await owner.scalar(protected)
        assert before == 82
        assert await owner.scalar(
            sa.text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                "WHERE oid='public.tenant_invitations'::regclass"
            )
        )
        with pytest.raises(RuntimeError, match="additional tenants"):
            await deactivate_rls(owner)
        await owner.rollback()
        assert await owner.scalar(protected) == before


async def test_activation_requires_every_dml_grant(tenant_database):
    from app.commands.tenant_cutover import activate_rls
    from app.runtime_database import verify_runtime_role

    admin, runtime, _, _, _ = tenant_database
    async with async_sessionmaker(admin)() as owner, async_sessionmaker(runtime)() as session:
        await owner.execute(sa.text(f"REVOKE DELETE ON accounts FROM {runtime.url.username}"))
        await owner.commit()
        try:
            with pytest.raises(RuntimeError, match="DML grants"):
                await activate_rls(owner, session)
            await owner.rollback()
        finally:
            await owner.execute(sa.text(f"GRANT DELETE ON accounts TO {runtime.url.username}"))
            await owner.commit()
            await session.rollback()
            await verify_runtime_role(session)


async def test_083_portal_directory_grants_require_review(second_postgres_url):
    """An old runtime grant set cannot silently access new identity directories."""
    from app.runtime_database import verify_portal_directory_grants

    url = second_postgres_url
    migrate(url, "082_tenant_onboarding")
    owner = create_async_engine(url)
    role = "firstout_dir_runtime_" + uuid.uuid4().hex[:12]
    password = "synthetic-" + uuid.uuid4().hex
    runtime = None
    try:
        async with owner.begin() as conn:
            await conn.execute(
                sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))
            await conn.execute(
                sa.text(
                    f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}"
                )
            )
        migrate(url, "head")
        async with owner.connect() as conn:
            constraints = dict(
                (
                    await conn.execute(
                        sa.text(
                            "SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conname IN ('fk_portal_access_customer_scope','fk_portal_access_user_scope','fk_portal_invitation_customer_scope')"
                        )
                    )
                ).all()
            )
            for name in ("fk_portal_access_customer_scope", "fk_portal_invitation_customer_scope"):
                assert (
                    "FOREIGN KEY (organisation_id, customer_id) REFERENCES customers(team_id, id)"
                    in constraints[name]
                )
            assert (
                "FOREIGN KEY (organisation_id, portal_user_id) REFERENCES customer_portal_users(team_id, id)"
                in constraints["fk_portal_access_user_scope"]
            )
        runtime = create_async_engine(make_url(url).set(username=role, password=password))
        maker = async_sessionmaker(runtime)
        async with maker() as session:
            with pytest.raises(RuntimeError, match="customer identity directories"):
                await verify_portal_directory_grants(session)
        async with owner.begin() as conn:
            await conn.execute(
                sa.text(
                    f"GRANT SELECT,INSERT,UPDATE,DELETE ON portal_access,portal_invitations TO {role}"
                )
            )
        async with maker() as session:
            await verify_portal_directory_grants(session)
        async with owner.begin() as conn:
            await conn.execute(sa.text(f"REVOKE INSERT ON portal_invitations FROM {role}"))
        async with maker() as session:
            with pytest.raises(RuntimeError, match="customer identity directories"):
                await verify_portal_directory_grants(session)
        async with owner.begin() as conn:
            await conn.execute(sa.text(f"GRANT INSERT ON portal_invitations TO {role}"))
        async with maker() as session:
            await verify_portal_directory_grants(session)
    finally:
        if runtime is not None:
            await runtime.dispose()
        async with owner.begin() as conn:
            await conn.execute(sa.text(f"DROP OWNED BY {role}"))
            await conn.execute(sa.text(f"DROP ROLE {role}"))
        await owner.dispose()
