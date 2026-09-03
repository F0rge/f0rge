"""Nia action catalog (#596 T0) — freeze, RBAC list, create_sku HITL."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ToolCallPart
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.config import settings
from app.nia.catalog import CATALOG
from app.nia.hitl import pending_from_deferred
import app.nia  # noqa: F401 — register tools

models.ALLOW_MODEL_REQUESTS = False

ACCEPT_FOLLOW_UP = "Approved."

WRITE_IDS = frozenset(
    {
        "create_sku",
        "update_sku",
        "delete_sku",
        "replace_sku_bom",
        "create_supplier",
        "create_proforma",
        "create_purchase_order",
        "mark_on_water",
        "land_purchase_order",
        "create_reorder_draft_po",
        "receive_purchase_order",
        "create_transfer",
        "dispatch_transfer",
        "receive_transfer",
        "cancel_transfer",
        "create_adjustment",
        "add_adjustment_line",
        "update_adjustment_line",
        "delete_adjustment_line",
        "complete_adjustment",
        "cancel_adjustment",
        "start_stocktake",
        "update_stocktake_line",
        "complete_stocktake",
        "cancel_stocktake",
        "correct_unit_cost",
        "create_location",
        "update_location",
        "create_bin",
        "generate_bin_grid",
        "update_bin",
        "create_pick",
        "update_pick",
        "confirm_pick",
        "complete_pick",
        "cancel_pick",
        "create_customer",
        "update_customer",
        "create_return",
        "complete_return",
        "cancel_return",
        "create_layby",
        "add_layby_payment",
        "complete_layby",
        "cancel_layby",
        "create_delivery",
        "pack_delivery",
        "complete_delivery",
        "cancel_delivery",
        "create_account",
        "update_account",
        "create_contact",
        "create_invoice",
        "create_bill",
        "create_credit_note",
        "create_payment",
        "create_journal",
        "post_journal",
        "void_journal",
        "create_repeating_invoice",
        "update_repeating_invoice",
        "run_repeating_invoice",
        "create_bank_rule",
        "update_bank_rule",
        "delete_bank_rule",
        "match_bank_line",
        "apply_bank_rule",
        "recode_bank_line",
        "upsert_category_map",
        "create_period",
        "lock_period",
        "reopen_period",
        "create_user",
        "update_user",
        "update_profile",
        "create_role",
        "update_role",
        "delete_role",
        "update_settings",
    }
)

READ_IDS = frozenset(
    {
        "list_skus",
        "get_sku",
        "get_sku_bom",
        "list_suppliers",
        "list_proformas",
        "get_proforma",
        "list_purchase_orders",
        "get_purchase_order",
        "list_reorder",
        "list_transfers",
        "get_transfer",
        "list_locations",
        "list_bins",
        "list_customers",
        "get_customer",
        "list_contacts",
        "list_invoices",
        "get_invoice",
        "list_bills",
        "get_bill",
        "list_credit_notes",
        "get_credit_note",
        "list_payments",
        "list_journals",
        "get_journal",
        "list_repeating_invoices",
        "get_repeating_invoice",
        "list_vat201_periods",
        "get_vat201_period",
        "list_users",
        "list_roles",
        "get_settings",
        "home_summary",
        "aged_ar",
        "aged_ap",
        "profit_loss",
        "balance_sheet",
        "stock_valuation",
        "sales_by_sku",
        "trial_balance",
        "vat201_draft",
        "preview_pick",
        "list_returns",
        "get_return",
        "list_laybys",
        "get_layby",
        "list_deliveries",
        "get_delivery",
        "list_adjustments",
        "get_adjustment",
        "list_stocktakes",
        "get_stocktake",
        "lookup_stocktake",
        "list_accounts",
        "list_picks",
        "get_pick",
    }
)


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


def _sku_create_args(suffix: str) -> dict:
    return {
        "our_ref": f"NIA-CAT-{suffix}",
        "our_barcode": f"NIA-BAR-{suffix}",
        "name": f"Catalog SKU {suffix}",
        "design": f"Design {suffix}",
        "fabric": f"Fabric {suffix}",
    }


def test_write_ids_frozen() -> None:
    catalog_writes = {action.id for action in CATALOG if action.write}
    assert catalog_writes == WRITE_IDS
    catalog_ids = {action.id for action in CATALOG}
    assert "create_till_sale" not in catalog_ids
    assert not any(
        "till_sale" in action_id or "create_till" in action_id for action_id in catalog_ids
    )
    assert READ_IDS <= catalog_ids
    preview = next(action for action in CATALOG if action.id == "preview_pick")
    assert preview.write is False


def test_no_httpx_in_nia_package() -> None:
    # Catalog handlers call in-process services — never HTTP-to-self.
    nia_dir = Path(__file__).resolve().parents[1] / "app" / "nia"
    for path in nia_dir.glob("*.py"):
        text = path.read_text()
        assert "import httpx" not in text
        assert "from httpx" not in text


async def test_list_nia_actions_owner_till_buyer(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _listed_ids(email: str, password: str) -> set[str]:
        monkeypatch.setattr(
            "app.services.nia_run.build_nia_model",
            lambda: _tool_call_model("list_nia_actions", {}),
        )
        client = await _login(async_client, email, password)
        thread_id = await _create_thread(client)
        run = await client.post(
            f"/api/v1/nia/threads/{thread_id}/run",
            json={"message": "what can you do"},
        )
        assert run.status_code == 200
        await _consume_stream(run)
        thread = await client.get(f"/api/v1/nia/threads/{thread_id}")
        assert thread.status_code == 200
        return _thread_text_blob(thread.json())

    owner_blob = await _listed_ids("owner@example.com", settings.seed_owner_password)
    for action_id in (
        "create_sku",
        "create_invoice",
        "create_transfer",
        "create_journal",
        "lock_period",
    ):
        assert action_id in owner_blob

    till_blob = await _listed_ids("till@example.com", settings.seed_till_password)
    assert any(
        action_id in till_blob
        for action_id in ("create_customer", "create_layby", "create_return", "create_delivery")
    )
    assert "create_sku" not in till_blob
    assert "create_till_sale" not in till_blob

    buyer_blob = await _listed_ids("buyer@example.com", settings.seed_buyer_password)
    assert "create_sku" in buyer_blob
    assert "create_invoice" not in buyer_blob


async def test_create_sku_owner_hitl_then_exists(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sku_args = _sku_create_args("OWNER")
    _patch_sequential_models(
        monkeypatch,
        _tool_call_model(
            "run_nia_action",
            {"action_id": "create_sku", "args": sku_args},
        ),
        TestModel(custom_output_text=ACCEPT_FOLLOW_UP),
    )
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)

    run = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "create sku"},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread_before = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    assistant = next(m for m in thread_before.json()["messages"] if m["role"] == "assistant")
    assert assistant["content"] == "Nia needs your approval"
    payload = assistant["structured_payload"]
    assert payload["kind"] == "needs_ok"
    tool_call_id = payload["tool_call_id"]

    listed = await owner.get("/api/v1/skus")
    assert listed.status_code == 200
    assert not any(row["our_ref"] == sku_args["our_ref"] for row in listed.json())

    resume = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={"decision": "accept", "tool_call_id": tool_call_id},
    )
    assert resume.status_code == 200
    await _consume_stream(resume)

    after = await owner.get("/api/v1/skus")
    assert after.status_code == 200
    assert any(row["our_ref"] == sku_args["our_ref"] for row in after.json())


async def test_update_sku_hitl_accept_applies_without_second_model_call(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = await owner_client.post("/api/v1/skus", json=_sku_create_args("UPDATE"))
    assert created.status_code == 201
    sku_id = created.json()["id"]
    build_calls: list[str] = []

    def build_nia_model() -> ArgsTestModel:
        build_calls.append("called")
        return _tool_call_model(
            "run_nia_action",
            {
                "action_id": "update_sku",
                "args": {
                    "sku_id": sku_id,
                    "retail_inc_vat": "1500.00",
                    "our_barcode": None,
                },
            },
        )

    monkeypatch.setattr("app.services.nia_run.build_nia_model", build_nia_model)
    owner = await _login(async_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)

    run = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "update it"},
    )
    assert run.status_code == 200
    await _consume_stream(run)
    assert len(build_calls) == 1

    thread_before = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    assistant = next(m for m in thread_before.json()["messages"] if m["role"] == "assistant")
    payload = assistant["structured_payload"]
    assert payload["kind"] == "needs_ok"
    assert payload["action_id"] == "update_sku"
    assert payload["args"] == {"sku_id": sku_id, "retail_inc_vat": "1500.00"}
    assert "retail_inc_vat=1500.00" in payload["body"]
    assert "our_barcode=None" not in payload["body"]

    before = await owner.get(f"/api/v1/skus/{sku_id}")
    assert before.status_code == 200
    assert before.json()["retail_inc_vat"] != "1500.00"

    resume = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={"decision": "accept", "tool_call_id": payload["tool_call_id"]},
    )
    assert resume.status_code == 200
    assert resume.json() == {"ok": True}
    assert len(build_calls) == 1

    after = await owner.get(f"/api/v1/skus/{sku_id}")
    assert after.status_code == 200
    assert after.json()["retail_inc_vat"] == "1500.00"


@pytest.mark.no_db
def test_pending_from_deferred_keeps_one_richest_run_nia_action_approval() -> None:
    sparse = ToolCallPart("run_nia_action", {"action_id": "update_sku"}, tool_call_id="sparse")
    rich = ToolCallPart("run_nia_action", {"action_id": "update_sku"}, tool_call_id="rich")
    output = DeferredToolRequests(
        approvals=[sparse, rich],
        metadata={
            "sparse": {
                "kind": "needs_ok",
                "title": "Update SKU",
                "body": "Update SKU: sku_id=sku-1",
                "action_id": "update_sku",
                "args": {"sku_id": "sku-1"},
            },
            "rich": {
                "kind": "needs_ok",
                "title": "Update SKU",
                "body": "Update SKU: sku_id=sku-1, retail_inc_vat=1500.00",
                "action_id": "update_sku",
                "args": {"sku_id": "sku-1", "retail_inc_vat": "1500.00"},
            },
        },
    )

    pending = pending_from_deferred(output)

    assert pending is not None
    assert pending["tool_call_id"] == "rich"
    assert pending["tool_name"] == "run_nia_action"
    assert pending["action_id"] == "update_sku"
    assert pending["args"] == {"sku_id": "sku-1", "retail_inc_vat": "1500.00"}


async def test_create_sku_till_permission_string_no_hitl(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sku_args = _sku_create_args("TILL")
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: _tool_call_model(
            "run_nia_action",
            {"action_id": "create_sku", "args": sku_args},
        ),
    )
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    thread_id = await _create_thread(till)
    run = await till.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "create sku"},
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
    assert "catalogue" in blob or "catalogue.mutate" in blob

    listed = await till.get("/api/v1/skus")
    assert listed.status_code == 200
    assert not any(row["our_ref"] == sku_args["our_ref"] for row in listed.json())


async def test_create_sku_validation_no_hitl(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: _tool_call_model(
            "run_nia_action",
            {"action_id": "create_sku", "args": {}},
        ),
    )
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    run = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "create sku"},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    messages = thread.json()["messages"]
    assert not any(
        m.get("structured_payload", {}) and m["structured_payload"].get("kind") == "needs_ok"
        for m in messages
        if m["role"] == "assistant"
    )
    assistant = next(m for m in messages if m["role"] == "assistant")
    payload = assistant.get("structured_payload") or {}
    assert payload.get("kind") == "needs_fields"
    assert payload.get("action_id") == "create_sku"
    field_ids = {field["id"] for field in payload.get("fields", [])}
    assert {"our_ref", "our_barcode", "name", "design", "fabric"} <= field_ids
    blob = _thread_text_blob(thread.json()).lower()
    assert "missing" in blob or "invalid" in blob or "required" in blob or "field" in blob


async def test_create_invoice_hitl_before_mutate(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact = await owner_client.post("/api/v1/contacts", json={"name": "Nia Catalog Contact"})
    assert contact.status_code == 201
    customer_id = contact.json()["id"]
    invoice_args = {
        "customer_id": customer_id,
        "issue_date": "2026-09-01",
        "lines": [{"description": "Nia catalog chair", "qty": 1, "unit_ex_vat": "100.00"}],
    }
    _patch_sequential_models(
        monkeypatch,
        _tool_call_model(
            "run_nia_action",
            {"action_id": "create_invoice", "args": invoice_args},
        ),
        TestModel(custom_output_text=ACCEPT_FOLLOW_UP),
    )
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    run = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "create invoice"},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread_before = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    assistant = next(m for m in thread_before.json()["messages"] if m["role"] == "assistant")
    assert assistant["content"] == "Nia needs your approval"
    assert assistant["structured_payload"]["kind"] == "needs_ok"

    invoices_before = await owner.get("/api/v1/invoices")
    assert invoices_before.status_code == 200
    assert not any(row["customer_id"] == customer_id for row in invoices_before.json())

    resume = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={
            "decision": "accept",
            "tool_call_id": assistant["structured_payload"]["tool_call_id"],
        },
    )
    assert resume.status_code == 200
    await _consume_stream(resume)

    invoices_after = await owner.get("/api/v1/invoices")
    assert invoices_after.status_code == 200
    assert any(row["customer_id"] == customer_id for row in invoices_after.json())


async def test_create_sku_needs_fields_then_hitl(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: _tool_call_model(
            "run_nia_action",
            {"action_id": "create_sku", "args": {}},
        ),
    )
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    run = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "create sku"},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    assistant = next(m for m in thread.json()["messages"] if m["role"] == "assistant")
    assert assistant["structured_payload"]["kind"] == "needs_fields"

    sku_args = _sku_create_args("FIELDS")
    fields_resume = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={"decision": "submit_fields", "fields": sku_args},
    )
    assert fields_resume.status_code == 200

    after_fields = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    approval = next(
        m
        for m in after_fields.json()["messages"]
        if m["role"] == "assistant"
        and (m.get("structured_payload") or {}).get("kind") == "needs_ok"
    )
    listed = await owner.get("/api/v1/skus")
    assert listed.status_code == 200
    assert not any(row["our_ref"] == sku_args["our_ref"] for row in listed.json())

    accept = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/resume",
        json={"decision": "accept", "tool_call_id": approval["structured_payload"]["tool_call_id"]},
    )
    assert accept.status_code == 200

    after = await owner.get("/api/v1/skus")
    assert after.status_code == 200
    assert any(row["our_ref"] == sku_args["our_ref"] for row in after.json())
