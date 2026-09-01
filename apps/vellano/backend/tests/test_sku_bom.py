"""#573 F1 carton_count (A) and virtual kit BOM (B)."""

from __future__ import annotations

from io import BytesIO
from typing import Optional

from httpx import AsyncClient
from pypdf import PdfReader

from tests.test_purchase_orders import (
    _create_supplier,
    _create_till,
    _location_id_by_name,
)
from tests.test_till import _inventory_on_hand


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


async def _sku(
    client: AsyncClient,
    our_ref: str,
    *,
    carton_count: int = 1,
    opening_location_id: Optional[str] = None,
    opening_qty: Optional[int] = None,
    opening_cost: Optional[str] = None,
    retail_ex_vat: Optional[str] = None,
) -> dict:
    payload: dict = {
        "our_ref": our_ref,
        "our_barcode": f"{our_ref}-BAR",
        "name": our_ref,
        "design": f"{our_ref} design",
        "fabric": f"{our_ref} fabric",
        "carton_count": carton_count,
    }
    if opening_location_id is not None:
        payload["opening_location_id"] = opening_location_id
        payload["opening_qty"] = opening_qty
        payload["opening_unit_cost_zar"] = opening_cost
    resp = await client.post("/api/v1/skus", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    if retail_ex_vat is not None:
        patch = await client.patch(
            f"/api/v1/skus/{body['id']}",
            json={"retail_ex_vat": retail_ex_vat},
        )
        assert patch.status_code == 200
        return patch.json()
    return body


async def test_packing_sheet_and_invoice_pdf_carton_text(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "BOM Carton Supplier")
    sku = await _sku(owner_client, "BOM-PACK-SOFA", carton_count=3, retail_ex_vat="8000.00")

    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 2, "factory_unit_amount": "80.00"}],
        },
    )
    assert po_resp.status_code == 201
    sheet = await owner_client.get(f"/api/v1/purchase-orders/{po_resp.json()['id']}/packing-sheet")
    assert sheet.status_code == 200
    pack_text = _pdf_text(sheet.content)
    assert "Qty: 2" in pack_text
    assert "Cartons: 2" in pack_text
    assert "6" in pack_text

    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _sku(
        owner_client,
        "BOM-INV-SOFA",
        carton_count=3,
        opening_location_id=bedford_id,
        opening_qty=2,
        opening_cost="1000.00",
        retail_ex_vat="5000.00",
    )
    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sofa["id"], "qty": 2}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201
    pdf = await owner_client.get(f"/api/v1/invoices/{sale.json()['invoice_id']}/pdf")
    assert pdf.status_code == 200
    assert "Ships in 6 cartons" in _pdf_text(pdf.content)


async def test_bom_rejects_self_parent_and_duplicate_component(
    owner_client: AsyncClient,
) -> None:
    parent = await _sku(owner_client, "BOM-PARENT")
    component = await _sku(owner_client, "BOM-COMP")

    self_parent = await owner_client.put(
        f"/api/v1/skus/{parent['id']}/bom",
        json={"lines": [{"component_sku_id": parent["id"], "qty": 1}]},
    )
    assert self_parent.status_code == 400

    unknown = await owner_client.put(
        f"/api/v1/skus/{parent['id']}/bom",
        json={"lines": [{"component_sku_id": "00000000-0000-0000-0000-000000000099", "qty": 1}]},
    )
    assert unknown.status_code == 404

    dup = await owner_client.put(
        f"/api/v1/skus/{parent['id']}/bom",
        json={
            "lines": [
                {"component_sku_id": component["id"], "qty": 1},
                {"component_sku_id": component["id"], "qty": 2},
            ]
        },
    )
    assert dup.status_code == 400

    empty = await owner_client.get(f"/api/v1/skus/{parent['id']}/bom")
    assert empty.status_code == 200
    assert empty.json() == []


