"""Nia HITL audit trail and transfer_draft resume payload tests."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.config import settings
import app.nia  # noqa: F401 — register tools

models.ALLOW_MODEL_REQUESTS = False

ACCEPT_FOLLOW_UP = "Transfer approved."


class ArgsTestModel(TestModel):
    """TestModel that calls one tool with fixed arguments."""

    def __init__(self, tool_name: str, tool_args: dict, **kwargs) -> None:
        self._fixed_tool_name = tool_name
        self._fixed_tool_args = tool_args
        super().__init__(call_tools=[tool_name], **kwargs)

    def gen_tool_args(self, tool_def):
        if tool_def.name == self._fixed_tool_name:
            return self._fixed_tool_args
        return super().gen_tool_args(tool_def)


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
    *models_to_use,
) -> None:
    state = {"index": 0}

    def build_nia_model():
        model = models_to_use[state["index"]]
        if state["index"] < len(models_to_use) - 1:
            state["index"] += 1
        return model

    monkeypatch.setattr("app.services.nia_run.build_nia_model", build_nia_model)


def _tool_call_model(tool_name: str, args: dict) -> ArgsTestModel:
    return ArgsTestModel(tool_name, args)


def _thread_text_blob(thread_json: dict) -> str:
    return json.dumps(thread_json)


async def _approve_playground_transfer(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    *,
    our_ref: str = "NIA-AUDIT-TRF",
) -> tuple[AsyncClient, str, str, str]:
    from tests.test_transfers import _receive_qty_at_location

    await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref=our_ref,
    )

    _patch_sequential_models(
        monkeypatch,
        _tool_call_model(
            "propose_transfer",
            {
                "from_location": "Kramerville",
                "to_location": "Bedfordview",
                "sku": our_ref,
                "qty": 1,
            },
        ),
        TestModel(custom_output_text=ACCEPT_FOLLOW_UP),
    )

    warehouse = await _login(
        async_client, "warehouse@example.com", settings.seed_warehouse_password
    )
    thread_id = await _create_thread(warehouse)

    run = await warehouse.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "propose transfer"},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread_before = await warehouse.get(f"/api/v1/nia/threads/{thread_id}")
    assistant = next(m for m in thread_before.json()["messages"] if m["role"] == "assistant")
    tool_call_id = assistant["structured_payload"]["tool_call_id"]

    resume = await warehouse.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={"decision": "accept", "tool_call_id": tool_call_id},
    )
    assert resume.status_code == 200
    await _consume_stream(resume)

    return warehouse, thread_id, our_ref, tool_call_id


async def test_approve_transfer_records_audit_and_draft(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warehouse, thread_id, _, _ = await _approve_playground_transfer(
        async_client,
        owner_client,
        monkeypatch,
    )

    audit = await warehouse.get(f"/api/v1/nia/threads/{thread_id}/audit")
    assert audit.status_code == 200
    rows = audit.json()
    assert len(rows) == 1
    assert rows[0]["decision"] == "accept"
    assert rows[0]["tool_name"] == "propose_transfer"
    assert rows[0]["entity_type"] == "transfer"
    assert rows[0]["entity_id"] is not None

    transfers = await warehouse.get("/api/v1/transfers")
    assert transfers.status_code == 200
    drafts = [row for row in transfers.json() if row["status"] == "draft"]
    assert any(row["transfer_number"].startswith("TRF-") for row in drafts)


async def test_cancel_draft_then_second_cancel_409(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warehouse, _, _, _ = await _approve_playground_transfer(
        async_client,
        owner_client,
        monkeypatch,
        our_ref="NIA-AUDIT-CANCEL",
    )

    transfers = await warehouse.get("/api/v1/transfers")
    draft = next(row for row in transfers.json() if row["status"] == "draft")

    first = await warehouse.post(f"/api/v1/transfers/{draft['id']}/cancel")
    assert first.status_code == 200
    assert first.json()["status"] == "cancelled"

    second = await warehouse.post(f"/api/v1/transfers/{draft['id']}/cancel")
    assert second.status_code == 409


async def test_resume_structured_payload_transfer_draft_citations(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warehouse, thread_id, _, _ = await _approve_playground_transfer(
        async_client,
        owner_client,
        monkeypatch,
        our_ref="NIA-AUDIT-PAYLOAD",
    )

    thread = await warehouse.get(f"/api/v1/nia/threads/{thread_id}")
    assistants = [m for m in thread.json()["messages"] if m["role"] == "assistant"]
    resume_msg = assistants[-1]
    payload = resume_msg["structured_payload"]
    assert payload["kind"] == "transfer_draft"
    assert payload["undoable"] is True
    assert payload["transfer_number"].startswith("TRF-")
    assert any(citation["label"] == payload["transfer_number"] for citation in payload["citations"])

    blob = _thread_text_blob(thread.json()).lower()
    assert "openrouter" not in blob
    assert settings.openrouter_api_key.lower() not in blob


async def test_cross_user_get_audit_404(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warehouse, thread_id, _, _ = await _approve_playground_transfer(
        async_client,
        owner_client,
        monkeypatch,
        our_ref="NIA-AUDIT-404",
    )

    books = await _login(async_client, "books@example.com", settings.seed_books_password)
    audit = await books.get(f"/api/v1/nia/threads/{thread_id}/audit")
    assert audit.status_code == 404


async def test_dispatch_then_cancel_409_for_warehouse(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warehouse, _, _, _ = await _approve_playground_transfer(
        async_client,
        owner_client,
        monkeypatch,
        our_ref="NIA-AUDIT-DISPATCH",
    )

    transfers = await warehouse.get("/api/v1/transfers")
    draft = next(row for row in transfers.json() if row["status"] == "draft")

    dispatch = await warehouse.post(f"/api/v1/transfers/{draft['id']}/dispatch")
    assert dispatch.status_code == 200
    assert dispatch.json()["status"] == "in_transit"

    cancel = await warehouse.post(f"/api/v1/transfers/{draft['id']}/cancel")
    assert cancel.status_code == 409
