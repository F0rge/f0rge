"""#581 F9 multi-location kit picks."""

from __future__ import annotations

import uuid
from io import BytesIO
from typing import Optional

from httpx import AsyncClient
from pypdf import PdfReader

from app.services.pick_allocator import (
    ComponentNeed,
    LocationStockRow,
    allocate,
)
from tests.test_purchase_orders import _create_till, _location_id_by_name
from tests.test_sku_bom import _sku
from tests.test_transfers import _receive_qty_at_location


async def _on_hand_or_zero(client: AsyncClient, sku_id: str, location_id: str) -> int:
    inv = await client.get("/api/v1/inventory")
    assert inv.status_code == 200
    row = next((item for item in inv.json() if item["sku_id"] == sku_id), None)
    if row is None:
        return 0
    loc = next((item for item in row["locations"] if item["location_id"] == location_id), None)
    return 0 if loc is None else loc["on_hand"]


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _stock(
    location_id: uuid.UUID,
    sku_id: uuid.UUID,
    on_hand: int,
    location_type: str,
    location_name: str,
    *,
    is_archived: bool = False,
) -> LocationStockRow:
    return LocationStockRow(
        location_id=location_id,
        sku_id=sku_id,
        on_hand=on_hand,
        location_type=location_type,
        location_name=location_name,
        is_archived=is_archived,
    )


def test_allocator_warehouse_first_and_flip_prefer() -> None:
    warehouse = uuid.uuid4()
    showroom = uuid.uuid4()
    chairs = uuid.uuid4()
    needs = [ComponentNeed(sku_id=chairs, qty_needed=4)]
    stocks = [
        _stock(warehouse, chairs, 6, "warehouse", "Kramerville"),
        _stock(showroom, chairs, 6, "showroom", "Bedfordview"),
    ]
    prefer = allocate(
        needs,
        stocks,
        True,
        [showroom, warehouse],
    )
    assert prefer.lines[0].allocations[0].location_id == warehouse
    assert prefer.needs_confirm is False

    skip_warehouse = allocate(
        needs,
        stocks,
        False,
        [showroom, warehouse],
    )
    assert skip_warehouse.lines[0].allocations[0].location_id == showroom
    assert skip_warehouse.needs_confirm is True


def test_allocator_leave_behind() -> None:
    warehouse = uuid.uuid4()
    chairs = uuid.uuid4()
    result = allocate(
        [ComponentNeed(sku_id=chairs, qty_needed=4)],
        [_stock(warehouse, chairs, 6, "warehouse", "Kramerville")],
        True,
        [],
    )
    assert result.lines[0].qty_allocated == 4
    assert result.lines[0].qty_short == 0
    assert result.lines[0].allocations[0].qty == 4
    assert result.needs_confirm is False


async def _put_bom(client: AsyncClient, parent_id: str, lines: list[tuple[str, int]]) -> None:
    resp = await client.put(
        f"/api/v1/skus/{parent_id}/bom",
        json={"lines": [{"component_sku_id": sku_id, "qty": qty} for sku_id, qty in lines]},
    )
    assert resp.status_code == 200, resp.text


async def _kit(
    owner_client: AsyncClient,
    prefix: str,
    *,
    table_location_id: Optional[str] = None,
    table_qty: int = 1,
    chair_location_id: Optional[str] = None,
    chair_qty: int = 4,
    chair_bom_qty: int = 4,
) -> dict:
    table_kwargs = {}
    if table_location_id is not None:
        table_kwargs = {
            "opening_location_id": table_location_id,
            "opening_qty": table_qty,
            "opening_cost": "800.00",
        }
    chair_kwargs = {}
    if chair_location_id is not None:
        chair_kwargs = {
            "opening_location_id": chair_location_id,
            "opening_qty": chair_qty,
            "opening_cost": "100.00",
        }
    table = await _sku(owner_client, f"{prefix}-TABLE", **table_kwargs)
    chairs = await _sku(owner_client, f"{prefix}-CHAIR", **chair_kwargs)
    parent = await _sku(owner_client, f"{prefix}-SET", retail_ex_vat="5000.00")
    await _put_bom(
        owner_client,
        parent["id"],
        [(table["id"], 1), (chairs["id"], chair_bom_qty)],
    )
    return {"parent": parent, "table": table, "chairs": chairs}