async def test_bom_replace_all_and_is_kit_flag(owner_client: AsyncClient) -> None:
    parent = await _sku(owner_client, "BOM-KIT-PARENT", retail_ex_vat="12000.00")
    frame = await _sku(owner_client, "BOM-KIT-FRAME")
    cushion = await _sku(owner_client, "BOM-KIT-CUSHION")

    put = await owner_client.put(
        f"/api/v1/skus/{parent['id']}/bom",
        json={
            "lines": [
                {"component_sku_id": frame["id"], "qty": 1},
                {"component_sku_id": cushion["id"], "qty": 2},
            ]
        },
    )
    assert put.status_code == 200
    body = put.json()
    assert len(body) == 2
    assert {row["component_sku_id"] for row in body} == {frame["id"], cushion["id"]}

    listed = await owner_client.get(f"/api/v1/skus/{parent['id']}/bom")
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    got = await owner_client.get(f"/api/v1/skus/{parent['id']}")
    assert got.status_code == 200
    assert got.json()["is_kit"] is True
    assert got.json()["carton_count"] == 1

    replace = await owner_client.put(
        f"/api/v1/skus/{parent['id']}/bom",
        json={"lines": [{"component_sku_id": frame["id"], "qty": 1}]},
    )
    assert replace.status_code == 200
    assert len(replace.json()) == 1
    assert replace.json()[0]["component_sku_id"] == frame["id"]


async def test_kit_till_consumes_components_one_parent_invoice_line(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    frame = await _sku(
        owner_client,
        "KIT-TILL-FRAME",
        opening_location_id=bedford_id,
        opening_qty=2,
        opening_cost="1000.00",
    )
    cushion = await _sku(
        owner_client,
        "KIT-TILL-CUSHION",
        opening_location_id=bedford_id,
        opening_qty=4,
        opening_cost="200.00",
    )
    parent = await _sku(owner_client, "KIT-TILL-PARENT", retail_ex_vat="4000.00")
    put = await owner_client.put(
        f"/api/v1/skus/{parent['id']}/bom",
        json={
            "lines": [
                {"component_sku_id": frame["id"], "qty": 1},
                {"component_sku_id": cushion["id"], "qty": 2},
            ]
        },
    )
    assert put.status_code == 200

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": parent["id"], "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201
    body = sale.json()
    assert body["subtotal_ex_vat"] == "4000.00"
    assert len(body["lines"]) == 1
    assert body["lines"][0]["sku_id"] == parent["id"]
    assert body["lines"][0]["description"] == parent["name"]
    assert body["lines"][0]["qty"] == 1

    invoice = await owner_client.get(f"/api/v1/invoices/{body['invoice_id']}")
    assert invoice.status_code == 200
    assert len(invoice.json()["lines"]) == 1
    assert invoice.json()["lines"][0]["sku_id"] == parent["id"]

    assert await _inventory_on_hand(owner_client, frame["id"], bedford_id) == 1
    assert await _inventory_on_hand(owner_client, cushion["id"], bedford_id) == 2
    parent_inv = await owner_client.get("/api/v1/inventory")
    assert parent_inv.status_code == 200
    parent_row = next(
        (row for row in parent_inv.json() if row["sku_id"] == parent["id"]),
        None,
    )
    if parent_row is not None:
        locs = [loc for loc in parent_row["locations"] if loc["location_id"] == bedford_id]
        if locs:
            assert locs[0]["on_hand"] == 0


async def test_kit_till_short_component_returns_409(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    frame = await _sku(
        owner_client,
        "KIT-SHORT-FRAME",
        opening_location_id=bedford_id,
        opening_qty=1,
        opening_cost="1000.00",
    )
    cushion = await _sku(owner_client, "KIT-SHORT-CUSHION")
    parent = await _sku(owner_client, "KIT-SHORT-PARENT", retail_ex_vat="4000.00")
    put = await owner_client.put(
        f"/api/v1/skus/{parent['id']}/bom",
        json={
            "lines": [
                {"component_sku_id": frame["id"], "qty": 1},
                {"component_sku_id": cushion["id"], "qty": 1},
            ]
        },
    )
    assert put.status_code == 200

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": parent["id"], "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 409
    assert "KIT-SHORT-CUSHION" in sale.json()["detail"]

    invoices = await owner_client.get("/api/v1/invoices")
    assert invoices.status_code == 200
    assert invoices.json() == []
    assert await _inventory_on_hand(owner_client, frame["id"], bedford_id) == 1
