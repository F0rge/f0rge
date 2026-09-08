"""Nia threads, archive isolation, and usage ledger."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user import UserCRUD
from app.services.nia_usage import NiaUsageService


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


async def test_till_creates_thread_warehouse_cannot_read(
    async_client: AsyncClient,
) -> None:
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    create = await till.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    thread_id = create.json()["id"]
    assert create.json()["messages"] == []

    warehouse = await _login(
        async_client,
        "warehouse@example.com",
        settings.seed_warehouse_password,
    )
    foreign = await warehouse.get(f"/api/v1/nia/threads/{thread_id}")
    assert foreign.status_code == 404

    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    own = await till.get(f"/api/v1/nia/threads/{thread_id}")
    assert own.status_code == 200
    assert own.json()["id"] == thread_id
    assert own.json()["messages"] == []


async def test_list_active_threads_and_archive(owner_client: AsyncClient) -> None:
    create = await owner_client.post("/api/v1/nia/threads", json={"title": "Planning"})
    assert create.status_code == 201
    thread_id = create.json()["id"]

    listed = await owner_client.get("/api/v1/nia/threads")
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert thread_id in ids

    archived = await owner_client.post(f"/api/v1/nia/threads/{thread_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None

    listed_after = await owner_client.get("/api/v1/nia/threads")
    assert listed_after.status_code == 200
    ids_after = {row["id"] for row in listed_after.json()}
    assert thread_id not in ids_after

    again = await owner_client.post(f"/api/v1/nia/threads/{thread_id}/archive")
    assert again.status_code == 200
    assert again.json()["archived_at"] is not None


async def test_usage_helper_sums_per_user(async_db: AsyncSession) -> None:
    user_crud = UserCRUD(async_db)
    till = await user_crud.get_by_email("till@example.com")
    warehouse = await user_crud.get_by_email("warehouse@example.com")
    assert till is not None
    assert warehouse is not None

    service = NiaUsageService(async_db)
    event = await service.record_usage(
        user_id=till.id,
        model="test-model",
        prompt_tokens=17,
        completion_tokens=31,
    )
    assert event.total_tokens == 48

    assert await service.sum_total_tokens_for_user(till.id) == 48
    assert await service.sum_total_tokens_for_user(warehouse.id) == 0


async def test_create_thread_logged_out(async_client: AsyncClient) -> None:
    async_client.cookies.clear()
    resp = await async_client.post("/api/v1/nia/threads", json={})
    assert resp.status_code == 401


def test_migration_037_down_revision() -> None:
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "migrations/versions/037_nia_threads.py"
    spec = importlib.util.spec_from_file_location("migration_037", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "037_nia_threads"
    assert module.down_revision == "036_picks"
