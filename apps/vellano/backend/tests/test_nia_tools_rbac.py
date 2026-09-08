"""Nia service-tool RBAC and HITL tests."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.config import settings
import app.nia  # noqa: F401 — register tools
from app.nia.tools import _is_allowed_nav_path

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


async def _create_customer(owner_client: AsyncClient, name: str) -> str:
    resp = await owner_client.post("/api/v1/contacts", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_list_overdue_invoices_returns_fixture_id(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_id = await _create_customer(owner_client, "Nia Overdue Customer")
    invoice_resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-07-01",
            "lines": [{"description": "Overdue chair", "qty": 1, "unit_ex_vat": "500.00"}],
        },
    )
    assert invoice_resp.status_code == 201
    invoice_id = invoice_resp.json()["id"]

    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: TestModel(call_tools=["list_overdue_invoices"]),
    )
    books = await _login(async_client, "books@example.com", settings.seed_books_password)
    thread_id = await _create_thread(books)

    run = await books.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "list overdue invoices"},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await books.get(f"/api/v1/nia/threads/{thread_id}")
    assert thread.status_code == 200
    body = thread.json()
    blob = _thread_text_blob(body)
    assert invoice_id in blob
    assert "Nia Overdue Customer" in blob
    remaining = invoice_resp.json()["balance"]
    assert str(remaining) in blob
    assistant = next(m for m in reversed(body["messages"]) if m["role"] == "assistant")
    payload = assistant["structured_payload"]
    assert payload["kind"] == "overdue_invoices"
    match = next(row for row in payload["invoices"] if row["id"] == invoice_id)
    assert match["customer_name"] == "Nia Overdue Customer"
    assert match["remaining_zar"] == str(remaining)
    assert match["issue_date"] == "2026-07-01"
    assert match["terms_days"] == 30
    assert isinstance(match["days_overdue"], int)
    assert match["days_overdue"] >= 0


async def test_till_propose_transfer_denied_without_hitl(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: TestModel(call_tools=["propose_transfer"]),
    )
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    thread_id = await _create_thread(till)

    run = await till.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "transfer stock"},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await till.get(f"/api/v1/nia/threads/{thread_id}")
    messages = thread.json()["messages"]
    assert not any(
        m.get("structured_payload", {}) and m["structured_payload"].get("kind") == "needs_ok"
        for m in messages
        if m["role"] == "assistant"
    )
    blob = _thread_text_blob(thread.json()).lower()
    assert "denied" in blob or "cannot create stock transfers" in blob


async def test_warehouse_propose_transfer_hitl_creates_draft(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_transfers import _receive_qty_at_location

    our_ref = "NIA-TRF-TOOL"
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
    assert assistant["content"] == "Nia needs your approval"
    tool_call_id = assistant["structured_payload"]["tool_call_id"]

    resume = await warehouse.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={"decision": "accept", "tool_call_id": tool_call_id},
    )
    assert resume.status_code == 200
    await _consume_stream(resume)

    transfers = await warehouse.get("/api/v1/transfers")
    assert transfers.status_code == 200
    drafts = [row for row in transfers.json() if row["status"] == "draft"]
    assert any(row["transfer_number"].startswith("TRF-") for row in drafts)


async def test_warehouse_stock_on_hand_hides_cost_owner_shows(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_transfers import _receive_qty_at_location

    our_ref = "NIA-STOCK-COST"
    await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=3,
        location_name="Kramerville",
        our_ref=our_ref,
    )

    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: _tool_call_model(
            "get_stock_on_hand",
            {"sku": our_ref, "location": "Kramerville"},
        ),
    )

    warehouse = await _login(
        async_client, "warehouse@example.com", settings.seed_warehouse_password
    )
    thread_id = await _create_thread(warehouse)
    run = await warehouse.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "stock on hand"},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    wh_thread = await warehouse.get(f"/api/v1/nia/threads/{thread_id}")
    wh_blob = _thread_text_blob(wh_thread.json())
    assert our_ref in wh_blob
    assert "on_hand" in wh_blob
    assert "unit_cost_zar" not in wh_blob

    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: _tool_call_model(
            "get_stock_on_hand",
            {"sku": our_ref, "location": "Kramerville"},
        ),
    )
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    owner_thread_id = await _create_thread(owner)
    owner_run = await owner.post(
        f"/api/v1/nia/threads/{owner_thread_id}/run",
        json={"message": "stock on hand"},
    )
    assert owner_run.status_code == 200
    await _consume_stream(owner_run)

    owner_thread = await owner.get(f"/api/v1/nia/threads/{owner_thread_id}")
    owner_blob = _thread_text_blob(owner_thread.json())
    assert "unit_cost_zar" in owner_blob


async def test_till_navigate_allowed_and_unknown_denied(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    till = await _login(async_client, "till@example.com", settings.seed_till_password)

    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: _tool_call_model("navigate", {"path": "/invoices"}),
    )
    thread_ok = await _create_thread(till)
    ok_run = await till.post(
        f"/api/v1/nia/threads/{thread_ok}/run",
        json={"message": "open invoices"},
    )
    assert ok_run.status_code == 200
    await _consume_stream(ok_run)

    ok_thread = await till.get(f"/api/v1/nia/threads/{thread_ok}")
    ok_assistant = next(m for m in ok_thread.json()["messages"] if m["role"] == "assistant")
    payload = ok_assistant.get("structured_payload")
    assert payload == {"kind": "opened_page", "path": "/invoices"}

    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: _tool_call_model("navigate", {"path": "/not-a-route"}),
    )
    thread_bad = await _create_thread(till)
    bad_run = await till.post(
        f"/api/v1/nia/threads/{thread_bad}/run",
        json={"message": "open mystery page"},
    )
    assert bad_run.status_code == 200
    await _consume_stream(bad_run)

    bad_thread = await till.get(f"/api/v1/nia/threads/{thread_bad}")
    bad_blob = _thread_text_blob(bad_thread.json()).lower()
    assert "denied" in bad_blob or "unknown route" in bad_blob


@pytest.mark.no_db
def test_navigate_allows_invoice_list_and_uuid_detail() -> None:
    assert _is_allowed_nav_path("/invoices")
    assert _is_allowed_nav_path("/invoices/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    assert not _is_allowed_nav_path("/invoices/not-a-uuid")
    assert not _is_allowed_nav_path("/not-a-route")
