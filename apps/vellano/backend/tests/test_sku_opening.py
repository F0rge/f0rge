"""S1 opening on-hand on SKU create."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient


def _sku_payload(**overrides: object) -> dict:
    body: dict = {
        "our_ref": "OPEN-REF",
        "our_barcode": "OPEN-BAR",
        "name": "Opening sofa",
        "design": "Opening design",
        "fabric": "Opening fabric",
    }
    body.update(overrides)
    return body


async def _kramerville_id(client: AsyncClient) -> str:
    resp = await client.get("/api/v1/locations")
    assert resp.status_code == 200
    for loc in resp.json():
        if loc["name"] == "Kramerville":
            return loc["id"]
    raise AssertionError("Kramerville not found")


async def test_create_sku_without_opening_is_absent_from_inventory(
    owner_client: AsyncClient,
) -> None:
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json=_sku_payload(our_ref="OPEN-NONE-REF", our_barcode="OPEN-NONE-BAR"),
    )
    assert create_resp.status_code == 201
    sku_id = create_resp.json()["id"]

    inv = await owner_client.get("/api/v1/inventory")
    assert inv.status_code == 200
    assert all(row["sku_id"] != sku_id for row in inv.json())


async def test_create_sku_with_opening_at_kramerville(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json=_sku_payload(
            our_ref="OPEN-KRAM-REF",
            our_barcode="OPEN-KRAM-BAR",
            design="Opening kram design",
            fabric="Opening kram fabric",
            opening_location_id=location_id,
            opening_qty=5,
            opening_unit_cost_zar="100.00",
        ),
    )
    assert create_resp.status_code == 201
    sku_id = create_resp.json()["id"]

    inv = await owner_client.get("/api/v1/inventory")
    assert inv.status_code == 200
    row = next(r for r in inv.json() if r["sku_id"] == sku_id)
    assert row["on_hand"] == 5
    loc = next(item for item in row["locations"] if item["location_id"] == location_id)
    assert loc["on_hand"] == 5
    assert Decimal(str(loc["unit_cost_zar"])) == Decimal("100.0000")

    audit = await owner_client.get(f"/api/v1/skus/{sku_id}/cost-audit")
    assert audit.status_code == 200
    sources = [entry["source"] for entry in audit.json()]
    assert "opening" in sources


async def test_partial_opening_fields_return_422(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    resp = await owner_client.post(
        "/api/v1/skus",
        json=_sku_payload(
            our_ref="OPEN-PART-REF",
            our_barcode="OPEN-PART-BAR",
            design="Opening partial design",
            fabric="Opening partial fabric",
            opening_location_id=location_id,
        ),
    )
    assert resp.status_code == 422


async def test_opening_qty_zero_or_negative_returns_422(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    zero = await owner_client.post(
        "/api/v1/skus",
        json=_sku_payload(
            our_ref="OPEN-QTY0-REF",
            our_barcode="OPEN-QTY0-BAR",
            design="Opening qty0 design",
            fabric="Opening qty0 fabric",
            opening_location_id=location_id,
            opening_qty=0,
            opening_unit_cost_zar="100.00",
        ),
    )
    assert zero.status_code == 422

    negative = await owner_client.post(
        "/api/v1/skus",
        json=_sku_payload(
            our_ref="OPEN-QTYNEG-REF",
            our_barcode="OPEN-QTYNEG-BAR",
            design="Opening qtyneg design",
            fabric="Opening qtyneg fabric",
            opening_location_id=location_id,
            opening_qty=-1,
            opening_unit_cost_zar="100.00",
        ),
    )
    assert negative.status_code == 422
