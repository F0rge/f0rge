"""Nia thread run (AG-UI SSE) and persistence tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.nia import NiaUsageEvent

models.ALLOW_MODEL_REQUESTS = False

TEST_MODEL_OUTPUT = "Hello from Nia"


@pytest.fixture(autouse=True)
def nia_test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: TestModel(custom_output_text=TEST_MODEL_OUTPUT),
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


async def test_till_run_persists_messages_and_usage(
    async_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    create = await till.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    thread_id = create.json()["id"]

    run = await till.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "hello", "page": {"path": "/invoices"}},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await till.get(f"/api/v1/nia/threads/{thread_id}")
    assert thread.status_code == 200
    messages = thread.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == TEST_MODEL_OUTPUT

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
    assert usage_rows[0].prompt_tokens >= 0
    assert usage_rows[0].completion_tokens >= 0


async def test_run_logged_out(async_client: AsyncClient) -> None:
    async_client.cookies.clear()
    resp = await async_client.post(
        f"/api/v1/nia/threads/{uuid.uuid4()}/run",
        json={"message": "hello"},
    )
    assert resp.status_code == 401


async def test_run_missing_openrouter_key_503(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    create = await till.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    thread_id = create.json()["id"]

    resp = await till.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "hello", "page": {"path": "/invoices"}},
    )
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "nia_llm_unconfigured"
    else:
        assert "nia_llm_unconfigured" in str(detail)
    assert "OPENROUTER" not in resp.text
