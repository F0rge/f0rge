"""Supplier proforma reading: match, review, guided SKU, purchase order."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sku_supplier_price import SkuSupplierPrice
from app.schemas.document_intake import ExtractedDocument, ExtractedLine, ModelUsage
from app.services.document_intake.extract import prepare_document, text_is_usable
from app.services.document_intake.matching import (
    PriceRecord,
    SkuRecord,
    SupplierRecord,
    match_sku_line,
    match_supplier,
)
from app.services.document_intake.pricing import net_unit_price

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "document_intake"
PROFORMA_JSON = json.loads((FIXTURE_DIR / "proforma.json").read_text())
PROFORMA_PDF = (FIXTURE_DIR / "sample_proforma.pdf").read_bytes()


def _usage() -> ModelUsage:
    return ModelUsage(model="test/mock", prompt_tokens=12, completion_tokens=30, total_tokens=42)


async def _fake_extract(*_args, **_kwargs):
    return ExtractedDocument.model_validate(PROFORMA_JSON), _usage()


async def _login(client: AsyncClient, email: str, password: str) -> None:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def _create_user(owner: AsyncClient, email: str, role: str) -> None:
    resp = await owner.post(
        "/api/v1/users",
        json={"email": email, "password": "role-password", "role": role},
    )
    assert resp.status_code == 201


@pytest.mark.no_db
def test_sample_proforma_pdf_has_a_text_layer() -> None:
    prepared = prepare_document(PROFORMA_PDF, "sample_proforma.pdf", "application/pdf")
    assert text_is_usable(prepared.text)
    assert "PF-2041" in prepared.text
    assert "CUSH-RED" in prepared.text
    assert prepared.pdf_bytes is None


@pytest.mark.no_db
def test_photo_is_prepared_for_vision() -> None:
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    prepared = prepare_document(png, "scan.png", "image/png")
    assert prepared.text == ""
    assert prepared.images[0][0] == "image/png"
    assert prepared.pdf_bytes is None


@pytest.mark.no_db
def test_net_unit_applies_percent_discount() -> None:
    net = net_unit_price(Decimal("160.00"), Decimal("4"), Decimal("10"), None)
    assert net == Decimal("144.0000")


@pytest.mark.no_db
def test_supplier_match_prefers_vat_number() -> None:
    supplier_id = uuid.uuid4()
    chosen, _candidates = match_supplier(
        "Cape Textile",
        "498 765 4321",
        "Cape Town",
        [
            SupplierRecord(
                id=supplier_id,
                name="Cape Textile Co",
                vat_number="4987654321",
                address="12 Main Road",
            )
        ],
    )
    assert chosen.supplier_id == supplier_id
    assert chosen.confidence == 1.0
    assert "VAT number" in chosen.reason


@pytest.mark.no_db
def test_sku_match_order_is_supplier_code_then_barcode_then_description() -> None:
    red_id = uuid.uuid4()
    navy_id = uuid.uuid4()
    supplier_id = uuid.uuid4()
    skus = [
        SkuRecord(
            id=red_id,
            our_ref="VEL-RED",
            our_barcode="BAR-RED",
            name="Something else",
            design="Red",
            fabric="Linen",
            supplier_ref=None,
        ),
        SkuRecord(
            id=navy_id,
            our_ref="VEL-NAV",
            our_barcode="BAR-NAV",
            name="Navy linen cushion 45cm",
            design="Navy",
            fabric="Linen",
            supplier_ref=None,
        ),
    ]
    prices = [
        PriceRecord(sku_id=red_id, supplier_id=supplier_id, supplier_sku="CUSH-RED"),
    ]
    red_line = ExtractedLine(
        supplier_code="cush-red",
        description="Red linen cushion 45cm",
        qty=Decimal("10"),
        unit_price=Decimal("145"),
    )
    match, _alts = match_sku_line(red_line, skus, prices, supplier_id)
    assert match is not None
    assert match.sku_id == red_id
    assert match.confidence == 1.0
    assert "Supplier product code" in match.reason

    barcode_line = ExtractedLine(
        supplier_code="BAR-NAV", description="Other", qty=Decimal("1"), unit_price=Decimal("1")
    )
    barcode_match, _alts = match_sku_line(barcode_line, skus, prices, supplier_id)
    assert barcode_match is not None
    assert barcode_match.sku_id == navy_id
    assert "Barcode" in barcode_match.reason

    fuzzy_line = ExtractedLine(
        supplier_code="UNKNOWN",
        description="Navy linen cushion 45cm",
        qty=Decimal("4"),
        unit_price=Decimal("160"),
    )
    fuzzy, _alts = match_sku_line(fuzzy_line, skus, prices, supplier_id)
    assert fuzzy is not None
    assert fuzzy.sku_id == navy_id
    assert fuzzy.confidence < 0.9
    assert "Description" in fuzzy.reason


async def test_extract_does_not_save_and_flags_review(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.document_intake.extract.extract_supplier_document",
        _fake_extract,
    )
    before = await owner_client.get("/api/v1/proformas")
    assert before.status_code == 200
    resp = await owner_client.post(
        "/api/v1/document-intake/proformas/extract",
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_number"] == "PF-2041"
    assert body["supplier"]["supplier_id"] is None
    assert body["supplier"]["confidence"] == 0
    assert body["usage"]["model"] == "test/mock"
    assert any(flag["code"] == "unmatched_sku" for flag in body["lines"][0]["flags"])
    assert body["payment_terms"] == "50% deposit, balance before dispatch"
    after = await owner_client.get("/api/v1/proformas")
    assert after.json() == before.json()
    orders = await owner_client.get("/api/v1/purchase-orders")
    assert orders.json()["total"] == 0


async def test_extract_matches_supplier_vat_and_supplier_code(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.document_intake.extract.extract_supplier_document",
        _fake_extract,
    )
    supplier = await owner_client.post(
        "/api/v1/suppliers",
        json={
            "name": "Cape Textile Co",
            "default_currency": "ZAR",
            "vat_number": "498 765 4321",
            "address": "12 Main Road, Cape Town",
        },
    )
    assert supplier.status_code == 201
    supplier_id = supplier.json()["id"]
    assert supplier.json()["vat_number"] == "4987654321"

    sku = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-RED",
            "our_barcode": "BAR-RED",
            "name": "Red cushion",
            "design": "Red block",
            "fabric": "Linen",
        },
    )
    assert sku.status_code == 201
    price = await owner_client.post(
        "/api/v1/document-intake/skus",
        json={
            "our_ref": "VEL-RED-2",
            "our_barcode": "BAR-RED-2",
            "name": "Red cushion priced",
            "design": "Red priced",
            "fabric": "Linen",
            "supplier_ref": "CUSH-RED",
            "supplier_id": supplier_id,
            "supplier_sku": "CUSH-RED",
            "latest_price": "145.00",
        },
    )
    assert price.status_code == 200
    sku_id = price.json()["sku"]["id"]

    resp = await owner_client.post(
        "/api/v1/document-intake/proformas/extract",
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["supplier"]["supplier_id"] == supplier_id
    assert body["supplier"]["confidence"] == 1.0
    red = body["lines"][0]
    assert red["match"]["sku_id"] == sku_id
    assert red["match"]["confidence"] == 1.0
    assert red["net_unit_price"] == "145.0000"
    navy = body["lines"][1]
    assert navy["net_unit_price"] == "144.0000"
    assert any(flag["code"] == "unmatched_sku" for flag in navy["flags"])
    assert not any(flag["code"] == "totals_mismatch" for flag in body["flags"])


async def test_totals_mismatch_is_flagged(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = json.loads(json.dumps(PROFORMA_JSON))
    bad["total"] = "9999.00"

    async def _bad_extract(*_args, **_kwargs):
        return ExtractedDocument.model_validate(bad), _usage()

    monkeypatch.setattr(
        "app.services.document_intake.extract.extract_supplier_document",
        _bad_extract,
    )
    resp = await owner_client.post(
        "/api/v1/document-intake/proformas/extract",
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert resp.status_code == 200
    flags = resp.json()["flags"]
    mismatch = next(flag for flag in flags if flag["code"] == "totals_mismatch")
    assert "do not add up" in mismatch["message"].lower()


async def test_guided_sku_hint_and_confirm_creates_open_po(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.document_intake.extract.extract_supplier_document",
        _fake_extract,
    )

    async def _hint(*_args, **_kwargs):
        return {
            "name": "Navy linen cushion",
            "design": "Navy cushion",
            "fabric": "Linen",
            "category": "Soft Furnishings",
        }

    monkeypatch.setattr("app.services.document_intake.extract.suggest_sku_fields", _hint)

    bare = await owner_client.post(
        "/api/v1/document-intake/sku-suggestions",
        json={
            "description": "Red linen cushion 45cm",
            "supplier_code": "CUSH-RED",
            "unit_price": "145.00",
        },
    )
    assert bare.status_code == 200
    assert bare.json()["source"] == "document"
    assert bare.json()["category"] is None
    assert bare.json()["fabric"] == "Unspecified"

    hinted = await owner_client.post(
        "/api/v1/document-intake/sku-suggestions",
        json={
            "description": "Navy linen cushion 45cm",
            "supplier_code": "CUSH-NAV",
            "unit_price": "144.00",
            "hint": "these are all cushions, use category Soft Furnishings",
        },
    )
    assert hinted.status_code == 200
    hint_body = hinted.json()
    assert hint_body["source"] == "model"
    assert hint_body["category"] == "Soft Furnishings"
    assert hint_body["name"] == "Navy linen cushion"

    supplier = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "Cape Textile Co", "default_currency": "ZAR", "vat_number": "4987654321"},
    )
    supplier_id = supplier.json()["id"]
    red = await owner_client.post(
        "/api/v1/document-intake/skus",
        json={
            "our_ref": bare.json()["our_ref"],
            "our_barcode": bare.json()["our_barcode"],
            "name": "Red linen cushion",
            "design": "Red cushion",
            "fabric": "Linen",
            "supplier_ref": "CUSH-RED",
            "supplier_id": supplier_id,
            "supplier_sku": "CUSH-RED",
            "latest_price": "145.00",
        },
    )
    assert red.status_code == 200
    navy = await owner_client.post(
        "/api/v1/document-intake/skus",
        json={
            "our_ref": hint_body["our_ref"],
            "our_barcode": hint_body["our_barcode"],
            "name": hint_body["name"],
            "design": hint_body["design"],
            "fabric": hint_body["fabric"],
            "category": hint_body["category"],
            "supplier_ref": "CUSH-NAV",
            "supplier_id": supplier_id,
            "supplier_sku": "CUSH-NAV",
            "latest_price": "144.0000",
        },
    )
    assert navy.status_code == 200

    payload = {
        "supplier_id": supplier_id,
        "document_number": "PF-2041",
        "document_date": "2026-03-01",
        "currency": "ZAR",
        "payment_terms": "50% deposit, balance before dispatch",
        "deposit": "50%",
        "vat_total": "303.90",
        "total": "2449.90",
        "charges": [{"description": "Shipping", "amount": "120.00"}],
        "lines": [
            {
                "supplier_code": "CUSH-RED",
                "description": "Red linen cushion 45cm",
                "qty": 10,
                "unit_price": "145.0000",
                "sku_id": red.json()["sku"]["id"],
                "skip": False,
            },
            {
                "supplier_code": "CUSH-NAV",
                "description": "Navy linen cushion 45cm",
                "qty": 4,
                "unit_price": "144.0000",
                "sku_id": navy.json()["sku"]["id"],
                "skip": False,
            },
        ],
    }
    resp = await owner_client.post(
        "/api/v1/document-intake/proformas/confirm",
        data={"payload": json.dumps(payload)},
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["purchase_order"]["status"] == "open"
    assert body["purchase_order"]["proforma_id"] == body["proforma"]["id"]
    assert body["proforma"]["invoice_number"] == "PF-2041"
    assert len(body["purchase_order"]["lines"]) == 2
    po_id = body["purchase_order"]["id"]
    stored = await owner_client.get(f"/api/v1/purchase-orders/{po_id}")
    assert stored.json()["status"] == "open"

    prices = (
        (
            await async_db.execute(
                select(SkuSupplierPrice).where(
                    SkuSupplierPrice.supplier_id == uuid.UUID(supplier_id)
                )
            )
        )
        .scalars()
        .all()
    )
    codes = {row.supplier_sku for row in prices}
    assert codes == {"CUSH-RED", "CUSH-NAV"}

    again = await owner_client.post(
        "/api/v1/document-intake/proformas/extract",
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert any(flag["code"] == "duplicate_proforma" for flag in again.json()["flags"])
    duplicate = await owner_client.post(
        "/api/v1/document-intake/proformas/confirm",
        data={"payload": json.dumps(payload)},
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert duplicate.status_code == 409


async def test_confirm_can_create_a_new_supplier(
    owner_client: AsyncClient,
) -> None:
    sku = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-ONE",
            "our_barcode": "BAR-ONE",
            "name": "Side table",
            "design": "Side",
            "fabric": "Oak",
        },
    )
    assert sku.status_code == 201
    payload = {
        "create_supplier": {
            "name": "New Mill Imports",
            "vat_number": "4111111111",
            "address": "1 Mill Street, Johannesburg",
            "default_currency": "ZAR",
        },
        "document_number": "PF-9",
        "document_date": "2026-04-01",
        "currency": "ZAR",
        "lines": [
            {
                "description": "Side table",
                "qty": 1,
                "unit_price": "500.00",
                "sku_id": sku.json()["id"],
            }
        ],
    }
    resp = await owner_client.post(
        "/api/v1/document-intake/proformas/confirm",
        data={"payload": json.dumps(payload)},
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    suppliers = await owner_client.get("/api/v1/suppliers")
    created = next(row for row in suppliers.json() if row["name"] == "New Mill Imports")
    assert created["vat_number"] == "4111111111"
    assert created["address"] == "1 Mill Street, Johannesburg"


async def test_warehouse_and_books_cannot_read_proformas(
    owner_client: AsyncClient,
    async_client: AsyncClient,
) -> None:
    await _create_user(owner_client, "warehouse-intake@example.com", "warehouse")
    await _create_user(owner_client, "books-intake@example.com", "books")
    await _login(async_client, "warehouse-intake@example.com", "role-password")
    warehouse = await async_client.post(
        "/api/v1/document-intake/proformas/extract",
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert warehouse.status_code == 403
    await _login(async_client, "books-intake@example.com", "role-password")
    books = await async_client.post(
        "/api/v1/document-intake/sku-suggestions",
        json={"description": "Cushion"},
    )
    assert books.status_code == 403


async def test_buyer_can_extract_proforma(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.document_intake.extract.extract_supplier_document",
        _fake_extract,
    )
    await _create_user(owner_client, "buyer-intake@example.com", "buyer")
    await _login(async_client, "buyer-intake@example.com", "role-password")
    resp = await async_client.post(
        "/api/v1/document-intake/proformas/extract",
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert resp.status_code == 200
