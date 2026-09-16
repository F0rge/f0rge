from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.main import app, tick_ready_tenants
from app.models.location import Location
from app.models.role import Role
from app.models.user import User
from app.services.nia_schedule import NiaScheduleService
from app.services.object_storage import save_bytes
from app.services.tenant_seed import seed_tenant_baseline
from app.tenancy.context import tenant_ctx
from app.tenancy.errors import TenantContext
from tests.test_tenancy_routing import _create_db, _register_tenant, _raw_client


@pytest.mark.asyncio
async def test_baseline_on_empty_db_has_no_users_or_locations(
    postgres_container,
    platform_registry: str,
) -> None:
    url = await _create_db(postgres_container, "vellano_baseline_empty")
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        await seed_tenant_baseline(session)
        users = int((await session.execute(select(func.count()).select_from(User))).scalar_one())
        locations = int(
            (await session.execute(select(func.count()).select_from(Location))).scalar_one()
        )
        roles = int((await session.execute(select(func.count()).select_from(Role))).scalar_one())
    await engine.dispose()
    assert users == 0
    assert locations == 0
    assert roles >= 1


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_storage_prefix_for_non_vellano_tenant(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    tenant_id = uuid.uuid4()
    prefix = f"tenants/{tenant_id}"
    ctx = TenantContext(
        id=tenant_id,
        slug="acme",
        database_url="postgresql+asyncpg://x",
        storage_prefix=prefix,
    )
    token = tenant_ctx.set(ctx)
    try:
        key = save_bytes("skus/photo.jpg", b"abc")
    finally:
        tenant_ctx.reset(token)
    normalised = str(key).replace("\\", "/")
    assert f"tenants/{tenant_id}/" in normalised
    assert normalised.endswith("skus/photo.jpg")


@pytest.mark.asyncio
async def test_ticker_continues_after_one_tenant_fails(
    postgres_container,
    platform_registry: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url_b = await _create_db(postgres_container, "vellano_ticker_b")
    await _register_tenant(
        slug="tickb",
        hostname="tickb.testserver",
        database_url=url_b,
        prefix="tenants/tickb",
    )
    seen: list[str] = []

    async def fake_tick(self) -> int:
        ctx = tenant_ctx.get()
        slug = ctx.slug if ctx is not None else ""
        seen.append(slug)
        if slug == "vellano":
            raise RuntimeError("boom")
        return 0

    monkeypatch.setattr(NiaScheduleService, "tick_due_tasks", fake_tick)
    await tick_ready_tenants()
    assert "vellano" in seen
    assert "tickb" in seen


@pytest.mark.asyncio
async def test_whatsapp_webhook_unknown_slug_is_404(
    platform_registry: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "wa_verify_token", "verify-me")
    async with _raw_client() as client:
        resp = await client.get(
            "/api/v1/webhooks/whatsapp/nope-slug",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me",
                "hub.challenge": "challenge-123",
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_whatsapp_legacy_path_still_verifies_without_header(
    platform_registry: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "wa_verify_token", "verify-me")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/v1/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me",
                "hub.challenge": "ok",
            },
        )
    assert resp.status_code == 200
    assert resp.text == "ok"
