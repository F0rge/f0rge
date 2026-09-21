"""Nia monthly token cap enforcement and usage APIs."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user import UserCRUD
from app.models.nia import NiaUsageEvent
from app.services.nia_usage import NiaUsageService

models.ALLOW_MODEL_REQUESTS = False

TEST_MODEL_OUTPUT = "Hello from Nia"


@pytest.fixture(autouse=True)
def nia_test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: TestModel(custom_output_text=TEST_MODEL_OUTPUT, call_tools=[]),
    )


@pytest.fixture(autouse=True)
def openrouter_key_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


async def _consume_stream(resp) -> bytes:
    chunks: list[bytes] = []
    async for chunk in resp.aiter_bytes():
        chunks.append(chunk)
    return b"".join(chunks)


async def _sum_usage(async_db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await async_db.execute(
        select(func.coalesce(func.sum(NiaUsageEvent.total_tokens), 0)).where(
            NiaUsageEvent.user_id == user_id
        )
    )
    return int(result.scalar_one())


async def test_at_cap_run_rejected_usage_unchanged(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    user_crud = UserCRUD(async_db)
    till = await user_crud.get_by_email("till@example.com")
    assert till is not None

    usage_service = NiaUsageService(async_db)
    await usage_service.record_usage(
        user_id=till.id,
        model="test-model",
        prompt_tokens=60,
        completion_tokens=40,
    )
    assert await _sum_usage(async_db, till.id) == 100

    cap_patch = await owner_client.patch(
        f"/api/v1/nia/usage/{till.id}",
        json={"nia_monthly_token_cap": 100},
    )
    assert cap_patch.status_code == 200
    assert cap_patch.json()["cap"] == 100

    till_client = await _login(async_client, "till@example.com", settings.seed_till_password)
    create = await till_client.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    thread_id = create.json()["id"]

    run = await till_client.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "hello", "page": {"path": "/invoices"}},
    )
    assert run.status_code == 429
    assert run.json()["detail"]["code"] == "nia_cap_exceeded"
    assert await _sum_usage(async_db, till.id) == 100


async def test_under_cap_run_succeeds(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    user_crud = UserCRUD(async_db)
    till = await user_crud.get_by_email("till@example.com")
    assert till is not None

    cap_patch = await owner_client.patch(
        f"/api/v1/nia/usage/{till.id}",
        json={"nia_monthly_token_cap": 10000},
    )
    assert cap_patch.status_code == 200

    till_client = await _login(async_client, "till@example.com", settings.seed_till_password)
    create = await till_client.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    thread_id = create.json()["id"]

    run = await till_client.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "hello", "page": {"path": "/invoices"}},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    usage_rows = (
        (
            await async_db.execute(
                select(NiaUsageEvent).where(NiaUsageEvent.thread_id == uuid.UUID(thread_id))
            )
        )
        .scalars()
        .all()
    )
    assert len(usage_rows) == 1
    assert await _sum_usage(async_db, till.id) >= 0


async def test_till_cannot_patch_other_user_cap(
    async_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    user_crud = UserCRUD(async_db)
    till = await user_crud.get_by_email("till@example.com")
    warehouse = await user_crud.get_by_email("warehouse@example.com")
    assert till is not None
    assert warehouse is not None

    till_client = await _login(async_client, "till@example.com", settings.seed_till_password)
    denied = await till_client.patch(
        f"/api/v1/nia/usage/{warehouse.id}",
        json={"nia_monthly_token_cap": 500},
    )
    assert denied.status_code == 403

    owner = await _login(async_client, "owner@example.com", settings.seed_owner_password)
    allowed = await owner.patch(
        f"/api/v1/nia/usage/{till.id}",
        json={"nia_monthly_token_cap": 2500},
    )
    assert allowed.status_code == 200
    assert allowed.json()["override"] == 2500
    assert allowed.json()["cap"] == 2500


async def test_usage_me_for_till(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    user_crud = UserCRUD(async_db)
    till = await user_crud.get_by_email("till@example.com")
    assert till is not None

    await owner_client.patch(
        f"/api/v1/nia/usage/{till.id}",
        json={"nia_monthly_token_cap": 900},
    )
    usage_service = NiaUsageService(async_db)
    await usage_service.record_usage(
        user_id=till.id,
        model="test-model",
        prompt_tokens=12,
        completion_tokens=8,
    )

    till_client = await _login(async_client, "till@example.com", settings.seed_till_password)
    me = await till_client.get("/api/v1/nia/usage/me")
    assert me.status_code == 200
    body = me.json()
    assert body["used"] == 20
    assert body["cap"] == 900
    assert body["remaining"] == 880
    assert body["period_start"] is not None


async def test_cap_zero_blocks_run(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    user_crud = UserCRUD(async_db)
    till = await user_crud.get_by_email("till@example.com")
    assert till is not None

    cap_patch = await owner_client.patch(
        f"/api/v1/nia/usage/{till.id}",
        json={"nia_monthly_token_cap": 0},
    )
    assert cap_patch.status_code == 200

    till_client = await _login(async_client, "till@example.com", settings.seed_till_password)
    create = await till_client.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    thread_id = create.json()["id"]

    run = await till_client.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "blocked", "page": {"path": "/invoices"}},
    )
    assert run.status_code == 429
    assert run.json()["detail"]["code"] == "nia_cap_exceeded"


def test_migration_039_down_revision() -> None:
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "migrations/versions/039_nia_caps.py"
    spec = importlib.util.spec_from_file_location("migration_039", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "038_nia_hitl"
