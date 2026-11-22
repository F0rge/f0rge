"""Cost of goods out equals cost restocked back: a stock movement returns what it consumed.

Each flow receives stock at a different cost between the stock leaving and coming back, so the
location's average moves underneath it. That is the case that booked the wrong cost before.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import LocationStock
from app.models.layby import LaybyLine
from app.models.tax_invoice import InvoiceLine
from app.models.unit_cost_audit import UnitCostAuditSource
from app.models.user import User
from app.services.stock_movements import StockCost, StockMovementService
from f0rge_core.exceptions import ValidationError
from tests.test_ledger_accounts import _account_balance
from tests.test_till import _set_retail_price

COGS = "5000"


async def _owner_id(db: AsyncSession) -> uuid.UUID:
    owner_id = await db.scalar(select(User.id).where(User.role == "owner"))
    assert owner_id is not None
    return owner_id


async def _receive(db: AsyncSession, sku_id: str, location_id: str, qty: str, cost: str) -> None:
    await StockMovementService(db).apply_incoming_qty(
        uuid.UUID(sku_id),
        uuid.UUID(location_id),
        Decimal(qty),
        Decimal(cost),
        await _owner_id(db),
        UnitCostAuditSource.RECEIVE,
        "Test receipt",
    )
    await db.flush()


async def _sku_in_showroom(
    client: AsyncClient, db: AsyncSession, ref: str, qty: str = "1", cost: str = "100.00"
) -> tuple[str, str]:
    locations = (await client.get("/api/v1/locations")).json()
    showroom = next(row["id"] for row in locations if row["name"] == "Bedfordview")
    created = await client.post(
        "/api/v1/skus",
        json={"our_ref": ref, "our_barcode": ref, "name": ref, "design": ref, "fabric": "Linen"},
    )
    assert created.status_code == 201, created.text
    sku_id = created.json()["id"]
    await _set_retail_price(client, sku_id, "1000.00")
    await _receive(db, sku_id, showroom, qty, cost)
    return sku_id, showroom


async def _average(db: AsyncSession, sku_id: str, location_id: str) -> Decimal:
    return await db.scalar(
        select(LocationStock.unit_cost_zar).where(
            LocationStock.sku_id == uuid.UUID(sku_id),
            LocationStock.location_id == uuid.UUID(location_id),
        )
    )


async def _cogs(client: AsyncClient) -> Decimal:
    return Decimal(await _account_balance(client, COGS))


async def _restock_return(client: AsyncClient, db: AsyncSession, invoice_id: str, location_id: str):
    line = await db.scalar(
        select(InvoiceLine).where(InvoiceLine.invoice_id == uuid.UUID(invoice_id))
    )
    assert line is not None
    created = await client.post(
        "/api/v1/returns",
        json={
            "invoice_id": invoice_id,
            "location_id": location_id,
            "reason": "damaged",
            "disposition": "restock",
            "lines": [{"invoice_line_id": str(line.id), "qty": 1}],
        },
    )
    assert created.status_code == 201, created.text
    completed = await client.post(f"/api/v1/returns/{created.json()['id']}/complete")
    assert completed.status_code == 200, completed.text
    return line


async def _layby(client: AsyncClient, sku_id: str, location_id: str) -> str:
    customer = await client.post("/api/v1/customers", json={"name": "Cost Customer"})
    created = await client.post(
        "/api/v1/laybys",
        json={
            "customer_id": customer.json()["id"],
            "location_id": location_id,
            "due_date": "2026-12-31",
            "hold_stock": True,
            "deposit_amount": "1150.00",
            "tender": "cash",
            "lines": [{"sku_id": sku_id, "qty": 1}],
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def test_outgoing_returns_the_cost_it_consumed(owner_client, async_db):
    sku_id, showroom = await _sku_in_showroom(owner_client, async_db, "COST-OUT", "3", "10.0050")
    movements = StockMovementService(async_db)

    taken = await movements.apply_outgoing_qty(
        uuid.UUID(sku_id),
        uuid.UUID(showroom),
        Decimal(1),
        await _owner_id(async_db),
        UnitCostAuditSource.ADJUSTMENT,
        "Test issue",
    )

    assert taken == StockCost(Decimal(1), Decimal("10.0050"))
    assert taken.total_zar == Decimal("10.01")  # rounded once, half-up to the cent
    assert await _average(async_db, sku_id, showroom) == Decimal("10.0050")
    with pytest.raises(ValidationError, match="unit cost required"):
        _ = StockCost(Decimal(1), None).total_zar


async def test_layby_hold_complete_return_books_the_hold_cost(owner_client, async_db):
    sku_id, showroom = await _sku_in_showroom(owner_client, async_db, "COST-LAYBY")
    layby_id = await _layby(owner_client, sku_id, showroom)
    held = await async_db.scalar(select(LaybyLine).where(LaybyLine.layby_id == uuid.UUID(layby_id)))
    assert held is not None and held.hold_unit_cost_zar == Decimal("100.00")

    # The shelf is empty after the hold; the next unit costs three times as much.
    await _receive(async_db, sku_id, showroom, "1", "300.00")
    cogs_before = await _cogs(owner_client)
    completed = await owner_client.post(f"/api/v1/laybys/{layby_id}/complete")
    assert completed.status_code == 200, completed.text
    assert await _cogs(owner_client) - cogs_before == Decimal("100.00")

    cogs_before = await _cogs(owner_client)
    line = await _restock_return(owner_client, async_db, completed.json()["invoice_id"], showroom)
    assert line.unit_cost_zar == Decimal("100.00")
    assert await _cogs(owner_client) - cogs_before == Decimal("-100.00")
    # One unit at 300 and the returned one at the 100 it left at.
    assert await _average(async_db, sku_id, showroom) == Decimal("200.00")


async def test_layby_cancel_restocks_at_the_hold_cost(owner_client, async_db):
    sku_id, showroom = await _sku_in_showroom(owner_client, async_db, "COST-LAYBY-CANCEL")
    layby_id = await _layby(owner_client, sku_id, showroom)
    await _receive(async_db, sku_id, showroom, "1", "300.00")

    cancelled = await owner_client.post(f"/api/v1/laybys/{layby_id}/cancel")

    assert cancelled.status_code == 200, cancelled.text
    assert await _average(async_db, sku_id, showroom) == Decimal("200.00")


async def test_till_sale_return_restocks_at_the_cost_the_sale_booked(owner_client, async_db):
    sku_id, showroom = await _sku_in_showroom(owner_client, async_db, "COST-TILL")
    cogs_before = await _cogs(owner_client)
    sale = await owner_client.post(
        "/api/v1/till/sales",
        json={"location_id": showroom, "lines": [{"sku_id": sku_id, "qty": 1}], "tender": "cash"},
    )
    assert sale.status_code == 201, sale.text
    assert await _cogs(owner_client) - cogs_before == Decimal("100.00")

    await _receive(async_db, sku_id, showroom, "1", "300.00")
    cogs_before = await _cogs(owner_client)
    line = await _restock_return(owner_client, async_db, sale.json()["invoice_id"], showroom)

    assert line.unit_cost_zar == Decimal("100.00")
    assert await _cogs(owner_client) - cogs_before == Decimal("-100.00")
    assert await _average(async_db, sku_id, showroom) == Decimal("200.00")


async def test_till_sale_writes_no_cost_audit_row_yet(owner_client, async_db):
    """Deferred one release so a rolled-back image can read "till"; the follow-up flips this."""
    sku_id, showroom = await _sku_in_showroom(owner_client, async_db, "COST-TILL-AUDIT")
    sale = await owner_client.post(
        "/api/v1/till/sales",
        json={"location_id": showroom, "lines": [{"sku_id": sku_id, "qty": 1}], "tender": "cash"},
    )
    assert sale.status_code == 201, sale.text

    audit = await owner_client.get(f"/api/v1/skus/{sku_id}/cost-audit")

    assert audit.status_code == 200
    assert [row for row in audit.json() if row["source"] == "till"] == []
