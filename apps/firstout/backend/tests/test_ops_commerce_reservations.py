"""Ops availability subtracts live till reservations (spec #979, ticket #988)."""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.sku import Sku
from app.models.stock_reservation import StockReservation
from app.models.team import Team
from tests.test_purchase_orders import _location_id_by_name
from tests.test_till_basket import SALES, _fill, _get, _line
from tests.test_till_reservations import _lapse, _stocked

FEED = "/api/v1/ops-commerce/v1/products"


async def _feed_setup(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, sku_id: str
) -> dict[str, str]:
    company_id = (await db.execute(select(Team.id))).scalar_one()
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id))
    monkeypatch.setattr(settings, "ops_commerce_token", "qa-ops-token")
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test")
    sku = await db.get(Sku, uuid.UUID(sku_id))
    assert sku is not None
    sku.storefront_published = True
    await db.flush()
    return {"Authorization": "Bearer qa-ops-token", "X-Ops-Company-ID": str(company_id)}


async def _product(client: AsyncClient, headers: dict[str, str], sku_id: str) -> dict:
    response = await client.get(FEED, headers=headers)
    assert response.status_code == 200, response.text
    return next(row for row in response.json()["products"] if row["source_sku_id"] == sku_id)


async def test_basket_reservation_lowers_feed_and_release_restores_it(
    owner_client: AsyncClient, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "OPS-RES-BASKET", showroom, 5)
    headers = await _feed_setup(async_db, monkeypatch, sofa["id"])
    before = await _product(owner_client, headers, sofa["id"])
    assert before["available_quantity"] == 5

    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 2)])
    reserved = await _product(owner_client, headers, sofa["id"])
    assert reserved["available_quantity"] == 3
    assert reserved["revision"] > before["revision"]

    await _fill(owner_client, basket, [])
    released = await _product(owner_client, headers, sofa["id"])
    assert released["available_quantity"] == 5
    assert released["revision"] > reserved["revision"]


async def test_expired_reservation_is_not_subtracted(
    owner_client: AsyncClient, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "OPS-RES-EXPIRED", showroom, 5)
    headers = await _feed_setup(async_db, monkeypatch, sofa["id"])
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 4)])
    reserved = await _product(owner_client, headers, sofa["id"])
    assert reserved["available_quantity"] == 1

    await _lapse(async_db, basket["id"])
    await async_db.flush()
    lapsed = await _product(owner_client, headers, sofa["id"])
    assert lapsed["available_quantity"] == 5
    assert lapsed["revision"] > reserved["revision"]


async def test_reservations_never_push_the_feed_below_zero(
    owner_client: AsyncClient, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "OPS-RES-FLOOR", showroom, 2)
    headers = await _feed_setup(async_db, monkeypatch, sofa["id"])
    await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 2)])
    assert (await _product(owner_client, headers, sofa["id"]))["available_quantity"] == 0


async def test_completed_sale_is_counted_once(
    owner_client: AsyncClient, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "OPS-RES-SALE", showroom, 5)
    headers = await _feed_setup(async_db, monkeypatch, sofa["id"])
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 2)])
    assert (await _product(owner_client, headers, sofa["id"]))["available_quantity"] == 3

    sale = await owner_client.post(
        SALES,
        json={
            "location_id": showroom,
            "lines": [{"sku_id": sofa["id"], "qty": 2}],
            "tender": "cash",
            "basket_id": basket["id"],
            "basket_version": basket["version"],
        },
    )
    assert sale.status_code == 201, sale.text
    # Stock is deducted and the reservation is gone: 5 - 2, not 5 - 2 - 2.
    assert (await _product(owner_client, headers, sofa["id"]))["available_quantity"] == 3


async def test_revision_is_stable_without_change_and_survives_prune(
    owner_client: AsyncClient, async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "OPS-RES-STABLE", showroom, 5)
    headers = await _feed_setup(async_db, monkeypatch, sofa["id"])
    first = await _product(owner_client, headers, sofa["id"])
    assert (await _product(owner_client, headers, sofa["id"]))["revision"] == first["revision"]

    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 2)])
    reserved = await _product(owner_client, headers, sofa["id"])
    assert reserved["revision"] > first["revision"]
    assert (await _product(owner_client, headers, sofa["id"]))["revision"] == reserved["revision"]

    # Lazy expiry (not yet pruned): the revision rises to the expiry time.
    await _lapse(async_db, basket["id"])
    await async_db.flush()
    lapsed = await _product(owner_client, headers, sofa["id"])
    assert lapsed["available_quantity"] == 5
    assert lapsed["revision"] > reserved["revision"]

    # Pruning deletes the row; the trigger marks the change, so the revision never regresses.
    await async_db.execute(
        delete(StockReservation).where(StockReservation.sku_id == UUID(sofa["id"]))
    )
    await async_db.flush()
    pruned = await _product(owner_client, headers, sofa["id"])
    assert pruned["available_quantity"] == 5
    assert pruned["revision"] >= lapsed["revision"]
