"""Nia Canvas clear / replace / add tools (#603)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.config import settings
from app.nia.agent import NIA_INSTRUCTIONS
from app.nia.canvas import (
    add_canvas_component,
    empty_canvas_spec,
    merge_canvas_mode,
    remove_canvas_component,
    set_canvas_spec,
    spec_from_thread_payloads,
)
import app.nia  # noqa: F401 — register tools

models.ALLOW_MODEL_REQUESTS = False


class ArgsTestModel(TestModel):
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


async def _run_tool(
    client: AsyncClient,
    thread_id: str,
    monkeypatch: pytest.MonkeyPatch,
    model: TestModel,
    message: str,
) -> dict:
    monkeypatch.setattr("app.services.nia_run.build_nia_model", lambda: model)
    run = await client.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": message},
    )
    assert run.status_code == 200
    await _consume_stream(run)
    thread = await client.get(f"/api/v1/nia/threads/{thread_id}")
    assert thread.status_code == 200
    assistants = [m for m in thread.json()["messages"] if m["role"] == "assistant"]
    assert assistants
    return assistants[-1]["structured_payload"]


@pytest.mark.no_db
def test_instructions_tell_nia_to_clear_canvas() -> None:
    assert "clear_canvas" in NIA_INSTRUCTIONS
    assert "set_canvas" in NIA_INSTRUCTIONS
    assert "add_canvas_component" in NIA_INSTRUCTIONS
    assert "chart_overdue_invoices" in NIA_INSTRUCTIONS
    assert "my only canvas action" not in NIA_INSTRUCTIONS.lower()


@pytest.mark.no_db
def test_spec_helpers_clear_replace_add_remove() -> None:
    dining = {
        "kind": "canvas_spec",
        "path": "/canvas",
        "title": "Dining vs sofas this month",
        "components": [
            {
                "type": "bar",
                "id": "dining-vs-sofas",
                "title": "Sales",
                "categories": ["Dining", "Sofas"],
                "series": [{"name": "Sales", "values": [1.0, 2.0]}],
            }
        ],
    }
    table = {
        "type": "table",
        "id": "overdue-invoices",
        "title": "Overdue",
        "headers": ["Invoice"],
        "rows": [["INV-0001"]],
    }
    replaced = set_canvas_spec("Overdue invoices", [table])
    assert replaced is not None
    assert [item["id"] for item in replaced["components"]] == ["overdue-invoices"]

    added = add_canvas_component(dining, table)
    assert added is not None
    assert [item["id"] for item in added["components"]] == [
        "dining-vs-sofas",
        "overdue-invoices",
    ]

    removed = remove_canvas_component(added, "dining-vs-sofas")
    assert [item["id"] for item in removed["components"]] == ["overdue-invoices"]

    merged_add = merge_canvas_mode(dining, replaced, "add")
    assert {item["id"] for item in merged_add["components"]} == {
        "dining-vs-sofas",
        "overdue-invoices",
    }
    merged_replace = merge_canvas_mode(dining, replaced, "replace")
    assert [item["id"] for item in merged_replace["components"]] == ["overdue-invoices"]

    cleared = spec_from_thread_payloads([dining, {"kind": "canvas_cleared", "path": "/canvas"}])
    assert cleared == empty_canvas_spec()


async def test_clear_canvas_emits_cleared_payload(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    await _run_tool(
        owner,
        thread_id,
        monkeypatch,
        TestModel(call_tools=["chart_dining_vs_sofas"]),
        "chart dining vs sofas",
    )
    payload = await _run_tool(
        owner,
        thread_id,
        monkeypatch,
        TestModel(call_tools=["clear_canvas"]),
        "clear the canvas",
    )
    assert payload["kind"] == "canvas_cleared"
    assert payload["path"] == "/canvas"
    assert payload.get("cleared_at")


async def test_replace_dining_with_overdue_invoices_table(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer = await owner_client.post("/api/v1/contacts", json={"name": "Canvas Overdue Co"})
    assert customer.status_code == 201
    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-07-01",
            "lines": [{"description": "Overdue sofa", "qty": 1, "unit_ex_vat": "500.00"}],
        },
    )
    assert invoice.status_code == 201
    invoice_number = invoice.json()["invoice_number"]

    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    dining = await _run_tool(
        owner,
        thread_id,
        monkeypatch,
        TestModel(call_tools=["chart_dining_vs_sofas"]),
        "chart dining vs sofas",
    )
    assert dining["components"][0]["id"] == "dining-vs-sofas"

    payload = await _run_tool(
        owner,
        thread_id,
        monkeypatch,
        TestModel(call_tools=["chart_overdue_invoices"]),
        "replace this with overdue invoices",
    )
    assert payload["kind"] == "canvas_spec"
    assert payload["title"] == "Overdue invoices"
    assert len(payload["components"]) == 1
    table = payload["components"][0]
    assert table["type"] == "table"
    assert table["id"] == "overdue-invoices"
    assert invoice_number in {row[0] for row in table["rows"]}


async def test_add_stock_on_hand_keeps_existing_card(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_purchase_orders import _location_id_by_name

    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    sku = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "PG-CANVAS-TABLE",
            "our_barcode": "PG-CANVAS-TABLE-BAR",
            "name": "Playground canvas table",
            "design": "Canvas",
            "fabric": "Oak",
            "category": "Dining",
            "opening_location_id": kramerville_id,
            "opening_qty": 4,
            "opening_unit_cost_zar": "250.00",
        },
    )
    assert sku.status_code == 201

    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    await _run_tool(
        owner,
        thread_id,
        monkeypatch,
        TestModel(call_tools=["chart_dining_vs_sofas"]),
        "chart dining vs sofas",
    )
    payload = await _run_tool(
        owner,
        thread_id,
        monkeypatch,
        ArgsTestModel(
            "chart_stock_on_hand",
            {"sku": "PG-CANVAS-TABLE", "location": "Kramerville", "mode": "add"},
        ),
        "add stock on hand for PG-CANVAS-TABLE at Kramerville underneath",
    )
    ids = [item["id"] for item in payload["components"]]
    assert "dining-vs-sofas" in ids
    assert any(
        item["type"] == "table" and "PG-CANVAS-TABLE" in item["id"].upper()
        for item in payload["components"]
    )
    stock = next(item for item in payload["components"] if item["type"] == "table")
    assert stock["rows"][0][0] == "PG-CANVAS-TABLE"
    assert stock["rows"][0][1] == "Kramerville"
    assert stock["rows"][0][2] == "4"


async def test_chart_sales_by_sku_uses_report_totals(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_nia_canvas import _create_categorized_sku, _till_sale
    from tests.test_purchase_orders import _create_till, _location_id_by_name

    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    sku_id = await _create_categorized_sku(
        owner_client,
        "NIA-CANVAS-SKU-BAR",
        "Canvas sku bar",
        "Dining",
        bedford_id,
    )
    till = await _create_till(async_client, owner_client)
    sale = await _till_sale(till, bedford_id, sku_id)
    expected = float(sale["total_inc_vat"])

    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    payload = await _run_tool(
        owner,
        thread_id,
        monkeypatch,
        ArgsTestModel("chart_sales_by_sku", {"top_n": 8, "mode": "replace"}),
        "chart sales by sku this month",
    )
    assert payload["kind"] == "canvas_spec"
    bar = payload["components"][0]
    assert bar["type"] == "bar"
    assert bar["id"] == "sales-by-sku"
    assert "NIA-CANVAS-SKU-BAR" in bar["categories"]
    sku_index = bar["categories"].index("NIA-CANVAS-SKU-BAR")
    assert bar["series"][0]["values"][sku_index] == pytest.approx(expected)


async def test_set_and_remove_canvas_component(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)
    metric = {
        "type": "metric",
        "id": "open-ar",
        "label": "Open AR",
        "value": "0.00",
    }
    set_payload = await _run_tool(
        owner,
        thread_id,
        monkeypatch,
        ArgsTestModel("set_canvas", {"title": "Morning pack", "components": [metric]}),
        "replace the canvas with a morning pack",
    )
    assert set_payload["title"] == "Morning pack"
    assert set_payload["components"][0]["id"] == "open-ar"

    removed = await _run_tool(
        owner,
        thread_id,
        monkeypatch,
        ArgsTestModel("remove_canvas_component", {"component_id": "open-ar"}),
        "remove the open-ar card",
    )
    assert removed["components"] == []
