from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD, UserCRUD
from app.models.team import Team
from app.models.user import User, UserRole
from app.platform.crud import SignupCRUD, TenantCRUD, TenantHostnameCRUD
from app.platform.database import platform_sessionmaker
from app.platform.models import (
    SIGNUP_STATUS_FAILED,
    SIGNUP_STATUS_PROVISIONING,
    SIGNUP_STATUS_READY,
    TENANT_STATUS_FAILED,
    TENANT_STATUS_PROVISIONING,
    TENANT_STATUS_READY,
    Signup,
    Tenant,
    TenantHostname,
)
from app.platform.service import (
    ROLE_DB_PATTERN,
    encrypt_database_url,
    tenant_role_name,
    validate_slug,
)
from app.services.tenant_seed import seed_tenant_baseline
from app.tenancy.context import tenant_ctx
from app.tenancy.engines import engine_cache
from app.tenancy.errors import TenantContext
from app.tenancy.resolver import invalidate_hostname_cache
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _pg_ident(name: str) -> str:
    if not ROLE_DB_PATTERN.fullmatch(name):
        raise ValidationError("Invalid identifier")
    return '"' + name.replace('"', '""') + '"'


def _pg_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class ProvisioningService:
    async def provision(self, signup_id: uuid.UUID) -> Tenant:
        maker = platform_sessionmaker()
        async with maker() as db:
            signup = await SignupCRUD(db).get_by_id(signup_id)
            if signup is None:
                raise NotFoundError("Signup not found")
            if signup.tenant_id is not None:
                existing = await TenantCRUD(db).get_by_id(signup.tenant_id)
                if existing is not None and existing.status == TENANT_STATUS_READY:
                    signup.status = SIGNUP_STATUS_READY
                    await db.commit()
                    return existing
            try:
                tenant = await self._provision(db, signup)
            except Exception:
                logger.exception("provision failed slug=%s", signup.slug)
                await self._mark_failed(db, signup, "provision_failed")
                raise
            return tenant

    async def _provision(self, db: AsyncSession, signup: Signup) -> Tenant:
        slug = validate_slug(signup.slug)
        role_name = tenant_role_name(slug)
        signup.status = SIGNUP_STATUS_PROVISIONING
        tenant = await self._tenant_row(db, signup, slug)
        tenant.status = TENANT_STATUS_PROVISIONING
        signup.tenant_id = tenant.id
        await db.commit()

        if not tenant.database_url_encrypted:
            password = secrets.token_urlsafe(24)
            database_url = await self._create_role_and_database(role_name, password)
            tenant.database_url_encrypted = encrypt_database_url(database_url)
            await db.commit()
        else:
            from app.platform.service import decrypt_database_url

            database_url = decrypt_database_url(tenant.database_url_encrypted)

        await self._ensure_citext(role_name)
        await asyncio.to_thread(self._upgrade_tenant, database_url)
        await self._seed(tenant, database_url, signup)
        await self._ensure_hostname(db, tenant, slug)
        tenant.status = TENANT_STATUS_READY
        signup.status = SIGNUP_STATUS_READY
        signup.failure_reason = None
        await db.commit()
        invalidate_hostname_cache()
        return tenant

    async def _tenant_row(self, db: AsyncSession, signup: Signup, slug: str) -> Tenant:
        crud = TenantCRUD(db)
        if signup.tenant_id is not None:
            existing = await crud.get_by_id(signup.tenant_id)
            if existing is not None:
                return existing
        existing = await crud.get_by_slug(slug)
        if existing is not None:
            return existing
        display = (signup.trading_name or signup.legal_name).strip()
        tenant = Tenant(
            slug=slug,
            display_name=display,
            status=TENANT_STATUS_PROVISIONING,
            storage_prefix=f"tenants/{uuid.uuid4()}",
        )
        async with unit_of_work(db):
            await crud.add_and_flush(tenant)
        reloaded = await crud.get_by_id(tenant.id)
        assert reloaded is not None
        return reloaded

    async def _mark_failed(self, db: AsyncSession, signup: Signup, reason: str) -> None:
        signup.status = SIGNUP_STATUS_FAILED
        signup.failure_reason = reason
        if signup.tenant_id is not None:
            tenant = await TenantCRUD(db).get_by_id(signup.tenant_id)
            if tenant is not None:
                tenant.status = TENANT_STATUS_FAILED
        await db.commit()

    def _admin_url(self) -> str:
        url = (settings.platform_admin_database_url or "").strip()
        if not url:
            raise ValidationError("PLATFORM_ADMIN_DATABASE_URL is not set")
        return url

    async def _create_role_and_database(self, role_name: str, password: str) -> str:
        admin_url = self._admin_url()
        parsed = make_url(admin_url)
        engine = create_async_engine(admin_url, echo=False, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as conn:
                role_exists = (
                    await conn.execute(
                        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
                        {"name": role_name},
                    )
                ).scalar_one_or_none()
                ident = _pg_ident(role_name)
                if role_exists is None:
                    await conn.execute(
                        sa.text(
                            f"CREATE ROLE {ident} WITH LOGIN PASSWORD {_pg_str(password)} "
                            "NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT"
                        ),
                    )
                else:
                    await conn.execute(
                        sa.text(f"ALTER ROLE {ident} WITH LOGIN PASSWORD {_pg_str(password)}")
                    )
                db_exists = (
                    await conn.execute(
                        sa.text("SELECT 1 FROM pg_database WHERE datname = :name"),
                        {"name": role_name},
                    )
                ).scalar_one_or_none()
                if db_exists is None:
                    await conn.execute(sa.text(f"CREATE DATABASE {ident} OWNER {ident}"))
                await conn.execute(sa.text(f"REVOKE CONNECT ON DATABASE {ident} FROM PUBLIC"))
                await conn.execute(sa.text(f"GRANT CONNECT ON DATABASE {ident} TO {ident}"))
        finally:
            await engine.dispose()
        host = parsed.host or "localhost"
        port = parsed.port or 5432
        encoded = quote_plus(password)
        return f"postgresql+asyncpg://{role_name}:{encoded}@{host}:{port}/{role_name}"

    async def _ensure_citext(self, db_name: str) -> None:
        parsed = make_url(self._admin_url())
        admin_to_tenant = parsed.set(database=db_name).render_as_string(hide_password=False)
        if parsed.drivername.startswith("postgresql") and "+asyncpg" not in parsed.drivername:
            admin_to_tenant = admin_to_tenant.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(admin_to_tenant, echo=False)
        try:
            async with engine.begin() as conn:
                await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext"))
                await conn.execute(sa.text(f"GRANT ALL ON SCHEMA public TO {_pg_ident(db_name)}"))
        finally:
            await engine.dispose()

    def _upgrade_tenant(self, database_url: str) -> None:
        cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(cfg, "head")

    async def _seed(self, tenant: Tenant, database_url: str, signup: Signup) -> None:
        from app.platform.service import decrypt_database_url

        url = database_url or decrypt_database_url(tenant.database_url_encrypted or "")
        ctx = TenantContext(
            id=tenant.id,
            slug=tenant.slug,
            database_url=url,
            storage_prefix=tenant.storage_prefix,
        )
        token = tenant_ctx.set(ctx)
        try:
            maker = await engine_cache.get_sessionmaker(ctx)
            async with maker() as session:
                await seed_tenant_baseline(session)
                await self._clear_migration_locations(session)
                await self._seed_owner(session, signup)
        finally:
            tenant_ctx.reset(token)

    async def _clear_migration_locations(self, session: AsyncSession) -> None:
        """Migration 003 inserts sample shops; a new Company Home must be empty."""
        await session.execute(sa.text("TRUNCATE TABLE locations RESTART IDENTITY CASCADE"))
        await session.commit()

    async def _seed_owner(self, session: AsyncSession, signup: Signup) -> None:
        users = UserCRUD(session)
        if await users.count() > 0:
            return
        teams = TeamCRUD(session)
        name = (signup.trading_name or signup.legal_name).strip()
        async with unit_of_work(session):
            team: Optional[Team] = await teams.get_first()
            if team is None:
                team = Team(name=name)
                await teams.add_and_flush(team)
            else:
                team.name = name
            owner = User(
                team_id=team.id,
                email=signup.email,
                password_hash=signup.password_hash,
                display_name=signup.owner_name,
                role=UserRole.OWNER,
            )
            await users.add_and_flush(owner)
        settings_row = await TeamSettingsCRUD(session).get_or_create_for_team(team.id)
        settings_row.legal_name = signup.legal_name
        settings_row.trading_name = signup.trading_name
        await session.commit()

    async def _ensure_hostname(self, db: AsyncSession, tenant: Tenant, slug: str) -> None:
        hostname = f"{slug}.{settings.tenant_base_domain}".lower()
        host_crud = TenantHostnameCRUD(db)
        row = await host_crud.get_by_hostname(hostname)
        if row is None:
            async with unit_of_work(db):
                await host_crud.add_and_flush(
                    TenantHostname(hostname=hostname, tenant_id=tenant.id, is_primary=True)
                )
        else:
            row.tenant_id = tenant.id
            row.is_primary = True


async def upgrade_tenant_url(database_url: str) -> None:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    await asyncio.to_thread(command.upgrade, cfg, "head")
