"""S10 search, home, settings, and unit cost audit tests."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from httpx import AsyncClient

MINIMAL_PDF = b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


async def _create_supplier(client: AsyncClient, name: str = "S10 Supplier") -> str:
    resp = await client.post("/api/v1/suppliers", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_sku(
    client: AsyncClient,
    our_ref: str,
    our_barcode: str,
    name: str = "S10 SKU",
) -> dict:
    resp = await client.post(
        "/api/v1/skus",
        json={
            "our_ref": our_ref,
            "our_barcode": our_barcode,
            "name": name,
            "design": "Design",
            "fabric": "Fabric",
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_po_on_water(
    client: AsyncClient,
    supplier_id: str,
    sku_id: str,
    qty: int = 2,
) -> dict:
    create_resp = await client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku_id, "qty": qty, "factory_unit_amount": "1000.00"}],
        },
    )
    assert create_resp.status_code == 201
    po = create_resp.json()
    on_water = await client.post(f"/api/v1/purchase-orders/{po['id']}/on-water")
    assert on_water.status_code == 200
    return on_water.json()


async def _land_po(client: AsyncClient, po_id: str) -> dict:
    files = {
        "factory_file": ("factory.pdf", BytesIO(MINIMAL_PDF), "application/pdf"),
        "freight_file": ("freight.pdf", BytesIO(MINIMAL_PDF), "application/pdf"),
        "clearance_file": ("clearance.pdf", BytesIO(MINIMAL_PDF), "application/pdf"),
    }
    data = {
        "fx_to_zar": "18.50",
        "factory_invoice_number": "FAC-S10",
        "factory_amount": "2000.00",
        "factory_currency": "USD",
        "freight_invoice_number": "FRE-S10",
        "freight_amount": "500.00",
        "freight_currency": "USD",
        "clearance_invoice_number": "CLR-S10",
        "clearance_amount": "300.00",
        "clearance_currency": "USD",
    }
    resp = await client.post(f"/api/v1/purchase-orders/{po_id}/land", data=data, files=files)
    assert resp.status_code == 200
    return resp.json()


async def test_search_requires_auth(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/search", params={"q": "test"})
    assert resp.status_code == 401


async def test_home_requires_auth(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/home")
    assert resp.status_code == 401


async def test_search_finds_sku_barcode_po_and_invoice(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client)
    sku = await _create_sku(owner_client, "S10-REF", "S10-BARCODE-001")
    po = await _create_po_on_water(owner_client, supplier_id, sku["id"])

    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "S10 Customer"},
    )
    assert customer_resp.status_code == 201
    invoice_resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_resp.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Chair", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert invoice_resp.status_code == 201
    invoice_number = invoice_resp.json()["invoice_number"]

    sku_search = await owner_client.get("/api/v1/search", params={"q": "S10-BARCODE-001"})
    assert sku_search.status_code == 200
    sku_body = sku_search.json()
    assert any(hit["our_barcode"] == "S10-BARCODE-001" for hit in sku_body["skus"])

    po_search = await owner_client.get("/api/v1/search", params={"q": po["po_number"]})
    assert po_search.status_code == 200
    assert any(hit["po_number"] == po["po_number"] for hit in po_search.json()["purchase_orders"])

    inv_search = await owner_client.get("/api/v1/search", params={"q": invoice_number})
    assert inv_search.status_code == 200
    assert any(hit["invoice_number"] == invoice_number for hit in inv_search.json()["invoices"])


async def test_home_on_order_differs_from_on_hand_when_on_water(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Home Supplier")
    sku = await _create_sku(owner_client, "HOME-REF", "HOME-BAR", name="Home SKU")
    await _create_po_on_water(owner_client, supplier_id, sku["id"], qty=3)

    home = await owner_client.get("/api/v1/home")
    assert home.status_code == 200
    body = home.json()
    assert body["on_order_qty"] >= 3
    assert body["on_hand_qty"] == 0
    assert Decimal(body["on_order_value_zar"]) > 0
    assert Decimal(body["on_hand_value_zar"]) == 0


async def test_land_inserts_cost_audit(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Audit Supplier")
    sku = await _create_sku(owner_client, "AUD-REF", "AUD-BAR")
    po = await _create_po_on_water(owner_client, supplier_id, sku["id"])
    await _land_po(owner_client, po["id"])

    audit_resp = await owner_client.get(f"/api/v1/skus/{sku['id']}/cost-audit")
    assert audit_resp.status_code == 200
    rows = audit_resp.json()
    assert len(rows) >= 1
    land_row = next(row for row in rows if row["source"] == "land")
    assert land_row["old_cost_zar"] is None
    assert Decimal(land_row["new_cost_zar"]) > 0
    assert land_row["changed_by_email"]


async def test_cost_correction_inserts_audit(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Correct Supplier")
    sku = await _create_sku(owner_client, "COR-REF", "COR-BAR")
    po = await _create_po_on_water(owner_client, supplier_id, sku["id"], qty=1)
    landed = await _land_po(owner_client, po["id"])

    loc_resp = await owner_client.get("/api/v1/locations")
    location_id = loc_resp.json()[0]["id"]
    receive_resp = await owner_client.post(
        "/api/v1/receive",
        json={"purchase_order_id": landed["id"], "location_id": location_id},
    )
    assert receive_resp.status_code == 200

    patch_resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}/unit-cost",
        json={"location_id": location_id, "unit_cost_zar": "9999.0000"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["source"] == "correction"

    audit_resp = await owner_client.get(f"/api/v1/skus/{sku['id']}/cost-audit")
    correction_rows = [row for row in audit_resp.json() if row["source"] == "correction"]
    assert len(correction_rows) == 1
    assert Decimal(correction_rows[0]["new_cost_zar"]) == Decimal("9999.0000")


async def test_settings_default_vat_is_15_percent(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["home_currency"] == "ZAR"
    assert Decimal(body["vat_rate"]) == Decimal("0.15")
    assert Decimal(body["vat_percent"]) == Decimal("15.00")
    assert body["defaults_locked"] is True


async def test_settings_mutate_owner_only(
    owner_client: AsyncClient, async_client: AsyncClient
) -> None:
    books_resp = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "books-s10@example.com",
            "password": "books-password",
            "role": "books",
        },
    )
    assert books_resp.status_code == 201

    async_client.cookies.clear()
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books-s10@example.com", "password": "books-password"},
    )
    assert login.status_code == 200

    patch = await async_client.patch(
        "/api/v1/settings",
        json={"vat_rate": "0.14"},
    )
    assert patch.status_code == 403

    get_settings = await async_client.get("/api/v1/settings")
    assert get_settings.status_code == 200


async def test_cost_audit_forbidden_for_till(
    owner_client: AsyncClient,
    async_client: AsyncClient,
) -> None:
    await _create_supplier(owner_client)
    sku = await _create_sku(owner_client, "TILL-REF", "TILL-BAR")

    till_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-s10@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert till_user.status_code == 201

    async_client.cookies.clear()
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-s10@example.com", "password": "till-password"},
    )
    assert login.status_code == 200

    audit = await async_client.get(f"/api/v1/skus/{sku['id']}/cost-audit")
    assert audit.status_code == 403