async def test_always_prefer_warehouse_flip_changes_preview(
    owner_client: AsyncClient,
) -> None:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    chairs = await _sku(
        owner_client,
        "PCK-PREF-CHAIR",
        opening_location_id=kramerville_id,
        opening_qty=4,
        opening_cost="100.00",
    )
    adj = await owner_client.post(
        "/api/v1/adjustments",
        json={"location_id": bedford_id, "reason": "opening"},
    )
    assert adj.status_code == 201
    line = await owner_client.post(
        f"/api/v1/adjustments/{adj.json()['id']}/lines",
        json={"sku_id": chairs["id"], "qty_delta": 4, "unit_cost_zar": "100.00"},
    )
    assert line.status_code == 201, line.text
    complete = await owner_client.post(f"/api/v1/adjustments/{adj.json()['id']}/complete")
    assert complete.status_code == 200, complete.text

    parent = await _sku(owner_client, "PCK-PREF-SET", retail_ex_vat="2000.00")
    await _put_bom(owner_client, parent["id"], [(chairs["id"], 4)])

    settings = await owner_client.get("/api/v1/settings")
    assert settings.status_code == 200
    assert settings.json()["always_prefer_warehouse"] is True
    assert settings.json()["pick_priority"] == []

    patched = await owner_client.patch(
        "/api/v1/settings",
        json={
            "always_prefer_warehouse": True,
            "pick_priority": [bedford_id, kramerville_id],
        },
    )
    assert patched.status_code == 200, patched.text

    prefer = await owner_client.post(
        "/api/v1/picks/preview",
        json={"sku_id": parent["id"], "qty": 1},
    )
    assert prefer.status_code == 200, prefer.text
    assert prefer.json()["lines"][0]["allocations"][0]["location_id"] == kramerville_id

    flipped = await owner_client.patch(
        "/api/v1/settings",
        json={"always_prefer_warehouse": False},
    )
    assert flipped.status_code == 200
    skipped = await owner_client.post(
        "/api/v1/picks/preview",
        json={"sku_id": parent["id"], "qty": 1},
    )
    assert skipped.status_code == 200
    assert skipped.json()["lines"][0]["allocations"][0]["location_id"] == bedford_id


