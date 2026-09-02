"""Nia thread rename (PATCH) and auto-title from first user message."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.config import settings

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


async def test_owner_patch_rename_shows_in_list_and_get(owner_client: AsyncClient) -> None:
    create = await owner_client.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    thread_id = create.json()["id"]

    patched = await owner_client.patch(
        f"/api/v1/nia/threads/{thread_id}",
        json={"title": "Bedfordview transfer"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Bedfordview transfer"

    listed = await owner_client.get("/api/v1/nia/threads")
    assert listed.status_code == 200
    row = next(r for r in listed.json() if r["id"] == thread_id)
    assert row["title"] == "Bedfordview transfer"

    got = await owner_client.get(f"/api/v1/nia/threads/{thread_id}")
    assert got.status_code == 200
    assert got.json()["title"] == "Bedfordview transfer"


async def test_other_user_patch_returns_404(async_client: AsyncClient) -> None:
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    create = await till.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    thread_id = create.json()["id"]

    warehouse = await _login(
        async_client,
        "warehouse@example.com",
        settings.seed_warehouse_password,
    )
    resp = await warehouse.patch(
        f"/api/v1/nia/threads/{thread_id}",
        json={"title": "Stolen title"},
    )
    assert resp.status_code == 404


@pytest.mark.parametrize("title", ["", "   "])
async def test_patch_empty_or_whitespace_title_returns_422(
    owner_client: AsyncClient,
    title: str,
) -> None:
    create = await owner_client.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    thread_id = create.json()["id"]

    resp = await owner_client.patch(
        f"/api/v1/nia/threads/{thread_id}",
        json={"title": title},
    )
    assert resp.status_code == 422


async def test_patch_logged_out(async_client: AsyncClient) -> None:
    async_client.cookies.clear()
    resp = await async_client.patch(
        f"/api/v1/nia/threads/{uuid.uuid4()}",
        json={"title": "Nope"},
    )
    assert resp.status_code == 401


async def test_first_run_auto_titles_default_thread(async_client: AsyncClient) -> None:
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    create = await till.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    thread_id = create.json()["id"]
    assert create.json()["title"] == "New thread"

    run = await till.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "hello nia rename me", "page": {"path": "/invoices"}},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await till.get(f"/api/v1/nia/threads/{thread_id}")
    assert thread.status_code == 200
    title = thread.json()["title"]
    assert title.startswith("hello nia rename me")
    assert title != "New thread"


async def test_run_does_not_overwrite_custom_title(owner_client: AsyncClient) -> None:
    create = await owner_client.post("/api/v1/nia/threads", json={"title": "Planning"})
    assert create.status_code == 201
    thread_id = create.json()["id"]

    run = await owner_client.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "hello nia rename me", "page": {"path": "/invoices"}},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await owner_client.get(f"/api/v1/nia/threads/{thread_id}")
    assert thread.status_code == 200
    assert thread.json()["title"] == "Planning"
