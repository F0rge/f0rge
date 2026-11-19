"""Read APIs over imported Cin7 detail: addresses, contacts, supplier prices, history, bins."""

from __future__ import annotations

from tests.conftest import authenticate_as, create_test_staff

from decimal import Decimal
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.archive_credit_note import ArchiveCreditNote, ArchiveCreditNoteLine
from app.models.bill import Bill, BillLine
from app.models.cin7_party import CustomerAddress, CustomerContact, SupplierAddress, SupplierContact
from app.models.location_bin import BinStock, LocationBin
from app.models.sku import Sku
from app.models.sku_supplier_price import SkuSupplierPrice
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.services.sku_bom import whole_component_qty
from f0rge_core.exceptions import ValidationError


async def _load(async_db: AsyncSession) -> None:
    customer = Customer(name="Fixture Buyer", customer_type="trade")
    supplier = Supplier(name="Fixture Mill")
    sku = Sku(
        our_ref="CHAIR-1", our_barcode="CHAIR-1", name="Chair", design="Oak", fabric="Natural"
    )
    async_db.add_all([customer, supplier, sku])
    await async_db.flush()
    bin_id = await async_db.scalar(select(LocationBin.id).limit(1))
    amounts = dict(
        issue_date=date(2025, 1, 1), subtotal_ex_vat=100, vat_amount=15, total_inc_vat=115
    )
    async_db.add_all(
        [
            CustomerAddress(customer_id=customer.id, natural_key="address", city="Johannesburg"),
            CustomerContact(customer_id=customer.id, natural_key="contact", name="Buyer"),
            SupplierAddress(supplier_id=supplier.id, natural_key="address", city="Cape Town"),
            SupplierContact(supplier_id=supplier.id, natural_key="contact", name="Ada"),
            SkuSupplierPrice(sku_id=sku.id, supplier_id=supplier.id, latest_price=100),
            BinStock(sku_id=sku.id, bin_id=bin_id, on_hand=Decimal("2.4")),
            TaxInvoice(
                invoice_number="INV-9001",
                customer_id=customer.id,
                is_archive=True,
                lines=[
                    InvoiceLine(
                        description="Chair",
                        sku_id=sku.id,
                        qty=1,
                        unit_ex_vat=100,
                        ex_vat=100,
                        vat_amount=15,
                        inc_vat=115,
                    )
                ],
                **amounts,
            ),
            ArchiveCreditNote(
                document_number="CR-9001",
                lines=[
                    ArchiveCreditNoteLine(
                        description="Returned chair",
                        sku_id=sku.id,
                        qty=-1,
                        ex_vat=-100,
                        vat_amount=-15,
                        inc_vat=-115,
                    )
                ],
                customer_id=customer.id,
                issue_date=date(2025, 1, 2),
                subtotal_ex_vat=-100,
                vat_amount=-15,
                total_inc_vat=-115,
            ),
            Bill(
                bill_number="AP-001",
                lines=[BillLine(description="Chair", qty=1, unit_amount=10, amount_foreign=10)],
                is_archive=True,
                supplier_id=supplier.id,
                supplier_ref="A",
                issue_date=date(2025, 1, 1),
                currency="USD",
                fx_to_zar=1,
                amount_foreign=10,
                amount_zar=10,
                fx_rate_known=False,
            ),
        ]
    )
    await async_db.commit()


async def _login_as(owner_client: AsyncClient, role: str) -> AsyncClient:
    email = f"{role}-records@example.com"
    await create_test_staff(
        owner_client, **{"email": email, "password": f"{role}-password", "role": role}
    )
    owner_client.cookies.clear()
    owner_client.headers.pop("Authorization", None)
    login = await authenticate_as(owner_client, email)
    assert login.status_code == 200
    return owner_client


async def test_party_addresses_and_contacts(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    await _load(async_db)
    customer = (
        await async_db.execute(select(Customer).where(Customer.name == "Fixture Buyer"))
    ).scalar_one()
    supplier = (
        await async_db.execute(select(Supplier).where(Supplier.name == "Fixture Mill"))
    ).scalar_one()

    addresses = await owner_client.get(f"/api/v1/customers/{customer.id}/addresses")
    assert addresses.status_code == 200
    assert addresses.json()
    contacts = await owner_client.get(f"/api/v1/customers/{customer.id}/contacts")
    assert contacts.status_code == 200
    supplier_contacts = await owner_client.get(f"/api/v1/suppliers/{supplier.id}/contacts")
    assert [row["name"] for row in supplier_contacts.json()] == ["Ada"]
    supplier_addresses = await owner_client.get(f"/api/v1/suppliers/{supplier.id}/addresses")
    assert len(supplier_addresses.json()) == 1

    missing = await owner_client.get(
        "/api/v1/customers/00000000-0000-0000-0000-000000000000/addresses"
    )
    assert missing.status_code == 404


async def test_sales_history_includes_archive_credit_notes(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    await _load(async_db)
    resp = await owner_client.get("/api/v1/history/sales")
    assert resp.status_code == 200
    kinds = {(row["kind"], row["document_number"]) for row in resp.json()["items"]}
    assert ("invoice", "INV-9001") in kinds
    assert ("credit_note", "CR-9001") in kinds
    only_credit = await owner_client.get("/api/v1/history/sales", params={"q": "CR-9001"})
    assert only_credit.json()["total"] == 1
    assert Decimal(only_credit.json()["items"][0]["inc_vat"]) == Decimal("-115.00")


async def test_purchase_history_and_supplier_prices_hide_cost(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    await _load(async_db)
    bills = await owner_client.get("/api/v1/history/purchases")
    assert bills.status_code == 200
    row = bills.json()["items"][0]
    assert row["currency"] == "USD"
    assert row["fx_rate_known"] is False
    assert row["bill_amount_zar"] is None
    assert row["amount_foreign"] is not None

    prices = await owner_client.get("/api/v1/supplier-prices")
    assert prices.status_code == 200
    assert prices.json()["total"] >= 1

    client = await _login_as(owner_client, "warehouse")
    hidden = await client.get("/api/v1/history/purchases")
    assert hidden.json()["items"][0]["amount_foreign"] is None
    hidden_prices = await client.get("/api/v1/supplier-prices")
    assert all(item["latest_price"] is None for item in hidden_prices.json()["items"])


async def test_stock_by_bin(owner_client: AsyncClient, async_db: AsyncSession) -> None:
    await _load(async_db)
    resp = await owner_client.get("/api/v1/stock/by-bin", params={"q": "CHAIR-1"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items and items[0]["on_hand"] == 2.4
    assert items[0]["bin_code"]


async def test_records_require_login(async_client: AsyncClient) -> None:
    for path in ("/api/v1/history/sales", "/api/v1/supplier-prices", "/api/v1/stock/by-bin"):
        assert (await async_client.get(path)).status_code == 401


def test_whole_component_qty_refuses_fractional_need() -> None:
    assert whole_component_qty(Decimal("2"), 3) == 6
    assert whole_component_qty(Decimal("0.5"), 2) == 1
    with pytest.raises(ValidationError):
        whole_component_qty(Decimal("0.5"), 1)
