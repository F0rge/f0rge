"""Supplier invoice reading: match a purchase order, post, or explain the difference."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.schemas.document_intake import ExtractedDocument, ModelUsage
from app.services.document_intake.compare import compare_invoice
from app.services.document_intake.extract import prepare_document, text_is_usable

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "document_intake"
INVOICE_JSON = json.loads((FIXTURE_DIR / "invoice.json").read_text())
INVOICE_PDF = (FIXTURE_DIR / "sample_invoice.pdf").read_bytes()
PROFORMA_PDF = (FIXTURE_DIR / "sample_proforma.pdf").read_bytes()


def _usage() -> ModelUsage:
    return ModelUsage(model="test/mock", prompt_tokens=10, completion_tokens=20, total_tokens=30)


def _document(payload: dict) -> ExtractedDocument:
    return ExtractedDocument.model_validate(payload)


async def _fake_invoice(*_args, **_kwargs):
    return _document(INVOICE_JSON), _usage()


def _patch_extract(monkeypatch: pytest.MonkeyPatch, payload: dict | None = None) -> None:
    body = INVOICE_JSON if payload is None else payload

    async def _extract(*_args, **_kwargs):
        return _document(body), _usage()

    monkeypatch.setattr(
        "app.services.document_intake.extract.extract_supplier_document",
        _extract,
    )


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


async def _open_order(owner: AsyncClient) -> dict[str, str]:
    supplier = await owner.post(
        "/api/v1/suppliers",
        json={"name": "Cape Textile Co", "default_currency": "ZAR", "vat_number": "4987654321"},
    )
    assert supplier.status_code == 201, supplier.text
    supplier_id = supplier.json()["id"]
    red = await owner.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-RED",
            "our_barcode": "BAR-RED",
            "name": "Red linen cushion",
            "design": "Red",
            "fabric": "Linen",
        },
    )
    navy = await owner.post(
        "/api/v1/skus",
        json={
            "our_ref": "VEL-NAV",
            "our_barcode": "BAR-NAV",
            "name": "Navy linen cushion",
            "design": "Navy",
            "fabric": "Linen",
        },
    )
    assert red.status_code == 201 and navy.status_code == 201
    payload = {
        "supplier_id": supplier_id,
        "document_number": "PF-2041",
        "document_date": "2026-03-01",
        "currency": "ZAR",
        "vat_total": "303.90",
        "total": "2449.90",
        "charges": [{"description": "Shipping", "amount": "120.00"}],
        "lines": [
            {
                "supplier_code": "CUSH-RED",
                "description": "Red linen cushion 45cm",
                "qty": 10,
                "unit_price": "145.0000",
                "discount_percent": "0",
                "sku_id": red.json()["id"],
            },
            {
                "supplier_code": "CUSH-NAV",
                "description": "Navy linen cushion 45cm",
                "qty": 4,
                "unit_price": "144.0000",
                "discount_percent": "10",
                "sku_id": navy.json()["id"],
            },
        ],
    }
    confirmed = await owner.post(
        "/api/v1/document-intake/proformas/confirm",
        data={"payload": json.dumps(payload)},
        files={"file": ("sample_proforma.pdf", PROFORMA_PDF, "application/pdf")},
    )
    assert confirmed.status_code == 200, confirmed.text
    order = confirmed.json()["purchase_order"]
    return {
        "supplier_id": supplier_id,
        "po_id": order["id"],
        "po_number": order["po_number"],
        "red_id": red.json()["id"],
        "navy_id": navy.json()["id"],
    }


def _process_payload(order: dict[str, str], *, qty: int = 4, accept: bool = False) -> dict:
    return {
        "supplier_id": order["supplier_id"],
        "purchase_order_id": order["po_id"],
        "document_number": "INV-7781",
        "document_date": "2026-03-12",
        "currency": "ZAR",
        "accept_differences": accept,
        "vat_total": "303.90",
        "total": "2449.90",
        "charges": [{"description": "Shipping", "amount": "120.00"}],
        "lines": [
            {
                "supplier_code": "CUSH-RED",
                "description": "Red linen cushion 45cm",
                "qty": 10,
                "unit_price": "145.00",
                "discount_percent": "0",
                "sku_id": order["red_id"],
            },
            {
                "supplier_code": "CUSH-NAV",
                "description": "Navy linen cushion 45cm",
                "qty": qty,
                "unit_price": "144.00",
                "discount_percent": "10",
                "sku_id": order["navy_id"],
            },
        ],
    }


async def _extract(owner: AsyncClient):
    return await owner.post(
        "/api/v1/document-intake/invoices/extract",
        files={"file": ("sample_invoice.pdf", INVOICE_PDF, "application/pdf")},
    )


@pytest.mark.no_db
def test_sample_invoice_pdf_has_a_text_layer() -> None:
    prepared = prepare_document(INVOICE_PDF, "sample_invoice.pdf", "application/pdf")
    assert text_is_usable(prepared.text)
    assert "INV-7781" in prepared.text
    assert "PF-2041" in prepared.text
    assert "CUSH-RED" in prepared.text


@pytest.mark.no_db
def test_compare_explains_a_qty_and_price_difference() -> None:
    sku_id = uuid.uuid4()
    exact, differences = compare_invoice(
        currency="ZAR",
        po_currency="ZAR",
        po_lines=[(sku_id, "CUSH-RED", 10, Decimal("140"))],
        invoice_lines=[(3, sku_id, "Red cushion", 12, Decimal("145"))],
        po_charges=[],
        invoice_charges=[],
        po_vat=Decimal("0"),
        invoice_vat=Decimal("0"),
        po_total=Decimal("1400"),
        invoice_total=Decimal("1740"),
    )
    assert exact is False
    assert differences[0] == ("Line 3: invoice says 12 units at R145.00, order said 10 at R140.00.")


@pytest.mark.no_db
def test_compare_accepts_money_within_one_cent() -> None:
    red = uuid.uuid4()
    navy = uuid.uuid4()
    exact, differences = compare_invoice(
        currency="ZAR",
        po_currency="ZAR",
        po_lines=[
            (red, "VEL-RED", 10, Decimal("145.0000")),
            (navy, "VEL-NAV", 4, Decimal("144.0000")),
        ],
        invoice_lines=[
            (1, red, "Red linen cushion 45cm", 10, Decimal("145.00")),
            (2, navy, "Navy linen cushion 45cm", 4, Decimal("144.004")),
        ],
        po_charges=[("Shipping", Decimal("120"))],
        invoice_charges=[("shipping", Decimal("120.00"))],
        po_vat=Decimal("303.90"),
        invoice_vat=Decimal("303.900"),
        po_total=Decimal("2449.90"),
        invoice_total=Decimal("2449.90"),
    )
    assert exact is True
    assert differences == []


async def test_exact_invoice_waits_until_auto_process_is_on(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = await owner_client.get("/api/v1/settings")
    assert settings.status_code == 200
    assert settings.json()["auto_process_exact_supplier_invoices"] is False

    await _open_order(owner_client)
    _patch_extract(monkeypatch)
    first = await _extract(owner_client)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["exact"] is True
    assert body["differences"] == []
    assert body["processed"] is None
    assert body["auto_process_enabled"] is False
    assert body["needs_fx"] is False
    assert body["purchase_order"]["po_number"].startswith("PO-")
    assert body["document_number"] == "INV-7781"
    bills = await owner_client.get("/api/v1/bills")
    assert bills.json()["total"] == 0

    referenced = json.loads(json.dumps(INVOICE_JSON))
    referenced["po_reference"] = body["purchase_order"]["po_number"]
    referenced["proforma_number"] = None
    _patch_extract(monkeypatch, referenced)
    by_number = await _extract(owner_client)
    assert by_number.status_code == 200, by_number.text
    assert by_number.json()["exact"] is True
    assert by_number.json()["purchase_order"]["po_number"] == body["purchase_order"]["po_number"]

    turned_on = await owner_client.patch(
        "/api/v1/settings",
        json={"auto_process_exact_supplier_invoices": True},
    )
    assert turned_on.status_code == 200
    assert turned_on.json()["auto_process_exact_supplier_invoices"] is True

    _patch_extract(monkeypatch)
    posted = await _extract(owner_client)
    assert posted.status_code == 200, posted.text
    processed = posted.json()["processed"]
    assert processed["auto"] is True
    assert processed["po_number"] == body["purchase_order"]["po_number"]
    bill = await owner_client.get(f"/api/v1/bills/{processed['bill_id']}")
    assert bill.status_code == 200
    saved = bill.json()
    assert saved["supplier_ref"] == "INV-7781"
    assert saved["purchase_order_id"] == processed["purchase_order_id"]
    assert saved["pdf_storage_key"]
    assert saved["amount_foreign"] == "2449.90"
    assert any(line["description"].startswith("CUSH-RED") for line in saved["lines"])
    assert any(line["description"] == "VAT" for line in saved["lines"])
    assert any(line["description"] == "Shipping" for line in saved["lines"])
    events = await owner_client.get(
        "/api/v1/books-events",
        params={"document_type": "bill", "document_id": processed["bill_id"]},
    )
    assert events.status_code == 200
    assert "Auto-processed from supplier invoice INV-7781" in events.json()[0]["note"]

    again = await _extract(owner_client)
    assert again.status_code == 200, again.text
    assert again.json()["processed"] is None
    assert any(flag["code"] == "duplicate_invoice" for flag in again.json()["flags"])
    assert (await owner_client.get("/api/v1/bills")).json()["total"] == 1


async def test_mismatch_is_explained_and_can_be_accepted(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await owner_client.patch(
        "/api/v1/settings",
        json={"auto_process_exact_supplier_invoices": True},
    )
    order = await _open_order(owner_client)
    changed = json.loads(json.dumps(INVOICE_JSON))
    changed["lines"][1]["qty"] = "12"
    _patch_extract(monkeypatch, changed)
    reviewed = await _extract(owner_client)
    assert reviewed.status_code == 200, reviewed.text
    body = reviewed.json()
    assert body["exact"] is False
    assert body["processed"] is None
    assert any(
        "Line 2: invoice says 12 units at R144.00, order said 4 at R144.00." == row
        for row in body["differences"]
    )
    assert (await owner_client.get("/api/v1/bills")).json()["total"] == 0

    refused = await owner_client.post(
        "/api/v1/document-intake/invoices/process",
        data={"payload": json.dumps(_process_payload(order, qty=12, accept=False))},
        files={"file": ("sample_invoice.pdf", INVOICE_PDF, "application/pdf")},
    )
    assert refused.status_code == 400
    assert "Line 2: invoice says 12 units at R144.00, order said 4 at R144.00." in refused.text

    accepted = await owner_client.post(
        "/api/v1/document-intake/invoices/process",
        data={"payload": json.dumps(_process_payload(order, qty=12, accept=True))},
        files={"file": ("sample_invoice.pdf", INVOICE_PDF, "application/pdf")},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["auto"] is False
    bill = await owner_client.get(f"/api/v1/bills/{accepted.json()['bill_id']}")
    navy = next(line for line in bill.json()["lines"] if line["description"].startswith("CUSH-NAV"))
    assert navy["qty"] == 12
    events = await owner_client.get(
        "/api/v1/books-events",
        params={"document_type": "bill", "document_id": accepted.json()["bill_id"]},
    )
    assert events.json()[0]["note"].startswith("Processed from supplier invoice INV-7781")


async def test_duplicate_supplier_invoice_number_is_rejected(
    owner_client: AsyncClient,
) -> None:
    order = await _open_order(owner_client)
    first = await owner_client.post(
        "/api/v1/document-intake/invoices/process",
        data={"payload": json.dumps(_process_payload(order))},
        files={"file": ("sample_invoice.pdf", INVOICE_PDF, "application/pdf")},
    )
    assert first.status_code == 200, first.text
    second_payload = _process_payload(order)
    second_payload["document_number"] = "inv-7781"
    second = await owner_client.post(
        "/api/v1/document-intake/invoices/process",
        data={"payload": json.dumps(second_payload)},
        files={"file": ("sample_invoice.pdf", INVOICE_PDF, "application/pdf")},
    )
    assert second.status_code == 409
    assert "already on a bill" in second.text


async def test_foreign_exact_match_is_not_auto_posted(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await owner_client.patch(
        "/api/v1/settings",
        json={"auto_process_exact_supplier_invoices": True},
    )
    await _open_order(owner_client)
    foreign = json.loads(json.dumps(INVOICE_JSON))
    foreign["currency"] = "USD"
    _patch_extract(monkeypatch, foreign)
    reviewed = await _extract(owner_client)
    assert reviewed.status_code == 200, reviewed.text
    body = reviewed.json()
    assert body["needs_fx"] is True
    assert body["exact"] is False
    assert body["processed"] is None
    assert any("currency" in row.lower() for row in body["differences"])


async def test_invoice_permissions_follow_books_mutate(
    owner_client: AsyncClient,
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_extract(monkeypatch)
    await _create_user(owner_client, "buyer-invoice@example.com", "buyer")
    await _create_user(owner_client, "warehouse-invoice@example.com", "warehouse")
    await _create_user(owner_client, "books-invoice@example.com", "books")

    await _login(async_client, "buyer-invoice@example.com", "role-password")
    buyer = await _extract(async_client)
    assert buyer.status_code == 403

    await _login(async_client, "warehouse-invoice@example.com", "role-password")
    warehouse = await _extract(async_client)
    assert warehouse.status_code == 403

    await _login(async_client, "books-invoice@example.com", "role-password")
    books = await _extract(async_client)
    assert books.status_code == 200
    assert books.json()["document_number"] == "INV-7781"
