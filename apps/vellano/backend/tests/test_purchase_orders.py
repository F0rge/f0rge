"""S4 purchase orders, packing sheet, transit, land, receive, inventory tests."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from typing import Optional

from httpx import AsyncClient
from pypdf import PdfReader

from app.services.auth import JWT_COOKIE_NAME
from tests.conftest import assert_vellano_session_cookie

MINIMAL_PDF = b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


async def _create_supplier(client: AsyncClient, name: str = "PO Supplier") -> str:
    resp = await client.post("/api/v1/suppliers", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_sku(
    client: AsyncClient,
    our_ref: str,
    our_barcode: str,
    name: str,
    design: str,
    fabric: str,
    supplier_ref: Optional[str] = None,
) -> dict:
    payload = {
        "our_ref": our_ref,
        "our_barcode": our_barcode,
        "name": name,
        "design": design,
        "fabric": fabric,
    }
    if supplier_ref is not None:
        payload["supplier_ref"] = supplier_ref
    resp = await client.post("/api/v1/skus", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def _create_buyer(client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "buyer-po@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )
    assert create_user.status_code == 201

    client.cookies.clear()
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "buyer-po@example.com", "password": "buyer-password"},
    )
    assert login_resp.status_code == 200
    assert_vellano_session_cookie(login_resp)
    return client


async def _create_warehouse(client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "warehouse-po@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )
    assert create_user.status_code == 201

    client.cookies.clear()
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse-po@example.com", "password": "warehouse-password"},
    )
    assert login_resp.status_code == 200
    return client


async def _create_till(client: AsyncClient, owner_client: AsyncClient) -> AsyncClient:
    await _relogin_owner(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-po@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert create_user.status_code == 201

    client.cookies.clear()
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "till-po@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200
    return client


async def _location_id_by_name(client: AsyncClient, name: str) -> str:
    resp = await client.get("/api/v1/locations")
    assert resp.status_code == 200
    for loc in resp.json():
        if loc["name"] == name:
            return loc["id"]
    raise AssertionError(f"Location {name} not found")


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


async def test_buyer_creates_po_with_two_lines(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    buyer = await _create_buyer(async_client, owner_client)
    supplier_id = await _create_supplier(buyer)
    sku1 = await _create_sku(buyer, "PO-SKU-1", "BAR-PO-1", "Sofa A", "Design A", "Fabric A")
    sku2 = await _create_sku(buyer, "PO-SKU-2", "BAR-PO-2", "Sofa B", "Design B", "Fabric B")

    create_resp = await buyer.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [
                {"sku_id": sku1["id"], "qty": 2, "factory_unit_amount": "100.00"},
                {"sku_id": sku2["id"], "qty": 1, "factory_unit_amount": "50.00"},
            ],
        },
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["po_number"] == "PO-0001"
    assert body["status"] == "open"
    assert len(body["lines"]) == 2


async def test_packing_sheet_pdf_content(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Pack Supplier")
    sku = await _create_sku(
        owner_client,
        "PACK-REF",
        "PACK-BARCODE",
        "Pack Name",
        "Pack Design",
        "Pack Fabric",
        supplier_ref="SUPPLIER-REF-ONLY",
    )

    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [
                {"sku_id": sku["id"], "qty": 3, "factory_unit_amount": "80.00"},
            ],
        },
    )
    assert po_resp.status_code == 201
    po_id = po_resp.json()["id"]
    po_number = po_resp.json()["po_number"]

    sheet_resp = await owner_client.get(f"/api/v1/purchase-orders/{po_id}/packing-sheet")
    assert sheet_resp.status_code == 200
    assert sheet_resp.headers["content-type"].startswith("application/pdf")

    text = _pdf_text(sheet_resp.content)
    assert "PACK-REF" in text
    assert "PACK-BARCODE" in text
    assert "Pack Name" in text
    assert "Pack Fabric" in text
    assert "3" in text
    assert po_number in text
    assert "SUPPLIER-REF-ONLY" not in text


async def test_on_water_updates_inventory_not_on_hand(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Water Supplier")
    sku = await _create_sku(
        owner_client,
        "WATER-REF",
        "WATER-BAR",
        "Water Item",
        "Water Design",
        "Water Fabric",
    )

    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 4, "factory_unit_amount": "10.00"}],
        },
    )
    po_id = po_resp.json()["id"]

    on_water = await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    assert on_water.status_code == 200
    assert on_water.json()["status"] == "on_water"

    inv_resp = await owner_client.get("/api/v1/inventory")
    assert inv_resp.status_code == 200
    row = next(r for r in inv_resp.json() if r["sku_id"] == sku["id"])
    assert row["on_order"] == 4
    assert row["on_hand"] == 0
    assert row["sellable"] is False
    assert row["locations"] == [] or all(loc["on_hand"] == 0 for loc in row["locations"])


async def test_land_allocation_math(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Land Supplier")
    sku1 = await _create_sku(owner_client, "LAND-1", "LAND-B1", "L1", "D1", "F1")
    sku2 = await _create_sku(owner_client, "LAND-2", "LAND-B2", "L2", "D2", "F2")

    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [
                {"sku_id": sku1["id"], "qty": 2, "factory_unit_amount": "100.00"},
                {"sku_id": sku2["id"], "qty": 3, "factory_unit_amount": "50.00"},
            ],
        },
    )
    po_id = po_resp.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")

    land_resp = await owner_client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "20.00",
            "factory_invoice_number": "FAC-1",
            "factory_amount": "1000.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FRE-1",
            "freight_amount": "500.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CLR-1",
            "clearance_amount": "200.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert land_resp.status_code == 200
    body = land_resp.json()
    assert body["status"] == "landed"
    lines = {line["sku_id"]: line for line in body["lines"]}
    assert Decimal(lines[sku1["id"]]["unit_cost_zar"]) == Decimal("7000.0000")
    assert Decimal(lines[sku2["id"]]["unit_cost_zar"]) == Decimal("3500.0000")


async def test_receive_before_land_returns_409(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "Early Recv Supplier")
    sku = await _create_sku(owner_client, "EARLY-R", "EARLY-B", "Early", "ED", "EF")
    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 2, "factory_unit_amount": "10.00"}],
        },
    )
    po_id = po_resp.json()["id"]
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")

    recv = await owner_client.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_id, "location_id": bedford_id},
    )
    assert recv.status_code == 409

    inv = await owner_client.get("/api/v1/inventory")
    if any(r["sku_id"] == sku["id"] for r in inv.json()):
        row = next(r for r in inv.json() if r["sku_id"] == sku["id"])
        assert row["on_hand"] == 0


async def test_receive_after_land_bedfordview_and_third_location(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Recv Supplier")
    sku = await _create_sku(owner_client, "RECV-R", "RECV-B", "Recv Item", "RD", "RF")

    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 5, "factory_unit_amount": "100.00"}],
        },
    )
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

    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)
    await _relogin_owner(owner_client)

    recv1 = await warehouse.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_id, "location_id": bedford_id},
    )
    assert recv1.status_code == 200
    assert recv1.json()["status"] == "received"

    inv1 = await owner_client.get("/api/v1/inventory")
    row1 = next(r for r in inv1.json() if r["sku_id"] == sku["id"])
    assert row1["on_order"] == 0
    assert row1["on_hand"] == 5
    assert row1["sellable"] is True
    bedford_loc = next(loc for loc in row1["locations"] if loc["location_name"] == "Bedfordview")
    assert bedford_loc["on_hand"] == 5
    assert bedford_loc["unit_cost_zar"] is not None

    # Second PO into a third location
    sku2 = await _create_sku(owner_client, "RECV2-R", "RECV2-B", "Recv2", "R2D", "R2F")
    po2 = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku2["id"], "qty": 2, "factory_unit_amount": "40.00"}],
        },
    )
    po2_id = po2.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po2_id}/on-water")
    await owner_client.post(
        f"/api/v1/purchase-orders/{po2_id}/land",
        data={
            "fx_to_zar": "18.50",
            "factory_invoice_number": "F2",
            "factory_amount": "200.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FR2",
            "freight_amount": "50.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CL2",
            "clearance_amount": "20.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )

    third_loc = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Third PO location", "type": "warehouse"},
    )
    assert third_loc.status_code == 201
    third_id = third_loc.json()["id"]

    recv2 = await warehouse.post(
        "/api/v1/receive",
        json={"purchase_order_id": po2_id, "location_id": third_id},
    )
    assert recv2.status_code == 200

    inv2 = await owner_client.get("/api/v1/inventory")
    row2 = next(r for r in inv2.json() if r["sku_id"] == sku2["id"])
    assert row2["on_hand"] == 2
    assert row2["on_order"] == 0
    third = next(loc for loc in row2["locations"] if loc["location_id"] == third_id)
    assert third["on_hand"] == 2
    assert third["unit_cost_zar"] is not None


async def test_receive_into_archived_location_returns_409(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Arch Supplier")
    sku = await _create_sku(owner_client, "ARCH-R", "ARCH-B", "Arch", "AD", "AF")

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
            "fx_to_zar": "18.00",
            "factory_invoice_number": "F",
            "factory_amount": "100.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FR",
            "freight_amount": "10.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CL",
            "clearance_amount": "5.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )

    loc = await owner_client.post(
        "/api/v1/locations",
        json={"name": "Archive for PO", "type": "showroom"},
    )
    loc_id = loc.json()["id"]
    archive = await owner_client.patch(
        f"/api/v1/locations/{loc_id}",
        json={"is_archived": True},
    )
    assert archive.status_code == 200

    warehouse = await _create_warehouse(async_client, owner_client)
    recv = await warehouse.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_id, "location_id": loc_id},
    )
    assert recv.status_code == 409


async def test_unauthenticated_po_and_receive_return_401(async_client: AsyncClient) -> None:
    assert (await async_client.get("/api/v1/purchase-orders")).status_code == 401
    post_po = await async_client.post(
        "/api/v1/purchase-orders",
        json={"supplier_id": "00000000-0000-0000-0000-000000000001", "lines": []},
    )
    assert post_po.status_code == 401
    recv = await async_client.post(
        "/api/v1/receive",
        json={
            "purchase_order_id": "00000000-0000-0000-0000-000000000001",
            "location_id": "00000000-0000-0000-0000-000000000002",
        },
    )
    assert recv.status_code == 401


async def test_login_sets_vellano_session(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "change-me-owner"},
    )
    assert resp.status_code == 200
    assert_vellano_session_cookie(resp)
    assert JWT_COOKIE_NAME in async_client.cookies


async def _relogin_owner(client: AsyncClient) -> None:
    from app.config import settings

    client.cookies.clear()
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.seed_owner_email,
            "password": settings.seed_owner_password,
        },
    )
    assert resp.status_code == 200


async def _login_as(client: AsyncClient, email: str, password: str) -> AsyncClient:
    client.cookies.clear()
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    return client


async def test_role_permissions(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _relogin_owner(owner_client)
    await owner_client.post(
        "/api/v1/users",
        json={
            "email": "buyer-po@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )
    await _relogin_owner(owner_client)
    await owner_client.post(
        "/api/v1/users",
        json={
            "email": "warehouse-po@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )
    await _relogin_owner(owner_client)
    await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-po@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    await _relogin_owner(owner_client)

    supplier_id = await _create_supplier(owner_client, "Role Supplier")
    sku = await _create_sku(owner_client, "ROLE-R", "ROLE-B", "Role", "RD", "RF")
    po = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "10.00"}],
        },
    )
    po_id = po.json()["id"]
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")

    till = await _login_as(async_client, "till-po@example.com", "till-password")
    assert (
        await till.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_id": supplier_id,
                "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "10.00"}],
            },
        )
    ).status_code == 403

    warehouse = await _login_as(async_client, "warehouse-po@example.com", "warehouse-password")
    assert (
        await warehouse.post(
            "/api/v1/purchase-orders",
            json={
                "supplier_id": supplier_id,
                "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "10.00"}],
            },
        )
    ).status_code == 403

    buyer = await _login_as(async_client, "buyer-po@example.com", "buyer-password")
    assert (
        await buyer.post(
            "/api/v1/receive",
            json={"purchase_order_id": po_id, "location_id": bedford_id},
        )
    ).status_code == 403

    await _relogin_owner(owner_client)
    await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")

    till = await _login_as(async_client, "till-po@example.com", "till-password")
    land_resp = await till.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "18.00",
            "factory_invoice_number": "F",
            "factory_amount": "100.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FR",
            "freight_amount": "10.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CL",
            "clearance_amount": "5.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert land_resp.status_code == 403

    # Owner can land and receive
    await _relogin_owner(owner_client)
    land_owner = await owner_client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "18.00",
            "factory_invoice_number": "F",
            "factory_amount": "100.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FR",
            "freight_amount": "10.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CL",
            "clearance_amount": "5.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert land_owner.status_code == 200

    warehouse = await _login_as(async_client, "warehouse-po@example.com", "warehouse-password")
    recv_warehouse = await warehouse.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_id, "location_id": bedford_id},
    )
    assert recv_warehouse.status_code == 200


async def test_land_succeeds_despite_leftover_deterministic_bill_paths(
    owner_client: AsyncClient,
) -> None:
    from pathlib import Path

    from app.config import settings

    supplier_id = await _create_supplier(owner_client, "Retry Land Supplier")
    sku = await _create_sku(
        owner_client,
        "RETRY-R",
        "RETRY-B",
        "Retry Item",
        "RD",
        "RF",
    )

    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 2, "factory_unit_amount": "100.00"}],
        },
    )
    assert po_resp.status_code == 201
    po_id = po_resp.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")

    leftover_dir = Path(settings.storage_dir) / "landing-bills" / po_id
    leftover_dir.mkdir(parents=True, exist_ok=True)
    (leftover_dir / "factory.pdf").write_bytes(MINIMAL_PDF)
    (leftover_dir / "freight.pdf").write_bytes(MINIMAL_PDF)
    (leftover_dir / "clearance.pdf").write_bytes(MINIMAL_PDF)

    land_resp = await owner_client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "20.00",
            "factory_invoice_number": "FAC-RETRY",
            "factory_amount": "1000.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FRE-RETRY",
            "freight_amount": "500.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CLR-RETRY",
            "clearance_amount": "200.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert land_resp.status_code == 200
    body = land_resp.json()
    assert body["status"] == "landed"
    line = body["lines"][0]
    assert line["unit_cost_zar"] is not None
    assert Decimal(line["unit_cost_zar"]) > 0


async def test_receive_blends_unit_cost_at_location(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Blend Supplier")
    sku = await _create_sku(
        owner_client,
        "BLEND-R",
        "BLEND-B",
        "Blend Item",
        "BD",
        "BF",
    )
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    warehouse = await _create_warehouse(async_client, owner_client)
    await _relogin_owner(owner_client)

    po_a_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 2, "factory_unit_amount": "100.00"}],
        },
    )
    po_a_id = po_a_resp.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_a_id}/on-water")
    land_a = await owner_client.post(
        f"/api/v1/purchase-orders/{po_a_id}/land",
        data={
            "fx_to_zar": "20.00",
            "factory_invoice_number": "FA",
            "factory_amount": "1000.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FRA",
            "freight_amount": "0.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CLA",
            "clearance_amount": "0.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert land_a.status_code == 200
    c1 = Decimal(land_a.json()["lines"][0]["unit_cost_zar"])
    assert c1 == Decimal("10000.0000")

    recv_a = await warehouse.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_a_id, "location_id": kramerville_id},
    )
    assert recv_a.status_code == 200

    po_b_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 3, "factory_unit_amount": "100.00"}],
        },
    )
    po_b_id = po_b_resp.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_b_id}/on-water")
    land_b = await owner_client.post(
        f"/api/v1/purchase-orders/{po_b_id}/land",
        data={
            "fx_to_zar": "20.00",
            "factory_invoice_number": "FB",
            "factory_amount": "2250.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FRB",
            "freight_amount": "0.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CLB",
            "clearance_amount": "0.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert land_b.status_code == 200
    c2 = Decimal(land_b.json()["lines"][0]["unit_cost_zar"])
    assert c2 == Decimal("15000.0000")

    recv_b = await warehouse.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_b_id, "location_id": kramerville_id},
    )
    assert recv_b.status_code == 200

    expected_blend = (Decimal(2) * c1 + Decimal(3) * c2) / Decimal(5)
    inv = await owner_client.get("/api/v1/inventory")
    row = next(r for r in inv.json() if r["sku_id"] == sku["id"])
    assert row["on_hand"] == 5
    kram = next(loc for loc in row["locations"] if loc["location_name"] == "Kramerville")
    assert kram["on_hand"] == 5
    assert Decimal(kram["unit_cost_zar"]) == expected_blend
    assert Decimal(kram["unit_cost_zar"]) == Decimal("13000.0000")


async def test_backend_app_has_no_smtp_or_mailer() -> None:
    import pathlib

    app_root = pathlib.Path(__file__).resolve().parents[1] / "app"
    hits = []
    for path in app_root.rglob("*.py"):
        text = path.read_text().lower()
        if "smtp" in text or "mailer" in text:
            hits.append(str(path))
    assert hits == []
