"""Read APIs over imported Cin7 detail: addresses, contacts, supplier prices, history, bins."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.supplier import Supplier
from app.services.cin7_import.load import run_import
from app.services.sku_bom import whole_component_qty
from f0rge_core.exceptions import ValidationError
from tests.test_cin7_import import _fixture_dir


async def _load(async_db: AsyncSession, tmp_path: Path) -> None:
    await run_import(async_db, _fixture_dir(tmp_path / "cin7"))
    await async_db.commit()


async def _login_as(owner_client: AsyncClient, role: str) -> AsyncClient:
    email = f"{role}-records@example.com"
    created = await owner_client.post(
        "/api/v1/users", json={"email": email, "password": f"{role}-password", "role": role}
    )
    assert created.status_code == 201
    owner_client.cookies.clear()
    login = await owner_client.post(
        "/api/v1/auth/login", json={"email": email, "password": f"{role}-password"}
    )
    assert login.status_code == 200
    return owner_client


async def test_party_addresses_and_contacts(
    owner_client: AsyncClient, async_db: AsyncSession, tmp_path: Path
) -> None:
    await _load(async_db, tmp_path)
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
    owner_client: AsyncClient, async_db: AsyncSession, tmp_path: Path
) -> None:
    await _load(async_db, tmp_path)
    resp = await owner_client.get("/api/v1/history/sales")
    assert resp.status_code == 200
    kinds = {(row["kind"], row["document_number"]) for row in resp.json()["items"]}
    assert ("invoice", "INV-9001") in kinds
    assert ("credit_note", "CR-9001") in kinds
    only_credit = await owner_client.get("/api/v1/history/sales", params={"q": "CR-9001"})
    assert only_credit.json()["total"] == 1
    assert Decimal(only_credit.json()["items"][0]["inc_vat"]) == Decimal("-115.00")


async def test_purchase_history_and_supplier_prices_hide_cost(
    owner_client: AsyncClient, async_db: AsyncSession, tmp_path: Path
) -> None:
    await _load(async_db, tmp_path)
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


async def test_stock_by_bin(
    owner_client: AsyncClient, async_db: AsyncSession, tmp_path: Path
) -> None:
    await _load(async_db, tmp_path)
    resp = await owner_client.get("/api/v1/stock/by-bin", params={"q": "CHAIR-1"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items and items[0]["on_hand"] == 2
    assert items[0]["bin_code"]


async def test_records_require_login(async_client: AsyncClient) -> None:
    for path in ("/api/v1/history/sales", "/api/v1/supplier-prices", "/api/v1/stock/by-bin"):
        assert (await async_client.get(path)).status_code == 401


def test_whole_component_qty_refuses_fractional_need() -> None:
    assert whole_component_qty(Decimal("2"), 3) == 6
    assert whole_component_qty(Decimal("0.5"), 2) == 1
    with pytest.raises(ValidationError):
        whole_component_qty(Decimal("0.5"), 1)
