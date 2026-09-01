"""S8 stock transfer tests."""

from __future__ import annotations

from httpx import AsyncClient

from tests.test_purchase_orders import (
    MINIMAL_PDF,
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


def _inventory_row(client_response, sku_id: str) -> dict:
    return next(row for row in client_response.json() if row["sku_id"] == sku_id)


async def test_transfer_happy_path_kramerville_to_bedfordview(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="XFER-HAPPY",
    )
    kramerville_id = data["location_id"]
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    sku_id = data["sku"]["id"]

    warehouse = await _create_warehouse(async_client, owner_client)

    transfer = await warehouse.post(
        "/api/v1/transfers",
        json={
            "from_location_id": kramerville_id,
            "to_location_id": bedford_id,
            "sku_id": sku_id,
            "qty": 1,
        },
    )
    assert transfer.status_code == 200
    body = transfer.json()
    assert body["qty"] == 1
    assert body["from_location"]["on_hand"] == 1
    assert body["to_location"]["on_hand"] == 1
    assert body["from_location"]["unit_cost_zar"] == body["to_location"]["unit_cost_zar"]

    inv = await owner_client.get("/api/v1/inventory")
    row = _inventory_row(inv, sku_id)
    assert row["on_hand"] == 2
    kram = next(loc for loc in row["locations"] if loc["location_name"] == "Kramerville")
    bed = next(loc for loc in row["locations"] if loc["location_name"] == "Bedfordview")
    assert kram["on_hand"] == 1
    assert bed["on_hand"] == 1


async def test_transfer_over_qty_unchanged_balances(
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

    transfer = await warehouse.post(
        "/api/v1/transfers",
        json={
            "from_location_id": data["location_id"],
            "to_location_id": bedford_id,
            "sku_id": data["sku"]["id"],
            "qty": 5,
        },
    )
    assert transfer.status_code == 409

    inv = await owner_client.get("/api/v1/inventory")
    row = _inventory_row(inv, data["sku"]["id"])
    assert row["on_hand"] == 1
    assert len(row["locations"]) == 1
    assert row["locations"][0]["on_hand"] == 1


async def test_transfer_archived_location_returns_409(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="XFER-ARCH",
    )
    archived = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Archive xfer", "type": "showroom"},
    )
    assert archived.status_code == 201
    archived_id = archived.json()["id"]
    patch = await owner_client.patch(
        f"/api/v1/locations/{archived_id}",
        json={"is_archived": True},
    )
    assert patch.status_code == 200

    warehouse = await _create_warehouse(async_client, owner_client)

    into_archived = await warehouse.post(
        "/api/v1/transfers",
        json={
            "from_location_id": data["location_id"],
            "to_location_id": archived_id,
            "sku_id": data["sku"]["id"],
            "qty": 1,
        },
    )
    assert into_archived.status_code == 409

    from_archived = await warehouse.post(
        "/api/v1/transfers",
        json={
            "from_location_id": archived_id,
            "to_location_id": data["location_id"],
            "sku_id": data["sku"]["id"],
            "qty": 1,
        },
    )
    assert from_archived.status_code == 409


async def test_transfer_third_location(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=3,
        location_name="Kramerville",
        our_ref="XFER-THIRD",
    )

    third = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Third xfer location", "type": "warehouse"},
    )
    assert third.status_code == 201
    third_id = third.json()["id"]

    warehouse = await _create_warehouse(async_client, owner_client)

    to_third = await warehouse.post(
        "/api/v1/transfers",
        json={
            "from_location_id": data["location_id"],
            "to_location_id": third_id,
            "sku_id": data["sku"]["id"],
            "qty": 2,
        },
    )
    assert to_third.status_code == 200
    assert to_third.json()["to_location"]["on_hand"] == 2

    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    from_third = await warehouse.post(
        "/api/v1/transfers",
        json={
            "from_location_id": third_id,
            "to_location_id": bedford_id,
            "sku_id": data["sku"]["id"],
            "qty": 1,
        },
    )
    assert from_third.status_code == 200

    inv = await owner_client.get("/api/v1/inventory")
    row = _inventory_row(inv, data["sku"]["id"])
    assert row["on_hand"] == 3
    by_name = {loc["location_name"]: loc["on_hand"] for loc in row["locations"]}
    assert by_name["Kramerville"] == 1
    assert by_name["Third xfer location"] == 1
    assert by_name["Bedfordview"] == 1


async def test_transfer_same_location_returns_400(
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
        json={
            "from_location_id": data["location_id"],
            "to_location_id": data["location_id"],
            "sku_id": data["sku"]["id"],
            "qty": 1,
        },
    )
    assert transfer.status_code == 400


async def test_transfer_on_water_only_returns_409(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "On water xfer")
    sku = await _create_sku(
        owner_client,
        "XFER-WATER",
        "XFER-WATER-B",
        "Water only",
        "WD",
        "WF",
    )
    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 2, "factory_unit_amount": "10.00"}],
        },
    )
    po_id = po_resp.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")

    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)

    transfer = await warehouse.post(
        "/api/v1/transfers",
        json={
            "from_location_id": kramerville_id,
            "to_location_id": bedford_id,
            "sku_id": sku["id"],
            "qty": 1,
        },
    )
    assert transfer.status_code == 409


async def test_transfer_unauthenticated_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/transfers",
        json={
            "from_location_id": "00000000-0000-0000-0000-000000000001",
            "to_location_id": "00000000-0000-0000-0000-000000000002",
            "sku_id": "00000000-0000-0000-0000-000000000003",
            "qty": 1,
        },
    )
    assert resp.status_code == 401


async def test_transfer_till_role_forbidden(
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
    till = await _create_till(async_client, owner_client)

    transfer = await till.post(
        "/api/v1/transfers",
        json={
            "from_location_id": data["location_id"],
            "to_location_id": bedford_id,
            "sku_id": data["sku"]["id"],
            "qty": 1,
        },
    )
    assert transfer.status_code == 403
