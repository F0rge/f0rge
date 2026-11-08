from __future__ import annotations

import os
import time
from types import SimpleNamespace
from contextlib import asynccontextmanager

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/test",
)
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-pytest-only-32b")

from typing import AsyncIterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import sqlalchemy as sa  # noqa: E402
import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from f0rge_testing import async_url, postgres_container_fixture, savepoint_session  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402

import app.models  # noqa: F401, E402

from app.config import settings  # noqa: E402
from app.database import Base, TenantSession, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auth import JWT_COOKIE_NAME  # noqa: E402
from app.services.chart_of_accounts import ChartOfAccountsSeedService
from app.services.locations import LocationSeedService  # noqa: E402
from app.services.role_user_seed import RoleUserSeedService  # noqa: E402
from app.services.roles import RoleSeedService  # noqa: E402
from app.services.storefront_system_actor import StorefrontSystemActorService
from app.services.till_seed import TillSeedService  # noqa: E402
from app.services.users import BootstrapService  # noqa: E402

OWNER_EMAIL = settings.seed_owner_email
OWNER_PASSWORD = settings.seed_owner_password

_container_fixture = postgres_container_fixture("postgres:16")
_bootstrap_team_id = None
_test_signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_CLERK_ISSUER = "https://synthetic.clerk.accounts.dev"


def legacy_staff_token(user_id, ttl_hours=1, *, token_version=0):
    """Retired format, generated only to prove that requests reject it."""
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "ver": token_version, "iat": now, "exp": now + ttl_hours * 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )


def legacy_portal_token(portal_user_id, ttl_hours=1, *, team_id=None):
    """Retired customer format, never accepted by the application."""
    from f0rge_db.organisation import tenant_id_ctx

    now = int(time.time())
    claims = {
        "sub": str(portal_user_id),
        "typ": "customer",
        "iat": now,
        "exp": now + ttl_hours * 3600,
    }
    team_id = team_id or tenant_id_ctx.get()
    if team_id:
        claims["team_id"] = str(team_id)
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def signed_clerk_token(subject: str, *, org_id="", org_slug="", status=None, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": TEST_CLERK_ISSUER,
        "sub": subject,
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "azp": "http://test",
    }
    if org_id:
        claims["o"] = {"id": org_id, "slg": org_slug, "rol": "member"}
    if status is not None:
        claims["sts"] = status
    claims.update(overrides)
    return jwt.encode(claims, _test_signing_key, algorithm="RS256")


class ClerkTestClient(AsyncClient):
    test_db: AsyncSession


async def _link_test_staff(db, user):
    from app.models.team import Team

    team = await db.get(Team, user.team_id)
    user.clerk_user_id = user.clerk_user_id or "user_test_" + user.id.hex
    team.clerk_org_id = team.clerk_org_id or "org_test_" + team.id.hex
    await db.flush()
    return team


async def authenticate_as(client, email: str) -> httpx.Response:
    """Explicit fixture sign-in; the actual request still verifies JWT/membership."""
    from app.models.user import User

    user = await client.test_db.scalar(sa.select(User).where(User.email == email))
    assert user is not None, "Create owned fixture staff before authentication"
    team = await _link_test_staff(client.test_db, user)
    client.headers["Authorization"] = "Bearer " + signed_clerk_token(
        user.clerk_user_id, org_id=team.clerk_org_id, org_slug=team.slug
    )
    return await client.get("/api/v1/auth/me")


async def create_test_staff(
    client,
    *,
    email: str,
    password="test-password",
    role="buyer",
    display_name=None,
    default_location_id=None,
) -> dict:
    """Owned database fixture, never a replacement response from a retired API."""
    import uuid
    from app.models.user import User
    from app.models.membership import Membership
    from app.models.team import Team
    from app.services.auth import hash_password
    from f0rge_db.organisation import tenant_id_ctx

    team = await client.test_db.get(Team, tenant_id_ctx.get())
    existing = await client.test_db.scalar(sa.select(User).where(User.email == email))
    if existing is not None:
        assert existing.team_id == team.id and existing.role == role, "Fixture identity mismatch"
        await _link_test_staff(client.test_db, existing)
        return _test_staff_record(existing, team)
    user = User(
        team_id=team.id,
        email=email,
        password_hash=hash_password(password),
        role=role,
        display_name=display_name,
        is_disabled=False,
        default_location_id=uuid.UUID(str(default_location_id)) if default_location_id else None,
    )
    client.test_db.add(user)
    await client.test_db.flush()
    client.test_db.add(
        Membership(
            user_id=user.id,
            team_id=team.id,
            role=role,
            is_legacy_home=True,
            is_disabled=False,
            default_location_id=user.default_location_id,
        )
    )
    await _link_test_staff(client.test_db, user)
    return _test_staff_record(user, team)


def _test_staff_record(user, team) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "display_name": user.display_name,
        "is_disabled": user.is_disabled,
        "team_id": str(team.id),
        "team": {"id": str(team.id), "name": team.name},
        "default_location_id": str(user.default_location_id) if user.default_location_id else None,
    }