async def test_leave_behind_and_confirm_split(
    owner_client: AsyncClient,
) -> None:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    kit = await _kit(
        owner_client,
        "PCK-LEAVE",
        table_location_id=kramerville_id,
        table_qty=1,
        chair_location_id=kramerville_id,
        chair_qty=6,
    )
    created = await owner_client.post(
        "/api/v1/picks",
        json={"sku_id": kit["parent"]["id"], "qty": 1},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["number"].startswith("PCK-")
    chair_line = next(line for line in body["lines"] if line["sku_id"] == kit["chairs"]["id"])
    assert chair_line["qty_needed"] == 4
    assert chair_line["allocations"][0]["qty"] == 4
    assert await _on_hand_or_zero(owner_client, kit["chairs"]["id"], kramerville_id) == 6

    split_kit = await _kit(
        owner_client,
        "PCK-SPLIT",
        table_location_id=kramerville_id,
        table_qty=1,
        chair_location_id=bedford_id,
        chair_qty=4,
    )
    split = await owner_client.post(
        "/api/v1/picks",
        json={"sku_id": split_kit["parent"]["id"], "qty": 1},
    )
    assert split.status_code == 201, split.text
    assert split.json()["needs_confirm"] is True
    denied = await owner_client.post(f"/api/v1/picks/{split.json()['id']}/confirm", json={})
    assert denied.status_code == 409
    assert denied.json()["detail"] == "confirm_split required"
    confirmed = await owner_client.post(
        f"/api/v1/picks/{split.json()['id']}/confirm",
        json={"confirm_split": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"


async def test_till_kit_requires_pick_does_not_drop_showroom_stock(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    kit = await _kit(
        owner_client,
        "PCK-TILL409",
        table_location_id=bedford_id,
        table_qty=1,
        chair_location_id=kramerville_id,
        chair_qty=4,
    )
    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": kit["parent"]["id"], "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 409
    assert sale.json()["detail"] == "Kit requires pick"
    assert await _on_hand_or_zero(owner_client, kit["table"]["id"], bedford_id) == 1


async def test_till_kit_100_percent_showroom_still_sells(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    kit = await _kit(
        owner_client,
        "PCK-TILL-OK",
        table_location_id=bedford_id,
        table_qty=1,
        chair_location_id=bedford_id,
        chair_qty=4,
    )
    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": kit["parent"]["id"], "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["lines"][0]["sku_id"] == kit["parent"]["id"]
    assert await _on_hand_or_zero(owner_client, kit["table"]["id"], bedford_id) == 0
    assert await _on_hand_or_zero(owner_client, kit["chairs"]["id"], bedford_id) == 0


async def test_complete_creates_f2_then_receive_stages(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    kit = await _kit(
        owner_client,
        "PCK-F2",
        table_location_id=kramerville_id,
        table_qty=1,
        chair_location_id=bedford_id,
        chair_qty=4,
    )
    created = await owner_client.post(
        "/api/v1/picks",
        json={"sku_id": kit["parent"]["id"], "qty": 1},
    )
    assert created.status_code == 201, created.text
    pick_id = created.json()["id"]
    confirmed = await owner_client.post(
        f"/api/v1/picks/{pick_id}/confirm",
        json={"confirm_split": True},
    )
    assert confirmed.status_code == 200
    before_dest = await _on_hand_or_zero(owner_client, kit["chairs"]["id"], kramerville_id)
    completed = await owner_client.post(f"/api/v1/picks/{pick_id}/complete", json={})
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "picking"
    transfers = await owner_client.get("/api/v1/transfers")
    assert transfers.status_code == 200
    pick_xfers = [row for row in transfers.json() if row.get("pick_id") == pick_id]
    assert len(pick_xfers) == 1
    assert pick_xfers[0]["status"] == "in_transit"
    assert pick_xfers[0]["to_location_id"] == kramerville_id
    assert await _on_hand_or_zero(owner_client, kit["chairs"]["id"], kramerville_id) == before_dest

    received = await owner_client.post(
        f"/api/v1/transfers/{pick_xfers[0]['id']}/receive",
        json={
            "lines": [
                {"line_id": line["id"], "qty_received": line["qty_dispatched"]}
                for line in pick_xfers[0]["lines"]
            ]
        },
    )
    assert received.status_code == 200, received.text
    staged = await owner_client.get(f"/api/v1/picks/{pick_id}")
    assert staged.status_code == 200
    assert staged.json()["status"] == "staged"


async def test_in_transit_qty_not_allocatable(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=8,
        location_name="Kramerville",
        our_ref="PCK-TRANSIT-CHAIR",
    )
    chairs_id = data["sku"]["id"]
    draft = await owner_client.post(
        "/api/v1/transfers",
        json={
            "from_location_id": kramerville_id,
            "to_location_id": bedford_id,
            "lines": [{"sku_id": chairs_id, "qty": 4}],
        },
    )
    assert draft.status_code == 201, draft.text
    dispatched = await owner_client.post(f"/api/v1/transfers/{draft.json()['id']}/dispatch")
    assert dispatched.status_code == 200
    parent = await _sku(owner_client, "PCK-TRANSIT-SET", retail_ex_vat="2000.00")
    await _put_bom(owner_client, parent["id"], [(chairs_id, 8)])
    preview = await owner_client.post(
        "/api/v1/picks/preview",
        json={"sku_id": parent["id"], "qty": 1},
    )
    assert preview.status_code == 200
    line = preview.json()["lines"][0]
    assert line["qty_allocated"] == 4
    assert line["qty_short"] == 4


async def test_third_location_is_just_another_row(owner_client: AsyncClient) -> None:
    sandton = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Sandton", "type": "warehouse"},
    )
    assert sandton.status_code == 201, sandton.text
    sandton_id = sandton.json()["id"]
    chairs = await _sku(
        owner_client,
        "PCK-THIRD-CHAIR",
        opening_location_id=sandton_id,
        opening_qty=4,
        opening_cost="100.00",
    )
    parent = await _sku(owner_client, "PCK-THIRD-SET", retail_ex_vat="2000.00")
    await _put_bom(owner_client, parent["id"], [(chairs["id"], 4)])
    preview = await owner_client.post(
        "/api/v1/picks/preview",
        json={"sku_id": parent["id"], "qty": 1},
    )
    assert preview.status_code == 200, preview.text
    allocs = preview.json()["lines"][0]["allocations"]
    assert len(allocs) == 1
    assert allocs[0]["location_id"] == sandton_id


async def test_does_not_patch_invoice_description(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    kit = await _kit(
        owner_client,
        "PCK-DESC",
        table_location_id=kramerville_id,
        table_qty=1,
        chair_location_id=kramerville_id,
        chair_qty=4,
    )
    created = await owner_client.post(
        "/api/v1/picks",
        json={"sku_id": kit["parent"]["id"], "qty": 1},
    )
    assert created.status_code == 201, created.text
    pick_id = created.json()["id"]
    confirmed = await owner_client.post(f"/api/v1/picks/{pick_id}/confirm", json={})
    assert confirmed.status_code == 200, confirmed.text
    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": kit["parent"]["id"], "qty": 1}],
            "tender": "cash",
            "pick_id": pick_id,
        },
    )
    assert sale.status_code == 201, sale.text
    invoice = await owner_client.get(f"/api/v1/invoices/{sale.json()['invoice_id']}")
    assert invoice.status_code == 200
    line = invoice.json()["lines"][0]
    assert line["sku_id"] == kit["parent"]["id"]
    assert line["description"] == kit["parent"]["name"]
    pdf = await owner_client.get(f"/api/v1/picks/{pick_id}/pdf")
    assert pdf.status_code == 200
    text = _pdf_text(pdf.content)
    assert created.json()["number"] in text
    assert "Set completeness" in text
