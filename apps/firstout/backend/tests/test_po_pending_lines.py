"""Purchase orders can wait for SKUs, then be approved."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sku_supplier_price import SkuSupplierPrice
from tests.pdf_fixture import MINIMAL_PDF
from tests.test_document_intake_proforma import PROFORMA_PDF
from tests.test_purchase_orders import (
    _create_sku,
    _create_supplier,
    _login_as,
    _relogin_owner,
)


async def _user(
    client: AsyncClient,
    owner_client: AsyncClient,
    *,
    email: str,
    password: str,
    role: str,
) -> AsyncClient:
    await _relogin_owner(owner_client)
    created = await owner_client.post(
        "/api/v1/users",
        json={"email": email, "password": password, "role": role},
    )
    assert created.status_code == 201
    return await _login_as(client, email, password)


async def _po(
    client: AsyncClient,
    supplier_id: str,
    lines: list[dict],
    **extra: object,
) -> dict:
    created = await client.post(
        "/api/v1/purchase-orders",
        json={"supplier_id": supplier_id, "lines": lines, **extra},
    )
    assert created.status_code == 201, created.text
    return created.json()


async def test_owner_submit_for_approval_lands_pending(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Submit Supplier")
    sku = await _create_sku(owner_client, "SUB-1", "SUB-B1", "Submit SKU", "Plain", "Cotton")
    body = await _po(
        owner_client,
        supplier_id,
        [{"sku_id": sku["id"], "qty": 2, "factory_unit_amount": "10.00"}],
        supplier_ref="PF-900",
        notes="Hold for Cindy",
        submit_for_approval=True,
    )
    assert body["status"] == "pending_approval"
    assert body["needs_sku_count"] == 0
    assert body["supplier_ref"] == "PF-900"
    assert body["notes"] == "Hold for Cindy"


async def test_owner_create_with_skus_stays_open(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Open Supplier")
    sku = await _create_sku(owner_client, "OPEN-1", "OPEN-B1", "Open SKU", "Plain", "Cotton")
    body = await _po(
        owner_client,
        supplier_id,
        [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "10.00"}],
    )
    assert body["status"] == "open"
    assert body["needs_sku_count"] == 0


async def test_unmatched_line_forces_pending_and_blocks_approve(
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Unmatched Supplier")
    sku = await _create_sku(owner_client, "UNM-1", "UNM-B1", "Matched cushion", "Red", "Linen")
    body = await _po(
        owner_client,
        supplier_id,
        [
            {"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "10.00"},
            {
                "description": "Loose cushion",
                "supplier_code": "LOOSE-1",
                "notes": "colour tbc",
                "qty": 3,
                "factory_unit_amount": "20.00",
            },
        ],
    )
    assert body["status"] == "pending_approval"
    assert body["needs_sku_count"] == 1
    missing = next(line for line in body["lines"] if line["needs_sku"])
    assert missing["sku_id"] is None
    assert missing["description"] == "Loose cushion"
    assert missing["supplier_code"] == "LOOSE-1"

    approve = await owner_client.post(f"/api/v1/purchase-orders/{body['id']}/approve")
    assert approve.status_code == 400
    assert "1 line without a SKU" in approve.json()["detail"]
    assert "before approving" in approve.json()["detail"]
    stored = await owner_client.get(f"/api/v1/purchase-orders/{body['id']}")
    assert stored.json()["status"] == "pending_approval"


async def test_duplicate_sku_rejected_and_two_blank_lines_allowed(
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Dup Supplier")
    sku = await _create_sku(owner_client, "DUP-1", "DUP-B1", "Dup SKU", "Plain", "Cotton")
    duplicate = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [
                {"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "10.00"},
                {"sku_id": sku["id"], "qty": 2, "factory_unit_amount": "10.00"},
            ],
        },
    )
    assert duplicate.status_code == 400
    assert "Duplicate SKU" in duplicate.json()["detail"]

    blank = await _po(
        owner_client,
        supplier_id,
        [
            {"description": "First unknown", "qty": 1, "factory_unit_amount": "5.00"},
            {"description": "Second unknown", "qty": 1, "factory_unit_amount": "6.00"},
        ],
    )
    assert blank["needs_sku_count"] == 2
    assert blank["status"] == "pending_approval"


async def test_buyer_edits_lines_and_warehouse_cannot(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Edit Supplier")
    first = await _create_sku(owner_client, "EDT-1", "EDT-B1", "First", "A", "Cotton")
    second = await _create_sku(owner_client, "EDT-2", "EDT-B2", "Second", "B", "Linen")
    body = await _po(
        owner_client,
        supplier_id,
        [
            {
                "sku_id": first["id"],
                "description": "Keep me",
                "qty": 1,
                "factory_unit_amount": "10.00",
            },
            {
                "description": "Fill me",
                "supplier_code": "FILL",
                "qty": 2,
                "factory_unit_amount": "15.00",
            },
            {
                "description": "Drop me",
                "qty": 1,
                "factory_unit_amount": "8.00",
            },
        ],
    )
    kept = next(line for line in body["lines"] if line["sku_id"] == first["id"])
    fill = next(line for line in body["lines"] if line["description"] == "Fill me")

    buyer = await _user(
        async_client,
        owner_client,
        email="buyer-pending-sku@example.com",
        password="buyer-password",
        role="buyer",
    )
    patched = await buyer.patch(
        f"/api/v1/purchase-orders/{body['id']}",
        json={
            "supplier_ref": "INV-44",
            "notes": "Cindy filled the SKU",
            "lines": [
                {
                    "id": kept["id"],
                    "sku_id": first["id"],
                    "description": "Keep me",
                    "qty": 4,
                    "factory_unit_amount": "11.50",
                },
                {
                    "id": fill["id"],
                    "sku_id": second["id"],
                    "supplier_code": "FILL",
                    "description": "Filled from the catalogue",
                    "qty": 6,
                    "factory_unit_amount": "18.00",
                },
                {
                    "description": "Added while pending",
                    "qty": 1,
                    "factory_unit_amount": "9.00",
                },
            ],
        },
    )
    assert patched.status_code == 200, patched.text
    edited = patched.json()
    assert edited["supplier_ref"] == "INV-44"
    assert edited["needs_sku_count"] == 1
    assert len(edited["lines"]) == 3
    updated_kept = next(line for line in edited["lines"] if line["sku_id"] == first["id"])
    assert updated_kept["qty"] == 4
    assert Decimal(updated_kept["factory_unit_amount"]) == Decimal("11.50")
    filled = next(line for line in edited["lines"] if line["sku_id"] == second["id"])
    assert filled["description"] == "Filled from the catalogue"
    added = next(line for line in edited["lines"] if line["needs_sku"])

    removed = await buyer.patch(
        f"/api/v1/purchase-orders/{body['id']}",
        json={
            "lines": [
                {
                    "id": updated_kept["id"],
                    "sku_id": first["id"],
                    "qty": 4,
                    "factory_unit_amount": "11.50",
                    "description": "Keep me",
                },
                {
                    "id": filled["id"],
                    "sku_id": second["id"],
                    "qty": 6,
                    "factory_unit_amount": "18.00",
                    "description": "Filled from the catalogue",
                },
            ],
        },
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["needs_sku_count"] == 0, removed.text
    assert all(line["id"] != added["id"] for line in removed.json()["lines"])

    await _relogin_owner(owner_client)
    approved = await owner_client.post(f"/api/v1/purchase-orders/{body['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "open"

    locked = await buyer.patch(
        f"/api/v1/purchase-orders/{body['id']}",
        json={
            "lines": [
                {
                    "id": updated_kept["id"],
                    "sku_id": first["id"],
                    "qty": 1,
                    "factory_unit_amount": "11.50",
                    "description": "Too late",
                },
            ],
        },
    )
    assert locked.status_code == 409

    warehouse = await _user(
        async_client,
        owner_client,
        email="warehouse-pending-sku@example.com",
        password="warehouse-password",
        role="warehouse",
    )
    forbidden = await warehouse.patch(
        f"/api/v1/purchase-orders/{body['id']}",
        json={
            "lines": [
                {
                    "description": "Warehouse should not edit this",
                    "qty": 1,
                    "factory_unit_amount": "1.00",
                }
            ]
        },
    )
    assert forbidden.status_code == 403


async def test_inline_sku_create_then_approve(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Inline Supplier")
    body = await _po(
        owner_client,
        supplier_id,
        [
            {
                "description": "Navy square cushion",
                "supplier_code": "NAV-SQ",
                "qty": 5,
                "factory_unit_amount": "42.50",
            }
        ],
    )
    line_id = body["lines"][0]["id"]
    buyer = await _user(
        async_client,
        owner_client,
        email="buyer-inline-sku@example.com",
        password="buyer-password",
        role="buyer",
    )
    created = await buyer.post(
        f"/api/v1/purchase-orders/{body['id']}/lines/{line_id}/sku",
        json={
            "our_ref": "NAV-SQ",
            "our_barcode": "csv:NAV-SQ",
            "name": "Navy square cushion",
            "design": "csv:NAV-SQ",
            "fabric": "-",
        },
    )
    assert created.status_code == 200, created.text
    line = created.json()["lines"][0]
    assert line["needs_sku"] is False
    assert line["our_ref"] == "NAV-SQ"
    assert line["our_barcode"] == "csv:NAV-SQ"
    assert created.json()["needs_sku_count"] == 0

    sku = await owner_client.get(f"/api/v1/skus/{line['sku_id']}")
    assert sku.status_code == 200
    assert sku.json()["preferred_supplier_id"] == supplier_id

    prices = (
        (
            await async_db.execute(
                select(SkuSupplierPrice).where(SkuSupplierPrice.sku_id == uuid.UUID(line["sku_id"]))
            )
        )
        .scalars()
        .all()
    )
    assert len(prices) == 1
    assert prices[0].supplier_sku == "NAV-SQ"
    assert prices[0].latest_price == Decimal("42.50")

    again = await buyer.post(
        f"/api/v1/purchase-orders/{body['id']}/lines/{line_id}/sku",
        json={
            "our_ref": "NAV-SQ-2",
            "our_barcode": "csv:NAV-SQ-2",
            "name": "Duplicate",
            "design": "csv:NAV-SQ-2",
            "fabric": "-",
        },
    )
    assert again.status_code == 409

    await _relogin_owner(owner_client)
    approved = await owner_client.post(f"/api/v1/purchase-orders/{body['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "open"


async def test_downstream_steps_refuse_a_line_without_a_sku(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Downstream Supplier")
    sku = await _create_sku(owner_client, "DWN-1", "DWN-B1", "Downstream SKU", "Plain", "Cotton")
    body = await _po(
        owner_client,
        supplier_id,
        [
            {"sku_id": sku["id"], "qty": 2, "factory_unit_amount": "10.00"},
            {"description": "No code yet", "qty": 1, "factory_unit_amount": "12.00"},
        ],
    )
    po_id = body["id"]

    on_water = await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    assert on_water.status_code == 400
    assert "without a SKU" in on_water.json()["detail"]
    assert "before this step" in on_water.json()["detail"]

    sheet = await owner_client.get(f"/api/v1/purchase-orders/{po_id}/packing-sheet")
    assert sheet.status_code == 400
    assert "without a SKU" in sheet.json()["detail"]

    location = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Pending SKU bay", "type": "warehouse"},
    )
    assert location.status_code == 201
    received = await owner_client.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_id, "location_id": location.json()["id"]},
    )
    assert received.status_code == 400
    assert "without a SKU" in received.json()["detail"]

    landed = await owner_client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "1.00",
            "factory_invoice_number": "FAC",
            "factory_amount": "10.00",
            "factory_currency": "ZAR",
            "freight_invoice_number": "FRE",
            "freight_amount": "1.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CLR",
            "clearance_amount": "1.00",
            "clearance_currency": "ZAR",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert landed.status_code == 400
    assert "without a SKU" in landed.json()["detail"]

    inventory = await owner_client.get("/api/v1/inventory")
    row = next((item for item in inventory.json() if item["sku_id"] == sku["id"]), None)
    assert row is None or row["on_order"] == 0

    await owner_client.patch(f"/api/v1/skus/{sku['id']}", json={"reorder_min": 5})
    reorder = await owner_client.get("/api/v1/reorder")
    assert reorder.status_code == 200
    listed = next(item for item in reorder.json() if item["sku_id"] == sku["id"])
    assert listed["on_order"] == 0
    assert all(item["sku_id"] and item["our_ref"] for item in reorder.json())

    stored = await owner_client.get(f"/api/v1/purchase-orders/{po_id}")
    assert stored.json()["status"] == "pending_approval"


async def test_needs_skus_filter(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Filter Supplier")
    sku = await _create_sku(owner_client, "FLT-1", "FLT-B1", "Filter SKU", "Plain", "Cotton")
    complete = await _po(
        owner_client,
        supplier_id,
        [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "10.00"}],
    )
    waiting = await _po(
        owner_client,
        supplier_id,
        [{"description": "Still blank", "qty": 1, "factory_unit_amount": "10.00"}],
    )
    listed = await owner_client.get(
        "/api/v1/purchase-orders", params={"needs_skus": True, "limit": 50}
    )
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert waiting["id"] in ids
    assert complete["id"] not in ids
    match = next(item for item in listed.json()["items"] if item["id"] == waiting["id"])
    assert match["needs_sku_count"] == 1


async def test_proforma_confirm_keeps_unmatched_lines_pending(owner_client: AsyncClient) -> None:
    supplier = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "Proforma Wait Co", "default_currency": "ZAR"},
    )
    assert supplier.status_code == 201
    supplier_id = supplier.json()["id"]
    sku = await _create_sku(owner_client, "PFW-1", "PFW-B1", "Known cushion", "Red", "Linen")
    payload = {
        "supplier_id": supplier_id,
        "document_number": "PF-WAIT-1",
        "document_date": "2026-03-01",
        "currency": "ZAR",
        "payment_terms": "Balance before dispatch",
        "lines": [
            {
                "supplier_code": "KNOWN",
                "description": "Known cushion",
                "qty": 2,
                "unit_price": "100.00",
                "sku_id": sku["id"],
                "skip": False,
            },
            {
                "supplier_code": "UNKNOWN",
                "description": "Uncoded throw",
                "qty": 1,
                "unit_price": "80.00",
                "sku_id": None,
                "skip": False,
            },
        ],
    }
    resp = await owner_client.post(
        "/api/v1/document-intake/proformas/confirm",
        data={"payload": json.dumps(payload)},
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    order = resp.json()["purchase_order"]
    assert order["status"] == "pending_approval"
    assert order["supplier_ref"] == "PF-WAIT-1"
    assert order["notes"] == "Balance before dispatch"
    assert order["needs_sku_count"] == 1
    unmatched = next(line for line in order["lines"] if line["sku_id"] is None)
    assert unmatched["description"] == "Uncoded throw"
    assert unmatched["supplier_code"] == "UNKNOWN"


async def test_proforma_submit_for_approval_with_every_sku(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Proforma Submit Co")
    sku = await _create_sku(owner_client, "PFS-1", "PFS-B1", "Ready cushion", "Blue", "Linen")
    payload = {
        "supplier_id": supplier_id,
        "document_number": "PF-SUBMIT-1",
        "document_date": "2026-04-02",
        "currency": "ZAR",
        "submit_for_approval": True,
        "lines": [
            {
                "description": "Ready cushion",
                "qty": 1,
                "unit_price": "50.00",
                "sku_id": sku["id"],
                "skip": False,
            }
        ],
    }
    resp = await owner_client.post(
        "/api/v1/document-intake/proformas/confirm",
        data={"payload": json.dumps(payload)},
        files={"file": ("ready.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["purchase_order"]["status"] == "pending_approval"
    assert resp.json()["purchase_order"]["needs_sku_count"] == 0
