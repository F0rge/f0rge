"""V2-S4 catalogue CSV import."""

from __future__ import annotations

from io import BytesIO
from typing import Optional

from httpx import AsyncClient


def _inventory_csv(
    our_ref: str,
    *,
    name: str = "Imported table",
    category: str = "Dining",
    retail: str = "115.00",
    extra_rows: str = "",
) -> bytes:
    body = f"SKU,Name,Category,Retail Price\n{our_ref},{name},{category},{retail}\n{extra_rows}"
    return body.encode("utf-8")


def _soh_csv(
    our_ref: str,
    *,
    location: str = "Kramerville",
    qty: str = "8",
    unit_cost: Optional[str] = "100.00",
) -> bytes:
    if unit_cost is None:
        body = f"SKU,Location,Qty\n{our_ref},{location},{qty}\n"
    else:
        body = f"SKU,Location,Qty,Unit Cost\n{our_ref},{location},{qty},{unit_cost}\n"
    return body.encode("utf-8")


def _inventory_file(content: bytes, filename: str = "inventory.csv") -> dict:
    return {"inventory": (filename, BytesIO(content), "text/csv")}


def _files(inventory: bytes, soh: Optional[bytes] = None) -> dict:
    files: dict = {"inventory": ("inventory.csv", BytesIO(inventory), "text/csv")}
    if soh is not None:
        files["soh"] = ("soh.csv", BytesIO(soh), "text/csv")
    return files


async def _kramerville_id(client: AsyncClient) -> str:
    resp = await client.get("/api/v1/locations")
    assert resp.status_code == 200
    for loc in resp.json():
        if loc["name"] == "Kramerville":
            return loc["id"]
    raise AssertionError("Kramerville not found")


async def _location_on_hand(client: AsyncClient, sku_id: str, location_id: str) -> int:
    inv = await client.get("/api/v1/inventory")
    assert inv.status_code == 200
    row = next(item for item in inv.json() if item["sku_id"] == sku_id)
    loc = next(item for item in row["locations"] if item["location_id"] == location_id)
    return loc["on_hand"]


async def test_commit_inventory_creates_sku(owner_client: AsyncClient) -> None:
    our_ref = "CSV-CREATE-REF"
    resp = await owner_client.post(
        "/api/v1/imports/commit",
        files=_inventory_file(_inventory_csv(our_ref)),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_skus"] == 1
    assert body["updated_skus"] == 0
    assert body["soh_rows"] == 0

    listed = await owner_client.get("/api/v1/skus")
    assert listed.status_code == 200
    sku = next(item for item in listed.json() if item["our_ref"] == our_ref)
    got = await owner_client.get(f"/api/v1/skus/{sku['id']}")
    assert got.status_code == 200
    payload = got.json()
    assert payload["retail_inc_vat"] == "115.00"
    assert payload["design"].startswith("csv:")
    assert payload["category"] == "Dining"
    assert payload["fabric"] == "-"


async def test_missing_category_preview_error_commit_400(owner_client: AsyncClient) -> None:
    csv_bytes = b"SKU,Name,Retail Price\nCSV-NOCAT-REF,Table,115.00\n"
    preview = await owner_client.post(
        "/api/v1/imports/preview",
        files=_inventory_file(csv_bytes),
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["ok"] is False
    assert any("category" in err["message"].lower() for err in body["errors"])

    commit = await owner_client.post(
        "/api/v1/imports/commit",
        files=_inventory_file(csv_bytes),
    )
    assert commit.status_code == 400


async def test_soh_sets_on_hand_not_add(owner_client: AsyncClient) -> None:
    location_id = await _kramerville_id(owner_client)
    our_ref = "CSV-SET-REF"
    created = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": our_ref,
            "our_barcode": "CSV-SET-BAR",
            "name": "Set sofa",
            "design": "Set design",
            "fabric": "Set fabric",
            "opening_location_id": location_id,
            "opening_qty": 5,
            "opening_unit_cost_zar": "100.00",
        },
    )
    assert created.status_code == 201
    sku_id = created.json()["id"]

    resp = await owner_client.post(
        "/api/v1/imports/commit",
        files=_files(
            _inventory_csv(our_ref, name="Set sofa"),
            _soh_csv(our_ref, qty="8", unit_cost="100.00"),
        ),
    )
    assert resp.status_code == 200
    assert resp.json()["soh_rows"] == 1
    assert await _location_on_hand(owner_client, sku_id, location_id) == 8


async def test_duplicate_sku_in_inventory_errors(owner_client: AsyncClient) -> None:
    csv_bytes = _inventory_csv(
        "CSV-DUP-REF",
        extra_rows="CSV-DUP-REF,Second,Dining,115.00\n",
    )
    preview = await owner_client.post(
        "/api/v1/imports/preview",
        files=_inventory_file(csv_bytes),
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["ok"] is False
    assert any("duplicate" in err["message"].lower() for err in body["errors"])

    commit = await owner_client.post(
        "/api/v1/imports/commit",
        files=_inventory_file(csv_bytes),
    )
    assert commit.status_code == 400


async def test_unknown_location_errors(owner_client: AsyncClient) -> None:
    our_ref = "CSV-LOC-REF"
    preview = await owner_client.post(
        "/api/v1/imports/preview",
        files=_files(
            _inventory_csv(our_ref, retail="115.00"),
            _soh_csv(our_ref, location="Narnia", qty="2", unit_cost="50.00"),
        ),
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["ok"] is False
    assert any("location" in err["message"].lower() for err in body["errors"])

    commit = await owner_client.post(
        "/api/v1/imports/commit",
        files=_files(
            _inventory_csv(our_ref, retail="115.00"),
            _soh_csv(our_ref, location="Narnia", qty="2", unit_cost="50.00"),
        ),
    )
    assert commit.status_code == 400


async def test_warehouse_cannot_preview_buyer_can(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    warehouse = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "csv-warehouse@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )
    assert warehouse.status_code == 201
    buyer = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "csv-buyer@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )
    assert buyer.status_code == 201

    csv_bytes = _inventory_csv("CSV-ROLE-REF")
    async_client.cookies.clear()
    login_wh = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "csv-warehouse@example.com", "password": "warehouse-password"},
    )
    assert login_wh.status_code == 200
    forbidden = await async_client.post(
        "/api/v1/imports/preview",
        files=_inventory_file(csv_bytes),
    )
    assert forbidden.status_code == 403

    async_client.cookies.clear()
    login_buyer = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "csv-buyer@example.com", "password": "buyer-password"},
    )
    assert login_buyer.status_code == 200
    allowed = await async_client.post(
        "/api/v1/imports/preview",
        files=_inventory_file(csv_bytes),
    )
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True


async def test_increase_from_zero_without_cost_errors(owner_client: AsyncClient) -> None:
    our_ref = "CSV-NOCOST-REF"
    preview = await owner_client.post(
        "/api/v1/imports/preview",
        files=_files(
            _inventory_csv(our_ref),
            _soh_csv(our_ref, qty="8", unit_cost=None),
        ),
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["ok"] is False
    assert any("unit cost" in err["message"].lower() for err in body["errors"])

    commit = await owner_client.post(
        "/api/v1/imports/commit",
        files=_files(
            _inventory_csv(our_ref),
            _soh_csv(our_ref, qty="8", unit_cost=None),
        ),
    )
    assert commit.status_code == 400
    assert "unit cost" in commit.json()["detail"].lower()
