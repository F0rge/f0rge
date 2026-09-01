"""V2-S7 home hub KPI tests."""

from __future__ import annotations

from httpx import AsyncClient

from tests.test_purchase_orders import _location_id_by_name


async def _kramerville_id(client: AsyncClient) -> str:
    return await _location_id_by_name(client, "Kramerville")


async def test_fresh_home_kpis_are_zero(owner_client: AsyncClient) -> None:
    home = await owner_client.get("/api/v1/home")
    assert home.status_code == 200
    body = home.json()
    assert body["open_returns_count"] == 0
    assert body["open_laybys_count"] == 0
    assert body["low_stock_count"] == 0


async def test_opening_qty_two_counts_as_low_stock(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "HOME-LOW-REF",
            "our_barcode": "HOME-LOW-BAR",
            "name": "Home low stock sofa",
            "design": "Home low design",
            "fabric": "Home low fabric",
            "opening_location_id": location_id,
            "opening_qty": 2,
            "opening_unit_cost_zar": "50.00",
        },
    )
    assert create_resp.status_code == 201

    home = await owner_client.get("/api/v1/home")
    assert home.status_code == 200
    assert home.json()["low_stock_count"] >= 1


async def test_draft_return_increments_open_returns_count(owner_client: AsyncClient) -> None:
    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Home KPI Return Customer"},
    )
    assert customer_resp.status_code == 201
    invoice_resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_resp.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Consulting", "qty": 1, "unit_ex_vat": "500.00"}],
        },
    )
    assert invoice_resp.status_code == 201
    invoice = invoice_resp.json()
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")

    before = await owner_client.get("/api/v1/home")
    assert before.status_code == 200
    assert before.json()["open_returns_count"] == 0

    created = await owner_client.post(
        "/api/v1/returns",
        json={
            "invoice_id": invoice["id"],
            "location_id": bedford_id,
            "reason": "damaged",
            "disposition": "write_off",
            "lines": [{"invoice_line_id": invoice["lines"][0]["id"], "qty": 1}],
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "draft"

    after = await owner_client.get("/api/v1/home")
    assert after.status_code == 200
    assert after.json()["open_returns_count"] == 1


async def test_low_stock_attention_order_links_to_reorder(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "HOME-ORDER-REF",
            "our_barcode": "HOME-ORDER-BAR",
            "name": "Home order sofa",
            "design": "Home order design",
            "fabric": "Home order fabric",
            "opening_location_id": location_id,
            "opening_qty": 2,
            "opening_unit_cost_zar": "50.00",
        },
    )
    assert create_resp.status_code == 201

    home = await owner_client.get("/api/v1/home")
    assert home.status_code == 200
    low = next(item for item in home.json()["needs_attention"] if item["kind"] == "low_stock")
    assert low["href"] == "/reorder"
