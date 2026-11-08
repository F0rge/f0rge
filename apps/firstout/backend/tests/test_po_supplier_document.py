"""Supplier code prefill and the supplier-facing purchase order PDF."""

from __future__ import annotations

import uuid
from decimal import Decimal
from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from typing import Optional

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sku_supplier_price import SkuSupplierPrice
from tests.pdf_fixture import MINIMAL_PDF
from tests.test_tenant_database import rls_database_url, tenant_database  # noqa: F401
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
    async_db: AsyncSession,
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

    from app.models.purchase_order import PoLine

    cost_line = await async_db.get(PoLine, uuid.UUID(created.json()["lines"][0]["id"]))
    cost_line.unit_cost_zar = Decimal("543210.99")
    await async_db.flush()

    warehouse = await _create_warehouse(async_client, owner_client)
    allowed = await warehouse.get(f"/api/v1/purchase-orders/{po_id}/pdf")
    assert allowed.status_code == 200
    allowed_text = _pdf_text(allowed.content)
    assert "VIEW-CODE" in allowed_text
    assert "543210.99" not in allowed_text
    assert "stock.cost.view" not in (await warehouse.get("/api/v1/auth/me")).json()["permissions"]

    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    anonymous = await async_client.get(f"/api/v1/purchase-orders/{po_id}/pdf")
    assert anonymous.status_code == 401


def _pdf_text_outside_page(data: bytes) -> list[tuple[int, str, float, float]]:
    outside = []
    for number, page in enumerate(PdfReader(BytesIO(data)).pages, start=1):
        width, height = float(page.mediabox.width), float(page.mediabox.height)

        def inspect(text, cm, tm, font, size):
            if not text.strip():
                return
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            font_name = str((font or {}).get("/BaseFont", "/Helvetica")).removeprefix("/")
            for line in text.splitlines():
                if not line.strip():
                    continue
                extent = stringWidth(line, font_name, size)
                if (
                    x < 10 * mm
                    or y < 10 * mm
                    or y > height - 10 * mm
                    or x + extent > width - 10 * mm
                ):
                    outside.append((number, line[:35], round(x, 2), round(y, 2)))

        page.extract_text(visitor_text=inspect)
    return outside


@pytest.mark.no_db
def test_supplier_pdf_paginates_long_notes_and_unbreakable_fields():
    from app.services.invoice_pdf import SellerDetails
    from app.services.purchase_order_pdf import PurchaseOrderPdfLine, build_purchase_order_pdf

    data = build_purchase_order_pdf(
        po_number="PO-PAGINATION",
        po_date="2026-11-08",
        status_label="Pending approval",
        draft=True,
        supplier_name="Supplier " + "W" * 400,
        supplier_ref="R" * 128,
        currency="USD",
        notes=" ".join(f"footer_note_{i:03d}" for i in range(700)),
        seller=SellerDetails(
            name="Seller " + "S" * 180,
            address="Address " + "A" * 300,
            vat_number="V" * 64,
            vat_percent_label="15%",
        ),
        lines=[
            PurchaseOrderPdfLine(
                supplier_code="C" * 128,
                description="D" * 512,
                our_ref="F" * 64,
                fabric="Fabric " + "B" * 512,
                notes=" ".join(f"line_note_{i:03d}" for i in range(700)),
                qty=2,
                unit_price=Decimal("19.95"),
            )
        ],
    )
    reader = PdfReader(BytesIO(data))
    assert len(reader.pages) > 1
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "line_note_699" in text and "footer_note_699" in text
    assert "USD 39.90" in text and "Grand total" in text
    assert not _pdf_text_outside_page(data), _pdf_text_outside_page(data)[:8]


@pytest.mark.no_db
def test_supplier_pdf_treats_dynamic_markup_as_literal_text():
    from app.services.invoice_pdf import SellerDetails
    from app.services.purchase_order_pdf import PurchaseOrderPdfLine, build_purchase_order_pdf

    literal = '<b>literal instructions</b> & <img src="file:///never-open-me">'
    data = build_purchase_order_pdf(
        po_number="PO-LITERAL",
        po_date="2026-11-08",
        status_label="Pending approval",
        draft=True,
        supplier_name="Factory <b>literal supplier</b> & Co",
        supplier_ref="<ref>ABC</ref>",
        currency="USD",
        notes=literal,
        seller=SellerDetails(
            name="Seller <b>literal seller</b>",
            address="Address & <suite>",
            vat_number="VAT<123>",
            vat_percent_label="15%",
        ),
        lines=[
            PurchaseOrderPdfLine(
                supplier_code="<code>ABC</code>",
                description="A <b>literal description</b>",
                our_ref="<our-ref>",
                fabric="<fabric> & finish",
                notes=literal,
                qty=1,
                unit_price=Decimal("10.00"),
            )
        ],
    )
    reader = PdfReader(BytesIO(data))
    text = " ".join(" ".join((page.extract_text() or "").split()) for page in reader.pages)
    for expected in (
        "<b>literal supplier</b>",
        "<ref>ABC</ref>",
        "<b>literal seller</b>",
        "Address & <suite>",
        "VAT<123>",
        "<code>ABC</code>",
        "<b>literal description</b>",
        "<our-ref>",
        "<fabric> & finish",
        "<b>literal instructions</b>",
        "file:///never-open-me",
    ):
        assert expected in text
    assert all(not page.get("/Annots") for page in reader.pages)
    assert not _pdf_text_outside_page(data)


