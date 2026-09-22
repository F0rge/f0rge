"""F0 warehouse bins (#572)."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from httpx import AsyncClient

from app.config import settings
from tests.test_purchase_orders import (
    MINIMAL_PDF,
    _create_sku,
    _create_supplier,
    _location_id_by_name,
)
from tests.test_transfers import complete_location_transfer


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


async def _bins(client: AsyncClient, location_id: str) -> list[dict]:
    resp = await client.get(f"/api/v1/locations/{location_id}/bins")
    assert resp.status_code == 200
    return resp.json()


def _floor(bins: list[dict]) -> dict:
    return next(row for row in bins if row["code"] == "FLOOR")


async def _land_and_receive(
    owner_client: AsyncClient,
    our_ref: str,
    qty: int,
    location_id: str,
    bin_id: Optional[str] = None,
) -> dict:
    supplier_id = await _create_supplier(owner_client, f"Bin Supplier {our_ref}")
    sku = await _create_sku(
        owner_client,
        our_ref,
        f"{our_ref}-BAR",
        f"Bin {our_ref}",
        "Bin Design",
        "Bin Fabric",
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
    land = await owner_client.post(
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
    assert land.status_code == 200
    payload: dict = {"purchase_order_id": po_id, "location_id": location_id}
    if bin_id is not None:
        payload["bin_id"] = bin_id
    recv = await owner_client.post("/api/v1/receive", json=payload)
    assert recv.status_code == 200
    return sku


def _inventory_location(inv: dict, sku_id: str, location_id: str) -> dict:
    row = next(item for item in inv if item["sku_id"] == sku_id)
    return next(loc for loc in row["locations"] if loc["location_id"] == location_id)


async def test_seed_locations_have_floor_default(owner_client: AsyncClient) -> None:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    for location_id in (kramerville_id, bedford_id):
        bins = await _bins(owner_client, location_id)
        floor = _floor(bins)
        assert floor["row_code"] == "F"
        assert floor["bay"] == 1
        assert floor["level"] == 1
        assert floor["is_default"] is True
        assert floor["is_archived"] is False
        assert sum(1 for row in bins if row["is_default"] and not row["is_archived"]) == 1


async def test_create_location_adds_floor_bin(owner_client: AsyncClient) -> None:
    created = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Bin new warehouse", "type": "warehouse"},
    )
    assert created.status_code == 201
    bins = await _bins(owner_client, created.json()["id"])
    assert len(bins) == 1
    assert bins[0]["code"] == "FLOOR"
    assert bins[0]["is_default"] is True


async def test_grid_generate_unique_codes_and_idempotent(owner_client: AsyncClient) -> None:
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    first = await owner_client.post(
        f"/api/v1/locations/{location_id}/bins/grid",
        json={"rows": ["A", "B"], "bays": 2, "levels": 2},
    )
    assert first.status_code == 200
    codes = {row["code"] for row in first.json()}
    assert "FLOOR" in codes
    assert codes.issuperset(
        {"A-01-1", "A-01-2", "A-02-1", "A-02-2", "B-01-1", "B-01-2", "B-02-1", "B-02-2"}
    )
    first_count = len(first.json())

    second = await owner_client.post(
        f"/api/v1/locations/{location_id}/bins/grid",
        json={"rows": ["A", "B"], "bays": 2, "levels": 2},
    )
    assert second.status_code == 200
    assert len(second.json()) == first_count


async def test_unique_code_and_slot_conflict(owner_client: AsyncClient) -> None:
    created = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Bin unique loc", "type": "warehouse"},
    )
    location_id = created.json()["id"]
    first = await owner_client.post(
        f"/api/v1/locations/{location_id}/bins",
        json={"row_code": "A", "bay": 1, "level": 1},
    )
    assert first.status_code == 201
    assert first.json()["code"] == "A-01-1"

    dup = await owner_client.post(
        f"/api/v1/locations/{location_id}/bins",
        json={"row_code": "a", "bay": 1, "level": 1},
    )
    assert dup.status_code == 409

    floor_slot = await owner_client.post(
        f"/api/v1/locations/{location_id}/bins",
        json={"row_code": "F", "bay": 1, "level": 1},
    )
    assert floor_slot.status_code == 409


async def test_receive_default_bin_rollup_and_location_cost(owner_client: AsyncClient) -> None:
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    sku = await _land_and_receive(owner_client, "BIN-ROLL", qty=2, location_id=location_id)
    inv = await owner_client.get("/api/v1/inventory")
    loc = _inventory_location(inv.json(), sku["id"], location_id)
    assert loc["on_hand"] == 2
    assert loc["unit_cost_zar"] is not None
    assert loc["on_hand"] == sum(row["on_hand"] for row in loc["bins"])
    floor = next(row for row in loc["bins"] if row["code"] == "FLOOR")
    assert floor["on_hand"] == 2


async def test_receive_into_non_default_bin(owner_client: AsyncClient) -> None:
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    created = await owner_client.post(
        f"/api/v1/locations/{location_id}/bins",
        json={"row_code": "C", "bay": 3, "level": 2},
    )
    assert created.status_code == 201
    bin_id = created.json()["id"]
    assert created.json()["code"] == "C-03-2"

    sku = await _land_and_receive(
        owner_client,
        "BIN-NDEF",
        qty=1,
        location_id=location_id,
        bin_id=bin_id,
    )
    inv = await owner_client.get("/api/v1/inventory")
    loc = _inventory_location(inv.json(), sku["id"], location_id)
    assert loc["on_hand"] == 1
    assert loc["unit_cost_zar"] is not None
    by_code = {row["code"]: row["on_hand"] for row in loc["bins"]}
    assert by_code["C-03-2"] == 1
    assert "FLOOR" not in by_code
    assert Decimal(str(loc["unit_cost_zar"])) > 0


async def test_transfer_without_bin_fields_uses_defaults(owner_client: AsyncClient) -> None:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    sku = await _land_and_receive(owner_client, "BIN-XDEF", qty=2, location_id=kramerville_id)
    transfer = await complete_location_transfer(
        owner_client,
        kramerville_id,
        bedford_id,
        sku["id"],
        1,
    )
    assert transfer["status"] == "received"

    inv = await owner_client.get("/api/v1/inventory")
    kram = _inventory_location(inv.json(), sku["id"], kramerville_id)
    bed = _inventory_location(inv.json(), sku["id"], bedford_id)
    assert kram["on_hand"] == 1
    assert bed["on_hand"] == 1
    assert next(row for row in kram["bins"] if row["code"] == "FLOOR")["on_hand"] == 1
    assert next(row for row in bed["bins"] if row["code"] == "FLOOR")["on_hand"] == 1


async def test_transfer_from_bin_insufficient_returns_409(owner_client: AsyncClient) -> None:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    empty = await owner_client.post(
        f"/api/v1/locations/{kramerville_id}/bins",
        json={"row_code": "D", "bay": 1, "level": 1},
    )
    assert empty.status_code == 201
    sku = await _land_and_receive(owner_client, "BIN-XINS", qty=2, location_id=kramerville_id)
    draft = await owner_client.post(
        "/api/v1/transfers",
        json={
            "from_location_id": kramerville_id,
            "to_location_id": bedford_id,
            "lines": [
                {
                    "sku_id": sku["id"],
                    "qty": 1,
                    "from_bin_id": empty.json()["id"],
                }
            ],
        },
    )
    assert draft.status_code == 201
    transfer = await owner_client.post(f"/api/v1/transfers/{draft.json()['id']}/dispatch")
    assert transfer.status_code == 409
    inv = await owner_client.get("/api/v1/inventory")
    kram = _inventory_location(inv.json(), sku["id"], kramerville_id)
    assert kram["on_hand"] == 2


async def test_cannot_archive_last_default_without_assigning_another(
    owner_client: AsyncClient,
) -> None:
    created = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Bin archive default", "type": "warehouse"},
    )
    location_id = created.json()["id"]
    floor = _floor(await _bins(owner_client, location_id))
    blocked = await owner_client.patch(
        f"/api/v1/locations/{location_id}/bins/{floor['id']}",
        json={"is_archived": True},
    )
    assert blocked.status_code == 409

    other = await owner_client.post(
        f"/api/v1/locations/{location_id}/bins",
        json={"row_code": "A", "bay": 1, "level": 1},
    )
    assert other.status_code == 201
    promoted = await owner_client.patch(
        f"/api/v1/locations/{location_id}/bins/{other.json()['id']}",
        json={"is_default": True},
    )
    assert promoted.status_code == 200
    assert promoted.json()["is_default"] is True

    archived = await owner_client.patch(
        f"/api/v1/locations/{location_id}/bins/{floor['id']}",
        json={"is_archived": True},
    )
    assert archived.status_code == 200
    assert archived.json()["is_archived"] is True
    assert archived.json()["is_default"] is False


async def test_archived_bin_cannot_receive(owner_client: AsyncClient) -> None:
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    created = await owner_client.post(
        f"/api/v1/locations/{location_id}/bins",
        json={"row_code": "E", "bay": 1, "level": 1},
    )
    assert created.status_code == 201
    bin_id = created.json()["id"]
    archived = await owner_client.patch(
        f"/api/v1/locations/{location_id}/bins/{bin_id}",
        json={"is_archived": True},
    )
    assert archived.status_code == 200

    supplier_id = await _create_supplier(owner_client, "Bin archived recv")
    sku = await _create_sku(
        owner_client,
        "BIN-ARCH",
        "BIN-ARCH-BAR",
        "Archived recv",
        "AD",
        "AF",
    )
    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "10.00"}],
        },
    )
    po_id = po_resp.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    await owner_client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "18.50",
            "factory_invoice_number": "F",
            "factory_amount": "10.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FR",
            "freight_amount": "1.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CL",
            "clearance_amount": "1.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    recv = await owner_client.post(
        "/api/v1/receive",
        json={
            "purchase_order_id": po_id,
            "location_id": location_id,
            "bin_id": bin_id,
        },
    )
    assert recv.status_code == 409


async def test_buyer_till_books_can_list_bins_not_mutate(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    roles = (
        ("buyer@example.com", settings.seed_buyer_password),
        ("till@example.com", settings.seed_till_password),
        ("books@example.com", settings.seed_books_password),
    )
    for email, password in roles:
        client = await _login(async_client, email, password)
        listed = await client.get(f"/api/v1/locations/{location_id}/bins")
        assert listed.status_code == 200
        grid = await client.post(
            f"/api/v1/locations/{location_id}/bins/grid",
            json={"rows": ["Z"], "bays": 1, "levels": 1},
        )
        assert grid.status_code == 403
