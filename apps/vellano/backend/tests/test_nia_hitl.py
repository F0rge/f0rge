"""Nia HITL deferred-tool approval tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.config import settings
import app.nia  # noqa: F401 — register deferred tools

models.ALLOW_MODEL_REQUESTS = False

ECHO_USER_MESSAGE = "echo with approval"
ACCEPT_FOLLOW_UP = "Echo was approved."
DECLINE_FOLLOW_UP = "User declined the echo."


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


async def _create_thread(client: AsyncClient) -> str:
    create = await client.post("/api/v1/nia/threads", json={})
    assert create.status_code == 201
    return create.json()["id"]


def _patch_sequential_models(
    monkeypatch: pytest.MonkeyPatch,
    *models_to_use: TestModel,
) -> None:
    state = {"index": 0}

    def build_nia_model() -> TestModel:
        model = models_to_use[state["index"]]
        if state["index"] < len(models_to_use) - 1:
            state["index"] += 1
        return model

    monkeypatch.setattr("app.services.nia_run.build_nia_model", build_nia_model)


async def test_run_triggers_needs_ok_card(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_sequential_models(
        monkeypatch,
        TestModel(call_tools=["demo_echo_approval"]),
    )
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    thread_id = await _create_thread(till)

    run = await till.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": ECHO_USER_MESSAGE},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await till.get(f"/api/v1/nia/threads/{thread_id}")
    assert thread.status_code == 200
    messages = thread.json()["messages"]
    assistant = next(m for m in messages if m["role"] == "assistant")
    assert assistant["content"] == "Nia needs your approval"
    assert "```" not in assistant["content"]
    payload = assistant["structured_payload"]
    assert payload["kind"] == "needs_ok"
    assert payload["actions"] == ["accept", "decline", "cancel"]
    assert payload["tool_name"] == "demo_echo_approval"
    assert payload["tool_call_id"]


async def test_resume_accept_clears_pending(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_sequential_models(
        monkeypatch,
        TestModel(call_tools=["demo_echo_approval"]),
        TestModel(custom_output_text=ACCEPT_FOLLOW_UP),
    )
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    thread_id = await _create_thread(till)

    run = await till.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": ECHO_USER_MESSAGE},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread_before = await till.get(f"/api/v1/nia/threads/{thread_id}")
    tool_call_id = thread_before.json()["messages"][-1]["structured_payload"]["tool_call_id"]

    resume = await till.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={"decision": "accept", "tool_call_id": tool_call_id},
    )
    assert resume.status_code == 200
    await _consume_stream(resume)

    thread = await till.get(f"/api/v1/nia/threads/{thread_id}")
    messages = thread.json()["messages"]
    assert messages[-1]["content"] == ACCEPT_FOLLOW_UP
    assert "```" not in messages[-1]["content"]
    assert not any(
        m.get("structured_payload", {}) and m["structured_payload"].get("kind") == "needs_ok"
        for m in messages
        if m["role"] == "assistant" and m is messages[-1]
    )


async def test_resume_decline_has_no_approved_side_effect(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_sequential_models(
        monkeypatch,
        TestModel(call_tools=["demo_echo_approval"]),
        TestModel(custom_output_text=DECLINE_FOLLOW_UP),
    )
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    thread_id = await _create_thread(till)

    run = await till.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": ECHO_USER_MESSAGE},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread_before = await till.get(f"/api/v1/nia/threads/{thread_id}")
    tool_call_id = thread_before.json()["messages"][-1]["structured_payload"]["tool_call_id"]

    resume = await till.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={"decision": "decline", "tool_call_id": tool_call_id},
    )
    assert resume.status_code == 200
    await _consume_stream(resume)

    thread = await till.get(f"/api/v1/nia/threads/{thread_id}")
    assistant_contents = [
        m["content"] for m in thread.json()["messages"] if m["role"] == "assistant"
    ]
    assert not any("approved:" in content for content in assistant_contents)


async def test_resume_cancel_clears_pending_without_model_call(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_calls: list[str] = []

    def build_nia_model() -> TestModel:
        build_calls.append("called")
        return TestModel(call_tools=["demo_echo_approval"])

    monkeypatch.setattr("app.services.nia_run.build_nia_model", build_nia_model)

    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    thread_id = await _create_thread(till)

    run = await till.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": ECHO_USER_MESSAGE},
    )
    assert run.status_code == 200
    await _consume_stream(run)
    assert len(build_calls) == 1

    cancel = await till.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={"decision": "cancel"},
    )
    assert cancel.status_code == 200
    assert cancel.json() == {"ok": True}
    assert len(build_calls) == 1

    thread = await till.get(f"/api/v1/nia/threads/{thread_id}")
    messages = thread.json()["messages"]
    assert messages[-1]["content"] == "Cancelled."
    assert messages[-1].get("structured_payload") is None


async def test_resume_without_pending_409(async_client: AsyncClient) -> None:
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    thread_id = await _create_thread(till)

    resp = await till.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={"decision": "accept"},
    )
    assert resp.status_code == 409
