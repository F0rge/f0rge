"""Nia Canvas chart tool tests."""

from __future__ import annotations

import datetime

import pytest
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.config import settings
import app.nia  # noqa: F401 — register tools

models.ALLOW_MODEL_REQUESTS = False


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


async def _create_categorized_sku(
    owner_client: AsyncClient,
    our_ref: str,
    name: str,
    category: str,
    location_id: str,
) -> str:
    sku_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": our_ref,
            "our_barcode": f"{our_ref}-BAR",
            "name": name,
            "design": f"Design {our_ref}",
            "fabric": "Linen",
            "category": category,
            "opening_location_id": location_id,
            "opening_qty": 5,
            "opening_unit_cost_zar": "500.00",
        },
    )
    assert sku_resp.status_code == 201
    sku_id = sku_resp.json()["id"]
    price = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"retail_ex_vat": "1000.00" if category == "Dining" else "2000.00"},
    )
    assert price.status_code == 200
    return sku_id


async def _till_sale(
    till_client: AsyncClient,
    location_id: str,
    sku_id: str,
    qty: int = 1,
) -> dict:
    resp = await till_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": location_id,
            "lines": [{"sku_id": sku_id, "qty": qty}],
            "tender": "cash",
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_chart_dining_vs_sofas_emits_canvas_spec(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_purchase_orders import _create_till, _location_id_by_name

    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    dining_sku_id = await _create_categorized_sku(
        owner_client,
        "NIA-CANVAS-DINING",
        "Oak dining table",
        "Dining",
        bedford_id,
    )
    sofa_sku_id = await _create_categorized_sku(
        owner_client,
        "NIA-CANVAS-SOFA",
        "London sofa",
        "Seating",
        bedford_id,
    )

    till = await _create_till(async_client, owner_client)
    dining_sale = await _till_sale(till, bedford_id, dining_sku_id)
    sofa_sale = await _till_sale(till, bedford_id, sofa_sku_id)

    today = datetime.date.today()
    assert dining_sale["issue_date"] == today.isoformat()
    assert sofa_sale["issue_date"] == today.isoformat()

    expected_dining = float(dining_sale["total_inc_vat"])
    expected_sofas = float(sofa_sale["total_inc_vat"])

    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: TestModel(call_tools=["chart_dining_vs_sofas"]),
    )
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    thread_id = await _create_thread(owner)

    run = await owner.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "chart dining vs sofas on canvas"},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    assert thread.status_code == 200
    assistant = next(m for m in thread.json()["messages"] if m["role"] == "assistant")
    payload = assistant["structured_payload"]
    assert payload["kind"] == "canvas_spec"
    assert payload["path"] == "/canvas"
    assert payload["title"] == "Dining vs sofas this month"

    bar = payload["components"][0]
    assert bar["type"] == "bar"
    assert bar["id"] == "dining-vs-sofas"
    assert bar["categories"] == ["Dining", "Sofas"]
    values = bar["series"][0]["values"]
    assert values == [expected_dining, expected_sofas]
    assert expected_dining == pytest.approx(1150.0)
    assert expected_sofas == pytest.approx(2300.0)


async def test_till_can_run_chart_dining_vs_sofas(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: TestModel(call_tools=["chart_dining_vs_sofas"]),
    )
    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    thread_id = await _create_thread(till)

    run = await till.post(
        f"/api/v1/nia/threads/{thread_id}/run",
        json={"message": "show dining vs sofas chart"},
    )
    assert run.status_code == 200
    await _consume_stream(run)

    thread = await till.get(f"/api/v1/nia/threads/{thread_id}")
    assert thread.status_code == 200
    assistant = next(m for m in thread.json()["messages"] if m["role"] == "assistant")
    payload = assistant["structured_payload"]
    assert payload["kind"] == "canvas_spec"
    assert payload["path"] == "/canvas"
    bar = payload["components"][0]
    assert bar["categories"] == ["Dining", "Sofas"]
    assert bar["series"][0]["values"] == [0.0, 0.0]
