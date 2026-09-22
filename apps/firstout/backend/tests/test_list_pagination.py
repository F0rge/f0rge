"""Paginated list endpoints for books and operations documents."""

from __future__ import annotations

from httpx import AsyncClient

from tests.pdf_fixture import MINIMAL_PDF


async def _create_customer(owner_client: AsyncClient, name: str) -> str:
    resp = await owner_client.post("/api/v1/customers", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_supplier(owner_client: AsyncClient, name: str) -> str:
    resp = await owner_client.post("/api/v1/suppliers", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_sku(owner_client: AsyncClient, our_ref: str) -> dict:
    resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": our_ref,
            "our_barcode": f"{our_ref}-BAR",
            "name": f"Name {our_ref}",
            "design": f"Design {our_ref}",
            "fabric": "Fabric",
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _account_ids(owner_client: AsyncClient) -> dict[str, str]:
    resp = await owner_client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account["id"] for account in resp.json()}


async def test_invoice_list_pagination(owner_client: AsyncClient) -> None:
    alpha_id = await _create_customer(owner_client, "Alpha Furnishings")
    beta_id = await _create_customer(owner_client, "Beta Interiors")

    first = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": alpha_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Alpha table", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": beta_id,
            "issue_date": "2026-09-02",
            "lines": [{"description": "Beta chair", "qty": 1, "unit_ex_vat": "200.00"}],
        },
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    page = await owner_client.get("/api/v1/invoices")
    assert page.status_code == 200
    body = page.json()
    assert "items" in body and "total" in body
    assert body["total"] >= 2
    assert len(body["items"]) >= 2
    assert "lines" not in body["items"][0]

    detail = await owner_client.get(f"/api/v1/invoices/{first_id}")
    assert detail.status_code == 200
    assert detail.json()["lines"]

    limited = await owner_client.get("/api/v1/invoices", params={"limit": 1, "offset": 0})
    assert limited.status_code == 200
    limited_body = limited.json()
    assert len(limited_body["items"]) == 1
    assert limited_body["total"] >= 2

    offset = await owner_client.get("/api/v1/invoices", params={"limit": 1, "offset": 1})
    assert offset.status_code == 200
    offset_ids = {row["id"] for row in offset.json()["items"]}
    assert offset_ids.isdisjoint({limited_body["items"][0]["id"]})

    filtered = await owner_client.get("/api/v1/invoices", params={"q": "Beta"})
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["total"] >= 1
    assert all("Beta" in row["customer_name"] for row in filtered_body["items"])
    assert any(row["id"] == second_id for row in filtered_body["items"])
    assert all(row["id"] != first_id for row in filtered_body["items"])

    bad_limit = await owner_client.get("/api/v1/invoices", params={"limit": 0})
    assert bad_limit.status_code == 422

    bad_limit_high = await owner_client.get("/api/v1/invoices", params={"limit": 101})
    assert bad_limit_high.status_code == 422


async def test_journal_list_pagination(owner_client: AsyncClient) -> None:
    accounts = await _account_ids(owner_client)
    created = await owner_client.post(
        "/api/v1/journals",
        json={
            "entry_date": "2026-09-03",
            "memo": "Pagination rent",
            "source": "manual",
            "status": "posted",
            "lines": [
                {"account_id": accounts["5000"], "debit_zar": "50.00", "credit_zar": "0.00"},
                {"account_id": accounts["1100"], "debit_zar": "0.00", "credit_zar": "50.00"},
            ],
        },
    )
    assert created.status_code == 201
    journal_id = created.json()["id"]

    page = await owner_client.get("/api/v1/journals")
    assert page.status_code == 200
    body = page.json()
    assert body["total"] >= 1
    row = next(item for item in body["items"] if item["id"] == journal_id)
    assert "lines" not in row
    assert row["debit_total_zar"] == "50.00"
    assert row["credit_total_zar"] == "50.00"

    detail = await owner_client.get(f"/api/v1/journals/{journal_id}")
    assert detail.status_code == 200
    assert detail.json()["lines"]

    filtered = await owner_client.get("/api/v1/journals", params={"q": "Pagination"})
    assert filtered.status_code == 200
    assert any(item["id"] == journal_id for item in filtered.json()["items"])


async def test_purchase_order_list_pagination(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Pagination PO Supplier")
    sku = await _create_sku(owner_client, "PG-PAG-1")

    open_po = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 2, "factory_unit_amount": "10.00"}],
        },
    )
    assert open_po.status_code == 201
    open_id = open_po.json()["id"]

    landed_po = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "20.00"}],
        },
    )
    assert landed_po.status_code == 201
    landed_id = landed_po.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{landed_id}/on-water")
    land_resp = await owner_client.post(
        f"/api/v1/purchase-orders/{landed_id}/land",
        data={
            "fx_to_zar": "18.50",
            "factory_invoice_number": "FAC-1",
            "factory_amount": "20.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FRT-1",
            "freight_amount": "5.00",
            "freight_currency": "USD",
            "clearance_invoice_number": "CLR-1",
            "clearance_amount": "2.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("factory.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("freight.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("clearance.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert land_resp.status_code == 200

    page = await owner_client.get("/api/v1/purchase-orders")
    assert page.status_code == 200
    body = page.json()
    assert body["total"] >= 2
    row = next(item for item in body["items"] if item["id"] == open_id)
    assert "lines" not in row
    assert "bills" not in row
    assert row["line_count"] == 1

    detail = await owner_client.get(f"/api/v1/purchase-orders/{open_id}")
    assert detail.status_code == 200
    assert detail.json()["lines"]

    landed_only = await owner_client.get("/api/v1/purchase-orders", params={"status": "landed"})
    assert landed_only.status_code == 200
    landed_body = landed_only.json()
    assert landed_body["total"] >= 1
    assert all(row["status"] == "landed" for row in landed_body["items"])
    assert any(row["id"] == landed_id for row in landed_body["items"])
    assert all(row["id"] != open_id for row in landed_body["items"])
