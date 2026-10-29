"""Supplier code prefill and the supplier-facing purchase order PDF."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sku_supplier_price import SkuSupplierPrice
from tests.pdf_fixture import MINIMAL_PDF
from tests.test_purchase_orders import (
    _create_sku,
    _create_supplier,
    _create_warehouse,
    _pdf_text,
    _relogin_owner,
)
from tests.test_reorder import _sku_with_opening


async def _price(
    db: AsyncSession,
    *,
    sku_id: str,
    supplier_id: str,
    supplier_sku: Optional[str],
) -> None:
    db.add(
        SkuSupplierPrice(
            sku_id=uuid.UUID(sku_id),
            supplier_id=uuid.UUID(supplier_id),
            supplier_sku=supplier_sku,
        )
    )
    await db.flush()


def _line_payload(line: dict, **overrides: object) -> dict:
    payload = {
        "id": line["id"],
        "sku_id": line["sku_id"],
        "supplier_code": line["supplier_code"],
        "description": line["description"],
        "notes": line["notes"],
        "qty": line["qty"],
        "factory_unit_amount": line["factory_unit_amount"],
    }
    payload.update(overrides)
    return payload


async def test_create_fills_supplier_code_and_keeps_a_typed_code(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Diron Codes")
    other_id = await _create_supplier(owner_client, "Other Factory")
    per_supplier = await _create_sku(
        owner_client,
        "CODE-PER",
        "CODE-PER-B",
        "Dining table",
        "Oak",
        "Oak veneer",
        supplier_ref="GENERIC-REF",
    )
    fallback = await _create_sku(
        owner_client,
        "CODE-FALL",
        "CODE-FALL-B",
        "Side table",
        "Plain",
        "-",
        supplier_ref="TOP-OAK",
    )
    blank_price = await _create_sku(
        owner_client,
        "CODE-BLANK",
        "CODE-BLANK-B",
        "Coffee table",
        "Plain",
        "Walnut",
        supplier_ref="WALNUT-TOP",
    )
    missing = await _create_sku(
        owner_client,
        "CODE-NONE",
        "CODE-NONE-B",
        "Stool",
        "Plain",
        "Cotton",
    )
    typed = await _create_sku(
        owner_client,
        "CODE-TYPED",
        "CODE-TYPED-B",
        "Chair",
        "Plain",
        "Linen",
        supplier_ref="SHOULD-NOT-WIN",
    )
    await _price(
        async_db,
        sku_id=per_supplier["id"],
        supplier_id=supplier_id,
        supplier_sku="DC-23-11G",
    )
    await _price(
        async_db,
        sku_id=per_supplier["id"],
        supplier_id=other_id,
        supplier_sku="OTHER-FACTORY",
    )
    await _price(
        async_db,
        sku_id=blank_price["id"],
        supplier_id=supplier_id,
        supplier_sku="   ",
    )
    await _price(
        async_db,
        sku_id=typed["id"],
        supplier_id=supplier_id,
        supplier_sku="OTHER-CODE",
    )

    created = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [
                {"sku_id": per_supplier["id"], "qty": 1, "factory_unit_amount": "10.00"},
                {"sku_id": fallback["id"], "qty": 1, "factory_unit_amount": "10.00"},
                {"sku_id": blank_price["id"], "qty": 1, "factory_unit_amount": "10.00"},
                {"sku_id": missing["id"], "qty": 1, "factory_unit_amount": "10.00"},
                {
                    "sku_id": typed["id"],
                    "supplier_code": " KEEP-ME ",
                    "qty": 1,
                    "factory_unit_amount": "10.00",
                },
                {
                    "description": "Loose cushion",
                    "supplier_code": "LOOSE",
                    "qty": 1,
                    "factory_unit_amount": "10.00",
                },
                {
                    "description": "No code yet",
                    "qty": 1,
                    "factory_unit_amount": "10.00",
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    by_name = {line["name"]: line for line in created.json()["lines"]}
    assert by_name["Dining table"]["supplier_code"] == "DC-23-11G"
    assert by_name["Side table"]["supplier_code"] == "TOP-OAK"
    assert by_name["Coffee table"]["supplier_code"] == "WALNUT-TOP"
    assert by_name["Stool"]["supplier_code"] is None
    assert by_name["Chair"]["supplier_code"] == "KEEP-ME"
    assert by_name["Loose cushion"]["supplier_code"] == "LOOSE"
    assert by_name["No code yet"]["supplier_code"] is None


async def test_update_fills_a_blank_code_and_keeps_a_typed_code(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Update Factory")
    first = await _create_sku(
        owner_client,
        "UPD-1",
        "UPD-1-B",
        "First table",
        "Design UPD-1",
        "Oak",
        supplier_ref="REF-1",
    )
    second = await _create_sku(
        owner_client,
        "UPD-2",
        "UPD-2-B",
        "Second table",
        "Design UPD-2",
        "Oak",
        supplier_ref="REF-2",
    )
    third = await _create_sku(
        owner_client,
        "UPD-3",
        "UPD-3-B",
        "Third table",
        "Design UPD-3",
        "Oak",
        supplier_ref="REF-3",
    )
    await _price(
        async_db,
        sku_id=first["id"],
        supplier_id=supplier_id,
        supplier_sku="FACTORY-1",
    )
    await _price(
        async_db,
        sku_id=second["id"],
        supplier_id=supplier_id,
        supplier_sku="FACTORY-2",
    )

    created = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "submit_for_approval": True,
            "lines": [
                {"sku_id": first["id"], "qty": 2, "factory_unit_amount": "15.00"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    po_id = created.json()["id"]
    original = created.json()["lines"][0]
    assert original["supplier_code"] == "FACTORY-1"

    typed = await owner_client.patch(
        f"/api/v1/purchase-orders/{po_id}",
        json={"lines": [_line_payload(original, supplier_code="HAND")]},
    )
    assert typed.status_code == 200, typed.text
    assert typed.json()["lines"][0]["supplier_code"] == "HAND"

    cleared = await owner_client.patch(
        f"/api/v1/purchase-orders/{po_id}",
        json={"lines": [_line_payload(typed.json()["lines"][0], supplier_code=None)]},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["lines"][0]["supplier_code"] == "FACTORY-1"

    whitespace = await owner_client.patch(
        f"/api/v1/purchase-orders/{po_id}",
        json={"lines": [_line_payload(cleared.json()["lines"][0], supplier_code="   ")]},
    )
    assert whitespace.status_code == 200, whitespace.text
    kept = whitespace.json()["lines"][0]
    assert kept["supplier_code"] == "FACTORY-1"

    added = await owner_client.patch(
        f"/api/v1/purchase-orders/{po_id}",
        json={
            "lines": [
                _line_payload(kept),
                {
                    "sku_id": second["id"],
                    "supplier_code": "KEEP-2",
                    "qty": 1,
                    "factory_unit_amount": "12.00",
                },
                {
                    "sku_id": third["id"],
                    "qty": 1,
                    "factory_unit_amount": "9.00",
                },
            ]
        },
    )
    assert added.status_code == 200, added.text
    by_sku = {line["sku_id"]: line for line in added.json()["lines"]}
    assert by_sku[first["id"]]["supplier_code"] == "FACTORY-1"
    assert by_sku[second["id"]]["supplier_code"] == "KEEP-2"
    assert by_sku[third["id"]]["supplier_code"] == "REF-3"


async def test_reorder_draft_po_fills_supplier_code(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    supplier = await _create_supplier(owner_client, "Reorder Factory")
    with_price = await _sku_with_opening(
        owner_client,
        our_ref="RO-CODE-A",
        opening_qty=1,
        reorder_min=4,
        preferred_supplier_id=supplier,
    )
    fallback = await _sku_with_opening(
        owner_client,
        our_ref="RO-CODE-B",
        opening_qty=1,
        reorder_min=4,
        preferred_supplier_id=supplier,
    )
    patched_a = await owner_client.patch(
        f"/api/v1/skus/{with_price['id']}",
        json={"supplier_ref": "REF-A"},
    )
    patched_b = await owner_client.patch(
        f"/api/v1/skus/{fallback['id']}",
        json={"supplier_ref": "REF-B"},
    )
    assert patched_a.status_code == 200
    assert patched_b.status_code == 200
    await _price(
        async_db,
        sku_id=with_price["id"],
        supplier_id=supplier,
        supplier_sku="FACTORY-9",
    )

    resp = await owner_client.post(
        "/api/v1/reorder/draft-po",
        json={"sku_ids": [with_price["id"], fallback["id"]]},
    )
    assert resp.status_code == 201, resp.text
    orders = resp.json()["purchase_orders"]
    assert len(orders) == 1
    by_sku = {line["sku_id"]: line for line in orders[0]["lines"]}
    assert by_sku[with_price["id"]]["supplier_code"] == "FACTORY-9"
    assert by_sku[fallback["id"]]["supplier_code"] == "REF-B"


async def test_purchase_order_pdf_shows_factory_details_and_hides_our_cost(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    supplier = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "Diron Factory", "default_currency": "EUR"},
    )
    assert supplier.status_code == 201
    supplier_id = supplier.json()["id"]
    table = await _create_sku(
        owner_client,
        "OUR-TBL-1",
        "OUR-TBL-1-B",
        "Oak dining table",
        "DC-23",
        "Belgian linen",
        supplier_ref="GENERIC-REF",
    )
    bare = await _create_sku(
        owner_client,
        "OUR-TOP-2",
        "OUR-TOP-2-B",
        "Bare top",
        "Plain",
        "-",
        supplier_ref="TOP-ONLY",
    )
    priced = await owner_client.patch(
        f"/api/v1/skus/{table['id']}",
        json={
            "retail_ex_vat": "98765.43",
            "wholesale_ex_vat": "87654.32",
            "stockist_ex_vat": "76543.21",
            "decorator_ex_vat": "65432.10",
        },
    )
    assert priced.status_code == 200
    await _price(
        async_db,
        sku_id=table["id"],
        supplier_id=supplier_id,
        supplier_sku="DC-23-11G",
    )

    created = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "supplier_ref": "PI-2026-14",
            "notes": "Call the factory before cutting.",
            "lines": [
                {
                    "sku_id": table["id"],
                    "description": "Oak dining table 180",
                    "notes": "Confirm oak sample",
                    "qty": 2,
                    "factory_unit_amount": "80.00",
                },
                {
                    "sku_id": bare["id"],
                    "qty": 1,
                    "factory_unit_amount": "40.00",
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    po_id = created.json()["id"]
    po_number = created.json()["po_number"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    landed = await owner_client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "17.25",
            "factory_invoice_number": "FAC-EUR",
            "factory_amount": "200.00",
            "factory_currency": "EUR",
            "freight_invoice_number": "FRE-EUR",
            "freight_amount": "13.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CLR-EUR",
            "clearance_amount": "7.00",
            "clearance_currency": "ZAR",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert landed.status_code == 200, landed.text
    costs = [line["unit_cost_zar"] for line in landed.json()["lines"]]
    assert all(costs)

    pdf = await owner_client.get(f"/api/v1/purchase-orders/{po_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    text = _pdf_text(pdf.content)
    assert "Firstout" in text
    assert "Diron Factory" in text
    assert po_number in text
    assert "PI-2026-14" in text
    assert "Landed" in text
    assert "DRAFT" not in text
    assert "DC-23-11G" in text
    assert "TOP-ONLY" in text
    assert "Oak dining table 180" in text
    assert "OUR-TBL-1" in text
    assert "Belgian linen" in text
    assert "Confirm oak sample" in text
    assert "Call the factory before cutting." in text
    assert "EUR 80.00" in text
    assert "EUR 160.00" in text
    assert "EUR 40.00" in text
    assert "EUR 200.00" in text
    assert text.count("Fabric / finish") == 1
    assert "Fabric / finish: -" not in text
    lowered = text.lower()
    assert "unit cost" not in lowered
    assert "margin" not in lowered
    assert "retail" not in lowered
    assert "wholesale" not in lowered
    assert "stockist" not in lowered
    assert "decorator" not in lowered
    assert "98765.43" not in text
    assert "17.25" not in text
    for cost in costs:
        assert cost not in text
        assert f"{Decimal(cost):.2f}" not in text

    sheet = await owner_client.get(f"/api/v1/purchase-orders/{po_id}/packing-sheet")
    assert sheet.status_code == 200
    sheet_text = _pdf_text(sheet.content)
    assert "DC-23-11G" not in sheet_text
    assert "Belgian linen" in sheet_text


async def test_pending_purchase_order_pdf_is_marked_draft(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Draft Factory")
    sku = await _create_sku(
        owner_client,
        "DRAFT-REF",
        "DRAFT-BAR",
        "Draft sofa",
        "Plain",
        "Cotton",
        supplier_ref="DRAFT-CODE",
    )
    created = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "submit_for_approval": True,
            "supplier_ref": "PF-1",
            "notes": "Hold the order.",
            "lines": [
                {"sku_id": sku["id"], "qty": 3, "factory_unit_amount": "25.00"},
                {"description": "Extra cushion", "qty": 1, "factory_unit_amount": "5.00"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "pending_approval"
    po_id = created.json()["id"]

    pdf = await owner_client.get(f"/api/v1/purchase-orders/{po_id}/pdf")
    assert pdf.status_code == 200
    text = _pdf_text(pdf.content)
    assert "DRAFT" in text
    assert "not approved" in text
    assert "Pending approval" in text
    assert "DRAFT-CODE" in text
    assert "Cotton" in text
    assert "Extra cushion" in text
    assert "USD 25.00" in text
    assert "USD 75.00" in text
    assert "USD 80.00" in text
    assert "Hold the order." in text

    await _relogin_owner(owner_client)
    rejected = await owner_client.post(f"/api/v1/purchase-orders/{po_id}/reject")
    assert rejected.status_code == 200
    blocked = await owner_client.get(f"/api/v1/purchase-orders/{po_id}/pdf")
    assert blocked.status_code == 409


async def test_anyone_who_can_view_a_po_can_download_it(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "View Factory")
    sku = await _create_sku(
        owner_client,
        "VIEW-REF",
        "VIEW-BAR",
        "View chair",
        "Plain",
        "Wool",
        supplier_ref="VIEW-CODE",
    )
    created = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "10.00"}],
        },
    )
    assert created.status_code == 201, created.text
    po_id = created.json()["id"]

    warehouse = await _create_warehouse(async_client, owner_client)
    allowed = await warehouse.get(f"/api/v1/purchase-orders/{po_id}/pdf")
    assert allowed.status_code == 200
    assert "VIEW-CODE" in _pdf_text(allowed.content)

    async_client.cookies.clear()
    anonymous = await async_client.get(f"/api/v1/purchase-orders/{po_id}/pdf")
    assert anonymous.status_code == 401