async def test_historical_blank_supplier_code_is_resolved_without_rewriting_line(
    owner_client, async_db
):
    from app.models.purchase_order import PoLine

    supplier_id = await _create_supplier(owner_client, "Historical Factory")
    sku = await _create_sku(
        owner_client,
        "HIST-REF",
        "HIST-BAR",
        "Historical chair",
        "Historical design",
        "Cotton",
        supplier_ref="GENERIC-HIST",
    )
    await _price(async_db, sku_id=sku["id"], supplier_id=supplier_id, supplier_sku="FACTORY-HIST")
    created = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "12.00"}],
        },
    )
    assert created.status_code == 201
    line = await async_db.get(PoLine, uuid.UUID(created.json()["lines"][0]["id"]))
    line.supplier_code = None
    await async_db.flush()
    before = (line.supplier_code, line.updated_at, line.factory_unit_amount, line.qty)
    response = await owner_client.get(f"/api/v1/purchase-orders/{created.json()['id']}/pdf")
    assert response.status_code == 200 and "FACTORY-HIST" in _pdf_text(response.content)
    await async_db.refresh(line)
    assert (line.supplier_code, line.updated_at, line.factory_unit_amount, line.qty) == before


@pytest.mark.no_db
@pytest.mark.usefixtures("tenant_database")
async def test_supplier_pdf_and_lookup_respect_migrated_tenant_isolation(request):
    from httpx import ASGITransport
    from sqlalchemy import text, select
    from app.database import get_db
    from app.main import app
    from app.crud.supplier import SupplierCRUD
    from app.models.membership import Membership
    from app.models.purchase_order import PurchaseOrder, PoLine, PurchaseOrderStatus
    from app.models.sku import Sku
    from app.models.supplier import Supplier
    from app.models.user import User
    from f0rge_db.organisation import organisation_session
    from tests.conftest import signed_clerk_token

    admin, _runtime, maker, own, foreign = request.getfixturevalue("tenant_database")
    orders, suppliers, skus, lines = {}, {}, {}, {}
    previous = app.dependency_overrides.get(get_db)
    try:
        for team, code in ((own, "OWN-FACTORY-CODE"), (foreign, "FOREIGN-FACTORY-CODE")):
            async with organisation_session(maker, team) as db:
                user = User(
                    team_id=team,
                    clerk_user_id=f"po900-{team.hex}",
                    email=f"po900-{team.hex}@example.com",
                    password_hash="fixture-not-authentication",
                    role="warehouse",
                    is_disabled=False,
                )
                supplier = Supplier(team_id=team, name="Same factory", default_currency="USD")
                sku = Sku(
                    team_id=team,
                    our_ref="SAME-PO900",
                    our_barcode="SAME-PO900",
                    name="Supplier chair",
                    design="Same design",
                    fabric="Same fabric",
                    supplier_ref="GENERIC-CODE",
                )
                db.add_all([user, supplier, sku])
                await db.flush()
                db.add(
                    Membership(
                        user_id=user.id,
                        team_id=team,
                        role="warehouse",
                        is_legacy_home=True,
                        is_disabled=False,
                    )
                )
                po = PurchaseOrder(
                    team_id=team,
                    po_number="PO-900-SAME",
                    supplier_id=supplier.id,
                    status=PurchaseOrderStatus.OPEN,
                )
                db.add(po)
                await db.flush()
                line = PoLine(
                    team_id=team,
                    po_id=po.id,
                    sku_id=sku.id,
                    supplier_code=None,
                    qty=2,
                    factory_unit_amount=Decimal("15.00"),
                    unit_cost_zar=Decimal("765432.10"),
                )
                db.add_all(
                    [
                        line,
                        SkuSupplierPrice(
                            team_id=team, sku_id=sku.id, supplier_id=supplier.id, supplier_sku=code
                        ),
                    ]
                )
                await db.commit()
                orders[team], suppliers[team], skus[team], lines[team] = (
                    po.id,
                    supplier.id,
                    sku.id,
                    line.id,
                )

        async def database():
            async with organisation_session(maker) as db:
                yield db

        app.dependency_overrides[get_db] = database
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.headers["Authorization"] = "Bearer " + signed_clerk_token(
                f"po900-{own.hex}", org_id=f"org-proof-{own.hex}", org_slug=f"proof-{own.hex}"
            )
            response = await client.get(f"/api/v1/purchase-orders/{orders[own]}/pdf")
            assert response.status_code == 200
            content = _pdf_text(response.content)
            assert "OWN-FACTORY-CODE" in content and "USD 30.00" in content
            assert "FOREIGN-FACTORY-CODE" not in content and "765432.10" not in content
            assert (
                await client.get(f"/api/v1/purchase-orders/{orders[foreign]}/pdf")
            ).status_code == 404
        async with organisation_session(maker, own) as db:
            assert (
                await SupplierCRUD(db).supplier_code_for_sku(suppliers[own], skus[own])
                == "OWN-FACTORY-CODE"
            )
            assert (
                await SupplierCRUD(db).supplier_code_for_sku(suppliers[foreign], skus[foreign])
                is None
            )
            assert (
                await db.scalar(select(PoLine.supplier_code).where(PoLine.id == lines[own])) is None
            )
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        async with admin.begin() as conn:
            for table in ("po_lines", "sku_supplier_prices", "purchase_orders", "suppliers"):
                await conn.execute(
                    text(f"DELETE FROM {table} WHERE team_id IN (:own,:foreign)"),
                    {"own": own, "foreign": foreign},
                )