@pytest.fixture(autouse=True)
def clerk_test_verification(monkeypatch):
    monkeypatch.setattr(settings, "tenant_isolation_mode", "enforced")
    monkeypatch.setattr(settings, "clerk_enabled", True)
    monkeypatch.setattr(settings, "clerk_issuer", TEST_CLERK_ISSUER)
    monkeypatch.setattr(
        settings, "clerk_authorized_parties", ["http://test", "https://app.firstout.co.za"]
    )
    monkeypatch.setattr(
        "app.services.clerk.jwks_client",
        lambda _: SimpleNamespace(
            get_signing_key_from_jwt=lambda _: SimpleNamespace(key=_test_signing_key.public_key())
        ),
    )


if os.environ.get("FIRSTOUT_TEST_DATABASE_URL"):

    @pytest.fixture(scope="session")
    def postgres_container():
        from sqlalchemy.engine import make_url

        url = make_url(os.environ["FIRSTOUT_TEST_DATABASE_URL"])
        if url.host not in (None, "localhost", "127.0.0.1") or not url.database.startswith(
            "firstout_"
        ):
            raise RuntimeError("Only a disposable local firstout_* test database is allowed")

        class LocalPostgres:
            def get_connection_url(self):
                return os.environ["FIRSTOUT_TEST_DATABASE_URL"]

        return LocalPostgres()
else:
    postgres_container = _container_fixture


@pytest.fixture(autouse=True)
def tenant_test_context(request):
    if request.node.get_closest_marker("no_db"):
        yield
        return
    request.getfixturevalue("async_engine")
    from f0rge_db.organisation import tenant_id_ctx

    token = tenant_id_ctx.set(_bootstrap_team_id)
    try:
        yield
    finally:
        tenant_id_ctx.reset(token)


@pytest.fixture(autouse=True)
def disable_payment_reminder_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "payment_reminder_ticker", False)


@pytest.fixture(autouse=True)
def patch_storage_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage_path = tmp_path / "storage"
    storage_path.mkdir()
    monkeypatch.setattr(settings, "storage_dir", str(storage_path))


@pytest.fixture(autouse=True)
def patch_async_session_maker(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if request.node.get_closest_marker("no_db"):
        return
    async_engine = request.getfixturevalue("async_engine")
    maker = async_sessionmaker(
        async_engine, expire_on_commit=False, class_=AsyncSession, sync_session_class=TenantSession
    )
    monkeypatch.setattr("app.database.engine", async_engine)
    monkeypatch.setattr("app.database.async_session_maker", maker)
    monkeypatch.setattr("app.main.async_session_maker", maker)


@pytest_asyncio.fixture(scope="session")
async def async_engine(
    postgres_container: PostgresContainer,
) -> AsyncIterator[AsyncEngine]:
    global _bootstrap_team_id
    url = os.environ.get("FIRSTOUT_TEST_DATABASE_URL") or async_url(postgres_container)
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession, sync_session_class=TenantSession
    )() as session:
        from app.models.team import Team
        from f0rge_db.organisation import apply_tenant_context, tenant_id_ctx

        await BootstrapService(session).seed_if_empty()
        _bootstrap_team_id = await session.scalar(sa.select(Team.id).limit(1))
        token = tenant_id_ctx.set(_bootstrap_team_id)
        await apply_tenant_context(session, _bootstrap_team_id)
        await RoleSeedService(session).seed()
        await LocationSeedService(session).seed_if_empty()
        await RoleUserSeedService(session).seed()
        await StorefrontSystemActorService(session).ensure()
        coa = ChartOfAccountsSeedService(session)
        await coa.seed_if_empty()
        await coa.ensure_opening_equity()
        await coa.ensure_category_chart()
        await coa.ensure_bank_accounts()
        await TillSeedService(session).seed_if_empty()
        tenant_id_ctx.reset(token)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def async_db(async_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with savepoint_session(async_engine, sync_session_class=TenantSession) as session:
        yield session


@pytest_asyncio.fixture
async def async_client(async_db: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield async_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with ClerkTestClient(transport=transport, base_url="http://test") as client:
        client.test_db = async_db
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def owner_client(async_client: AsyncClient) -> AsyncClient:
    resp = await authenticate_as(async_client, OWNER_EMAIL)
    assert resp.status_code == 200
    return async_client


def assert_firstout_session_cookie(resp: httpx.Response) -> None:
    set_cookie = resp.headers.get("set-cookie", "")
    assert JWT_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie or "SameSite=Lax" in set_cookie


@pytest_asyncio.fixture
async def second_postgres_url(postgres_container):
    import uuid
    from sqlalchemy.engine import make_url

    base_url = async_url(postgres_container)
    parsed = make_url(base_url)
    name = "firstout_test_second_" + uuid.uuid4().hex
    admin = create_async_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    try:
        yield parsed.set(database=name).render_as_string(hide_password=False)
    finally:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        await admin.dispose()


@asynccontextmanager
async def independent_request_sessions(shared_db: AsyncSession):
    """Cross-tenant tests use separate request sessions on the fixture transaction.

    Production never switches a session's tenant; the default test fixture reuses
    its one session for convenience, so tenant-switch scenarios need this scope.
    """
    maker = async_sessionmaker(
        shared_db.bind,
        expire_on_commit=False,
        sync_session_class=TenantSession,
        join_transaction_mode="create_savepoint",
    )

    async def request_db():
        async with maker() as session:
            yield session

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = request_db
    try:
        yield maker
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
