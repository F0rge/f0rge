"""F2 two-step transfer document tests."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

from httpx import AsyncClient
from pypdf import PdfReader

from tests.test_purchase_orders import (
    MINIMAL_PDF,
    _create_buyer,
    _create_sku,
    _create_supplier,
    _create_till,
    _create_warehouse,
    _location_id_by_name,
    _relogin_owner,
)


async def _receive_qty_at_location(
    client: AsyncClient,
    owner_client: AsyncClient,
    qty: int,
    location_name: str,
    our_ref: str = "XFER-R",
) -> dict:
    supplier_id = await _create_supplier(owner_client, f"Xfer Supplier {our_ref}")
    sku = await _create_sku(
        owner_client,
        our_ref,
        f"{our_ref}-BAR",
        f"Xfer {our_ref}",
        "Xfer Design",
        "Xfer Fabric",
    )

    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": qty, "factory_unit_amount": "100.00"}],
        },
    )
    assert po_resp.status_code == 201
    po_id = po_resp.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    await owner_client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "18.50",
            "factory_invoice_number": "F",
            "factory_amount": "500.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FR",
            "freight_amount": "100.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CL",
            "clearance_amount": "50.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )

    location_id = await _location_id_by_name(owner_client, location_name)
    warehouse = await _create_warehouse(client, owner_client)
    await _relogin_owner(owner_client)

    recv = await warehouse.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_id, "location_id": location_id},
    )
    assert recv.status_code == 200

    return {
        "sku": sku,
        "location_id": location_id,
        "location_name": location_name,
    }


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _inventory_row(client_response, sku_id: str) -> dict:
    return next(row for row in client_response.json() if row["sku_id"] == sku_id)


def _location_on_hand(inv_row: dict, location_name: str) -> int:
    loc = next(
        (item for item in inv_row["locations"] if item["location_name"] == location_name),
        None,
    )
    return 0 if loc is None else loc["on_hand"]


async def _on_hand(client: AsyncClient, sku_id: str, location_name: str) -> int:
    inv = await client.get("/api/v1/inventory")
    assert inv.status_code == 200
    return _location_on_hand(_inventory_row(inv, sku_id), location_name)


def _draft_payload(
    from_location_id: str,
    to_location_id: str,
    sku_id: str,
    qty: int,
    from_bin_id: Optional[str] = None,
) -> dict:
    line: dict = {"sku_id": sku_id, "qty": qty}
    if from_bin_id is not None:
        line["from_bin_id"] = from_bin_id
    return {
        "from_location_id": from_location_id,
        "to_location_id": to_location_id,
        "lines": [line],
    }


async def complete_location_transfer(
    client: AsyncClient,
    from_location_id: str,
    to_location_id: str,
    sku_id: str,
    qty: int,
    from_bin_id: Optional[str] = None,
    to_bin_id: Optional[str] = None,
) -> dict:
    line: dict = {"sku_id": sku_id, "qty": qty}
    if from_bin_id is not None:
        line["from_bin_id"] = from_bin_id
    if to_bin_id is not None:
        line["to_bin_id"] = to_bin_id
    created = await client.post(
        "/api/v1/transfers",
        json={
            "from_location_id": from_location_id,
            "to_location_id": to_location_id,
            "lines": [line],
        },
    )
    assert created.status_code == 201, created.text
    transfer_id = created.json()["id"]
    dispatched = await client.post(f"/api/v1/transfers/{transfer_id}/dispatch")
    assert dispatched.status_code == 200, dispatched.text
    received = await client.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        json={
            "lines": [
                {"line_id": item["id"], "qty_received": item["qty_dispatched"]}
                for item in dispatched.json()["lines"]
            ]
        },
    )
    assert received.status_code == 200, received.text
    return received.json()


async def test_draft_does_not_move_stock(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="XFER-DRAFT",
    )
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)
    sku_id = data["sku"]["id"]

    draft = await warehouse.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], bedford_id, sku_id, 1),
    )
    assert draft.status_code == 201
    body = draft.json()
    assert body["status"] == "draft"
    assert body["transfer_number"].startswith("TRF-")
    assert await _on_hand(owner_client, sku_id, "Kramerville") == 2
    assert await _on_hand(owner_client, sku_id, "Bedfordview") == 0


async def test_dispatch_decrements_source_only_and_pdf_ok(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="XFER-DISP",
    )
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)
    sku_id = data["sku"]["id"]

    draft = await warehouse.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], bedford_id, sku_id, 1),
    )
    assert draft.status_code == 201
    transfer_id = draft.json()["id"]

    dispatched = await warehouse.post(f"/api/v1/transfers/{transfer_id}/dispatch")
    assert dispatched.status_code == 200
    assert dispatched.json()["status"] == "in_transit"
    assert await _on_hand(owner_client, sku_id, "Kramerville") == 1
    assert await _on_hand(owner_client, sku_id, "Bedfordview") == 0

    pdf = await warehouse.get(f"/api/v1/transfers/{transfer_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")
    text = _pdf_text(pdf.content)
    assert "TRF-" in text


async def test_till_cannot_dispatch_but_can_receive(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="XFER-TILL",
    )
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)
    sku_id = data["sku"]["id"]

    till = await _create_till(async_client, owner_client)
    forbidden_draft = await till.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], bedford_id, sku_id, 1),
    )
    assert forbidden_draft.status_code == 403

    warehouse = await _create_warehouse(async_client, owner_client)
    draft = await warehouse.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], bedford_id, sku_id, 1),
    )
    assert draft.status_code == 201
    transfer_id = draft.json()["id"]

    till = await _create_till(async_client, owner_client)
    till_dispatch = await till.post(f"/api/v1/transfers/{transfer_id}/dispatch")
    assert till_dispatch.status_code == 403

    warehouse = await _create_warehouse(async_client, owner_client)
    dispatched = await warehouse.post(f"/api/v1/transfers/{transfer_id}/dispatch")
    assert dispatched.status_code == 200
    line = dispatched.json()["lines"][0]

    till = await _create_till(async_client, owner_client)
    received = await till.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        json={"lines": [{"line_id": line["id"], "qty_received": line["qty_dispatched"]}]},
    )
    assert received.status_code == 200
    assert received.json()["status"] == "received"
    assert await _on_hand(owner_client, sku_id, "Bedfordview") == 1


async def test_buyer_cannot_receive(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="XFER-BUYER",
    )
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)
    sku_id = data["sku"]["id"]
    draft = await warehouse.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], bedford_id, sku_id, 1),
    )
    dispatched = await warehouse.post(f"/api/v1/transfers/{draft.json()['id']}/dispatch")
    assert dispatched.status_code == 200
    line = dispatched.json()["lines"][0]

    buyer = await _create_buyer(async_client, owner_client)
    received = await buyer.post(
        f"/api/v1/transfers/{dispatched.json()['id']}/receive",
        json={"lines": [{"line_id": line["id"], "qty_received": line["qty_dispatched"]}]},
    )
    assert received.status_code == 403


async def test_receive_increments_dest_and_pdf_shows_receiver(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="XFER-RECV",
    )
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)
    sku_id = data["sku"]["id"]
    draft = await warehouse.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], bedford_id, sku_id, 1),
    )
    transfer_id = draft.json()["id"]
    dispatched = await warehouse.post(f"/api/v1/transfers/{transfer_id}/dispatch")
    line = dispatched.json()["lines"][0]

    await _relogin_owner(owner_client)
    received = await owner_client.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        json={"lines": [{"line_id": line["id"], "qty_received": line["qty_dispatched"]}]},
    )
    assert received.status_code == 200
    body = received.json()
    assert body["status"] == "received"
    assert body["received_display_name"]
    assert await _on_hand(owner_client, sku_id, "Kramerville") == 1
    assert await _on_hand(owner_client, sku_id, "Bedfordview") == 1

    pdf = await owner_client.get(f"/api/v1/transfers/{transfer_id}/pdf")
    assert pdf.status_code == 200
    text = _pdf_text(pdf.content)
    assert body["received_display_name"] in text
    assert "Qty received:" in text


async def test_over_qty_dispatch_returns_409(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="XFER-OVER",
    )
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)
    sku_id = data["sku"]["id"]
    draft = await warehouse.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], bedford_id, sku_id, 5),
    )
    assert draft.status_code == 201
    dispatched = await warehouse.post(f"/api/v1/transfers/{draft.json()['id']}/dispatch")
    assert dispatched.status_code == 409
    assert await _on_hand(owner_client, sku_id, "Kramerville") == 1
    assert await _on_hand(owner_client, sku_id, "Bedfordview") == 0


async def test_same_from_to_returns_400(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="XFER-SAME",
    )
    warehouse = await _create_warehouse(async_client, owner_client)
    transfer = await warehouse.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], data["location_id"], data["sku"]["id"], 1),
    )
    assert transfer.status_code in (400, 422)


async def test_stocktake_lock_blocks_dispatch(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="XFER-LOCK",
    )
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)
    sku_id = data["sku"]["id"]
    draft = await warehouse.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], bedford_id, sku_id, 1),
    )
    assert draft.status_code == 201

    started = await owner_client.post(
        "/api/v1/stocktakes",
        json={"location_id": data["location_id"]},
    )
    assert started.status_code == 201

    dispatched = await warehouse.post(f"/api/v1/transfers/{draft.json()['id']}/dispatch")
    assert dispatched.status_code == 409
    assert dispatched.json()["detail"] == "Location is locked for stocktake"
    assert await _on_hand(owner_client, sku_id, "Kramerville") == 2
    assert await _on_hand(owner_client, sku_id, "Bedfordview") == 0


async def test_transfer_unauthenticated_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/transfers",
        json=_draft_payload(
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
            "00000000-0000-0000-0000-000000000003",
            1,
        ),
    )
    assert resp.status_code == 401


def test_transfer_modules_have_no_smtp() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    for rel in (
        "services/transfers.py",
        "services/transfer_note.py",
        "routers/transfers.py",
        "models/transfer.py",
        "schemas/transfer.py",
        "crud/transfer.py",
    ):
        text = (root / rel).read_text().lower()
        assert "smtp" not in text
        assert "sendmail" not in text
