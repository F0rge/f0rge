"""Customer classification selects the SKU price and the VAT display."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from httpx import AsyncClient
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.sales_order import SalesOrderCreate, SalesOrderLineCreate
from app.services.cin7_import.parse import NAMED_PRICE_TIERS, tier_price_list_name
from app.services.pricing import (
    classification_for_legacy_customer_type,
    is_cin7_generated_price_list,
)
from app.services.sales_orders import SalesOrdersService
from tests.test_price_lists import _stock_sku_at_bedford
from tests.test_purchase_orders import _create_till

_MIGRATION = (
    Path(__file__).resolve().parents[1] / "migrations" / "versions" / "076_sku_price_tiers.py"
)

_TIERS = (
    ("Stockist", "700.00", False),
    ("Wholesale", "800.00", False),
    ("Decorator", "900.00", False),
    ("Retail", "1000.00", True),
)


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


@pytest.mark.no_db
def test_cin7_generated_list_names_do_not_count_as_overrides() -> None:
    for tier, name, _includes_vat in NAMED_PRICE_TIERS:
        assert tier_price_list_name(tier) == name
        assert is_cin7_generated_price_list(name)
    for tier in range(1, 11):
        assert is_cin7_generated_price_list(f"Cin7 Tier {tier}")
    assert is_cin7_generated_price_list("  Cin7 Tier 4  ")
    assert not is_cin7_generated_price_list("Decorator")
    assert not is_cin7_generated_price_list("Cin7")
    assert not is_cin7_generated_price_list("Cin7 Tier")
    assert not is_cin7_generated_price_list(None)


@pytest.mark.no_db
def test_migration_maps_trade_customers_to_wholesale() -> None:
    assert classification_for_legacy_customer_type("trade") == "Wholesale"
    assert classification_for_legacy_customer_type("retail") == "Retail"
    assert classification_for_legacy_customer_type(None) == "Retail"
    source = _MIGRATION.read_text()
    assert "WHEN customer_type = 'trade' THEN 'Wholesale'" in source
    assert "ELSE 'Retail'" in source
    assert "down_revision" in source
    assert "075_po_pending_skus" in source


async def _customer(owner_client: AsyncClient, classification: str) -> dict:
    created = await owner_client.post(
        "/api/v1/customers",
        json={"name": f"Class {classification}", "price_classification": classification},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["price_classification"] == classification
    assert body["customer_type"] == ("retail" if classification == "Retail" else "trade")
    return body


async def test_legacy_customer_type_sets_classification(owner_client: AsyncClient) -> None:
    trade = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Legacy Trade", "customer_type": "trade"},
    )
    assert trade.status_code == 201, trade.text
    assert trade.json()["price_classification"] == "Wholesale"
    assert trade.json()["customer_type"] == "trade"

    retail = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Legacy Retail", "customer_type": "retail"},
    )
    assert retail.status_code == 201, retail.text
    assert retail.json()["price_classification"] == "Retail"


async def test_each_classification_prices_till_quote_invoice_and_order(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    sku_id, bedford_id = await _stock_sku_at_bedford(
        async_client, owner_client, "CLASS-TIER", qty=8
    )
    priced = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={
            "stockist_ex_vat": "700.00",
            "wholesale_ex_vat": "800.00",
            "decorator_ex_vat": "900.00",
            "retail_ex_vat": "1000.00",
        },
    )
    assert priced.status_code == 200, priced.text
    customers: list[tuple[str, str, bool]] = []

    for classification, expected, include_vat in _TIERS:
        customer = await _customer(owner_client, classification)
        customer_id = customer["id"]
        customers.append((customer_id, expected, include_vat))

        quote = await owner_client.post(
            "/api/v1/quotes",
            json={"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": 1}]},
        )
        assert quote.status_code == 201, quote.text
        quote_body = quote.json()
        assert Decimal(quote_body["lines"][0]["unit_ex_vat"]) == Decimal(expected)
        assert quote_body["lines"][0]["price_warning"] is None
        assert quote_body["prices_include_vat"] is include_vat

        invoice = await owner_client.post(
            "/api/v1/invoices",
            json={
                "customer_id": customer_id,
                "issue_date": "2026-10-21",
                "lines": [{"description": classification, "qty": 1, "sku_id": sku_id}],
            },
        )
        assert invoice.status_code == 201, invoice.text
        invoice_body = invoice.json()
        assert Decimal(invoice_body["lines"][0]["unit_ex_vat"]) == Decimal(expected)
        assert invoice_body["lines"][0]["price_warning"] is None
        assert invoice_body["prices_include_vat"] is include_vat

        order = await SalesOrdersService(async_db).create_draft(
            SalesOrderCreate(
                customer_id=customer_id,
                lines=[SalesOrderLineCreate(sku_id=sku_id, qty=1)],
            )
        )
        assert order.lines[0].unit_ex_vat == Decimal(expected)
        assert order.lines[0].price_warning is None
        assert order.prices_include_vat is include_vat

    till = await _create_till(async_client, owner_client)
    for customer_id, expected, include_vat in customers:
        sale = await till.post(
            "/api/v1/till/sales",
            json={
                "location_id": bedford_id,
                "customer_id": customer_id,
                "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "0"}],
                "tender": "cash",
            },
        )
        assert sale.status_code == 201, sale.text
        sale_body = sale.json()
        assert Decimal(sale_body["lines"][0]["unit_ex_vat"]) == Decimal(expected)
        assert sale_body["lines"][0]["price_warning"] is None
        assert sale_body["prices_include_vat"] is include_vat
        if expected == "1000.00":
            assert Decimal(sale_body["subtotal_ex_vat"]) == Decimal("1000.00")
            assert Decimal(sale_body["vat_amount"]) == Decimal("150.00")
            assert Decimal(sale_body["total_inc_vat"]) == Decimal("1150.00")

    walk_in = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "0"}],
            "tender": "cash",
        },
    )
    assert walk_in.status_code == 201, walk_in.text
    assert Decimal(walk_in.json()["lines"][0]["unit_ex_vat"]) == Decimal("1000.00")
    assert walk_in.json()["prices_include_vat"] is True


async def test_retail_pdf_shows_inclusive_unit_and_same_vat_totals(
    owner_client: AsyncClient,
) -> None:
    from tests.test_sku_bom import _sku

    sku = await _sku(owner_client, "VAT-RETAIL", retail_ex_vat="1000.00")
    customer = await _customer(owner_client, "Retail")
    quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer["id"], "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert quote.status_code == 201, quote.text
    body = quote.json()
    assert body["subtotal_ex_vat"] == "1000.00"
    assert body["vat_amount"] == "150.00"
    assert body["total_inc_vat"] == "1150.00"
    assert body["lines"][0]["unit_ex_vat"] == "1000.00"
    pdf = await owner_client.get(f"/api/v1/quotes/{body['id']}/pdf")
    assert pdf.status_code == 200
    text = _pdf_text(pdf.content)
    assert "1150.00 incl. VAT" in text
    assert "Unit prices incl. VAT" in text
    assert "150.00" in text

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer["id"],
            "issue_date": "2026-10-21",
            "lines": [{"description": "Retail chair", "qty": 1, "sku_id": sku["id"]}],
        },
    )
    assert invoice.status_code == 201, invoice.text
    invoice_body = invoice.json()
    assert invoice_body["subtotal_ex_vat"] == "1000.00"
    assert invoice_body["vat_amount"] == "150.00"
    assert invoice_body["total_inc_vat"] == "1150.00"
    invoice_pdf = await owner_client.get(f"/api/v1/invoices/{invoice_body['id']}/pdf")
    assert invoice_pdf.status_code == 200
    invoice_text = _pdf_text(invoice_pdf.content)
    assert "1150.00 incl. VAT" in invoice_text
    assert "Unit prices incl. VAT" in invoice_text


async def test_wholesale_pdf_shows_exclusive_unit(
    owner_client: AsyncClient,
) -> None:
    from tests.test_sku_bom import _sku

    sku = await _sku(owner_client, "VAT-WHOLESALE", retail_ex_vat="1000.00")
    patched = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "800.00"},
    )
    assert patched.status_code == 200, patched.text
    customer = await _customer(owner_client, "Wholesale")
    quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer["id"], "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert quote.status_code == 201, quote.text
    body = quote.json()
    assert body["lines"][0]["unit_ex_vat"] == "800.00"
    assert body["prices_include_vat"] is False
    assert body["total_inc_vat"] == "920.00"
    pdf = await owner_client.get(f"/api/v1/quotes/{body['id']}/pdf")
    text = _pdf_text(pdf.content)
    assert "800.00 excl. VAT" in text
    assert "Unit prices excl. VAT" in text
    assert "920.00" in text


async def test_missing_tier_falls_back_to_retail_with_a_warning(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stock_sku_at_bedford(
        async_client, owner_client, "CLASS-FALLBACK", qty=4
    )
    priced = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={
            "stockist_ex_vat": None,
            "wholesale_ex_vat": "50.00",
            "decorator_ex_vat": None,
            "retail_ex_vat": "1000.00",
        },
    )
    assert priced.status_code == 200, priced.text
    customer = await _customer(owner_client, "Stockist")
    customer_id = customer["id"]

    quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": 1}]},
    )
    assert quote.status_code == 201, quote.text
    line = quote.json()["lines"][0]
    assert Decimal(line["unit_ex_vat"]) == Decimal("1000.00")
    assert "Stockist price is missing" in line["price_warning"]
    assert "Retail" in line["price_warning"]

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-10-21",
            "lines": [{"description": "Fallback", "qty": 1, "sku_id": sku_id}],
        },
    )
    assert invoice.status_code == 201, invoice.text
    invoice_line = invoice.json()["lines"][0]
    assert Decimal(invoice_line["unit_ex_vat"]) == Decimal("1000.00")
    assert "using Retail price" in invoice_line["price_warning"]

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "customer_id": customer_id,
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "0"}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201, sale.text
    assert Decimal(sale.json()["lines"][0]["unit_ex_vat"]) == Decimal("1000.00")
    assert "using Retail price" in sale.json()["lines"][0]["price_warning"]


async def test_reprice_drafts_waits_for_confirm_and_leaves_invoices(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    from tests.test_sku_bom import _sku

    sku = await _sku(owner_client, "REPRICE", retail_ex_vat="1000.00")
    patched = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "800.00", "decorator_ex_vat": "600.00"},
    )
    assert patched.status_code == 200, patched.text
    customer = await _customer(owner_client, "Wholesale")
    customer_id = customer["id"]

    draft = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]

    sent = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert sent.status_code == 201, sent.text
    sent_id = sent.json()["id"]
    marked = await owner_client.post(f"/api/v1/quotes/{sent_id}/mark-sent")
    assert marked.status_code == 200, marked.text

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-10-21",
            "lines": [{"description": "Issued", "qty": 1, "sku_id": sku["id"]}],
        },
    )
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["id"]
    assert invoice.json()["lines"][0]["unit_ex_vat"] == "800.00"

    order = await SalesOrdersService(async_db).create_draft(
        SalesOrderCreate(
            customer_id=customer_id,
            lines=[SalesOrderLineCreate(sku_id=sku["id"], qty=1)],
        )
    )
    assert order.lines[0].unit_ex_vat == Decimal("800.00")

    changed = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"price_classification": "Decorator"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["price_classification"] == "Decorator"
    assert changed.json()["draft_quote_count"] == 1
    assert changed.json()["draft_sales_order_count"] == 1

    still_draft = await owner_client.get(f"/api/v1/quotes/{draft_id}")
    assert still_draft.json()["lines"][0]["unit_ex_vat"] == "800.00"
    still_sent = await owner_client.get(f"/api/v1/quotes/{sent_id}")
    assert still_sent.json()["lines"][0]["unit_ex_vat"] == "800.00"
    still_invoice = await owner_client.get(f"/api/v1/invoices/{invoice_id}")
    assert still_invoice.json()["lines"][0]["unit_ex_vat"] == "800.00"
    still_order = await SalesOrdersService(async_db).get(order.id)
    assert still_order.lines[0].unit_ex_vat == Decimal("800.00")

    repriced = await owner_client.post(f"/api/v1/customers/{customer_id}/reprice-drafts")
    assert repriced.status_code == 200, repriced.text
    assert repriced.json() == {"quotes": 1, "sales_orders": 1}

    after_draft = await owner_client.get(f"/api/v1/quotes/{draft_id}")
    assert after_draft.json()["lines"][0]["unit_ex_vat"] == "600.00"
    assert after_draft.json()["prices_include_vat"] is False
    after_sent = await owner_client.get(f"/api/v1/quotes/{sent_id}")
    assert after_sent.json()["lines"][0]["unit_ex_vat"] == "800.00"
    after_invoice = await owner_client.get(f"/api/v1/invoices/{invoice_id}")
    assert after_invoice.json()["lines"][0]["unit_ex_vat"] == "800.00"
    after_order = await SalesOrdersService(async_db).get(order.id)
    assert after_order.lines[0].unit_ex_vat == Decimal("600.00")


async def test_cin7_tier_4_list_does_not_override_classification(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    """Old Cin7 Tier 4 stored the inc-VAT figure as if it were ex VAT."""
    sku_id, bedford_id = await _stock_sku_at_bedford(
        async_client, owner_client, "CIN7-TIER4", qty=4
    )
    cin7_list = await owner_client.post("/api/v1/price-lists", json={"name": "Cin7 Tier 4"})
    assert cin7_list.status_code == 201, cin7_list.text
    cin7_list_id = cin7_list.json()["id"]
    cin7_item = await owner_client.put(
        f"/api/v1/price-lists/{cin7_list_id}/items",
        json={"sku_id": sku_id, "unit_ex_vat": "1150.00"},
    )
    assert cin7_item.status_code == 200, cin7_item.text

    handmade = await owner_client.post("/api/v1/price-lists", json={"name": "Counter special"})
    assert handmade.status_code == 201, handmade.text
    handmade_id = handmade.json()["id"]
    handmade_item = await owner_client.put(
        f"/api/v1/price-lists/{handmade_id}/items",
        json={"sku_id": sku_id, "unit_ex_vat": "650.00"},
    )
    assert handmade_item.status_code == 200, handmade_item.text

    retail = await owner_client.post(
        "/api/v1/customers",
        json={
            "name": "Retail on Cin7 Tier 4",
            "price_classification": "Retail",
            "price_list_id": cin7_list_id,
        },
    )
    assert retail.status_code == 201, retail.text
    wholesale = await owner_client.post(
        "/api/v1/customers",
        json={
            "name": "Wholesale on Cin7 Tier 4",
            "price_classification": "Wholesale",
            "price_list_id": cin7_list_id,
        },
    )
    assert wholesale.status_code == 201, wholesale.text
    special = await owner_client.post(
        "/api/v1/customers",
        json={
            "name": "Retail on a hand-made list",
            "price_classification": "Retail",
            "price_list_id": handmade_id,
        },
    )
    assert special.status_code == 201, special.text

    retail_quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": retail.json()["id"], "lines": [{"sku_id": sku_id, "qty": 1}]},
    )
    assert retail_quote.status_code == 201, retail_quote.text
    assert retail_quote.json()["lines"][0]["unit_ex_vat"] == "1000.00"
    assert retail_quote.json()["lines"][0]["price_warning"] is None
    assert retail_quote.json()["prices_include_vat"] is True

    retail_invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": retail.json()["id"],
            "issue_date": "2026-10-21",
            "lines": [{"description": "Tier 4 ignored", "qty": 1, "sku_id": sku_id}],
        },
    )
    assert retail_invoice.status_code == 201, retail_invoice.text
    assert retail_invoice.json()["lines"][0]["unit_ex_vat"] == "1000.00"

    wholesale_quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": wholesale.json()["id"], "lines": [{"sku_id": sku_id, "qty": 1}]},
    )
    assert wholesale_quote.status_code == 201, wholesale_quote.text
    assert wholesale_quote.json()["lines"][0]["unit_ex_vat"] == "800.00"
    assert wholesale_quote.json()["prices_include_vat"] is False

    special_quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": special.json()["id"], "lines": [{"sku_id": sku_id, "qty": 1}]},
    )
    assert special_quote.status_code == 201, special_quote.text
    assert special_quote.json()["lines"][0]["unit_ex_vat"] == "650.00"

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "customer_id": retail.json()["id"],
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "0"}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["lines"][0]["unit_ex_vat"] == "1000.00"
    assert sale.json()["prices_include_vat"] is True
