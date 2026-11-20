"""Basket lines reserve company stock; open baskets expire lazily (spec #979, ticket #984)."""

from __future__ import annotations

import asyncio
import datetime
import uuid

from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import LocationStock
from app.models.location import Location
from app.models.stock_reservation import StockReservation
from app.models.tax_invoice import TaxInvoice
from app.models.till_basket import TillBasket
from app.models.user import User
from app.schemas.held_sale import TillBasketUpdate
from app.services.locations import LocationSeedService
from app.services.till_basket import TillBasketService
from f0rge_core.exceptions import ConflictError
from f0rge_db.crud import unit_of_work
from tests.conftest import authenticate_as
from tests.test_purchase_orders import _create_till, _location_id_by_name, _relogin_owner
from tests.test_sku_archive_commit_races import isolated_requests
from tests.test_sku_bom import _sku
from tests.test_till import _inventory_on_hand
from tests.test_till_basket import BASKET, SALES, _fill, _get, _line, _put

RESERVATIONS = "/api/v1/till/reservations"
TILL_EMAIL = "till-po@example.com"


async def _stocked(client: AsyncClient, ref: str, location: str, qty: int = 3) -> dict:
    return await _sku(
        client,
        ref,
        opening_location_id=location,
        opening_qty=qty,
        opening_cost="40.00",
        retail_ex_vat="100.00",
    )


async def _as(client: AsyncClient, email: str) -> None:
    client.cookies.clear()
    client.headers.pop("Authorization", None)
    assert (await authenticate_as(client, email)).status_code == 200


async def _second_user(client: AsyncClient, db: AsyncSession) -> None:
    """Create the second cashier; the client is left signed in as the owner."""
    await _create_till(client, client)
    await db.commit()
    await _relogin_owner(client)


async def _reservations(db: AsyncSession, basket_id: str) -> dict[str, int]:
    rows = await db.execute(
        select(StockReservation.sku_id, StockReservation.qty).where(
            StockReservation.holder_id == uuid.UUID(basket_id)
        )
    )
    return {str(sku): qty for sku, qty in rows}


async def _lapse(db: AsyncSession, basket_id: str) -> None:
    """Put the basket's expiry (and its reservations') in the past."""
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
    for model, column in ((TillBasket, TillBasket.id), (StockReservation, None)):
        query = update(model).values(expires_at=past).execution_options(synchronize_session=False)
        query = query.where(
            column == uuid.UUID(basket_id)
            if column is not None
            else StockReservation.holder_id == uuid.UUID(basket_id)
        )
        await db.execute(query)


async def test_add_reserves_and_second_basket_sees_reduced_availability(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    sofa = await _stocked(owner_client, "RES-SOFA", showroom, 2)
    bench = await _stocked(owner_client, "RES-WAREHOUSE-ONLY", warehouse, 1)
    mine = await _get(owner_client, showroom)

    saved = await _fill(owner_client, mine, [_line(sofa, 2), _line(bench, 1)])
    assert await _reservations(async_db, mine["id"]) == {sofa["id"]: 2, bench["id"]: 1}
    expires = datetime.datetime.fromisoformat(saved["expires_at"])
    assert saved["expired_at"] is None
    assert expires > datetime.datetime.now(datetime.timezone.utc)

    await _second_user(async_client, async_db)
    await _as(async_client, TILL_EMAIL)
    theirs = await _get(async_client, showroom)
    blocked = await async_client.put(
        f"{BASKET}/{theirs['id']}", json=_put(theirs, [_line(sofa, 1)])
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "stock_reserved"
    assert detail["sku_id"] == sofa["id"] and detail["available"] == 0
    assert detail["blocking"]["location_name"] == "Bedfordview"
    assert detail["blocking"]["location_id"] == showroom
    assert detail["blocking"]["holder_kind"] == "basket"
    assert detail["blocking"]["expires_at"] == saved["expires_at"]
    assert detail["basket"]["version"] == 1 and detail["basket"]["lines"] == []
    assert (await _get(async_client, showroom)) == theirs
    assert await _reservations(async_db, theirs["id"]) == {}

    seen = (await async_client.get(RESERVATIONS, params={"location_id": showroom})).json()
    assert {row["sku_id"]: row["reserved_by_others"] for row in seen} == {
        sofa["id"]: 2,
        bench["id"]: 1,
    }
    assert seen[0]["blocking"]["location_name"] == "Bedfordview"
    assert seen[0]["blocking"]["expires_at"] == saved["expires_at"]

    # The reserver never sees its own basket in the list, and may keep editing it.
    await _relogin_owner(async_client)
    assert (await async_client.get(RESERVATIONS, params={"location_id": showroom})).json() == []
    assert (await _fill(async_client, saved, [_line(sofa, 2)]))["version"] == 3


async def test_lowering_or_removing_a_line_releases_units(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "RES-LOWER", showroom, 3)
    chair = await _stocked(owner_client, "RES-LOWER-CHAIR", showroom, 3)
    mine = await _get(owner_client, showroom)
    full = await _fill(owner_client, mine, [_line(sofa, 3), _line(chair, 2)])
    await _second_user(async_client, async_db)
    await _as(async_client, TILL_EMAIL)
    theirs = await _get(async_client, showroom)
    assert (
        await async_client.put(f"{BASKET}/{theirs['id']}", json=_put(theirs, [_line(sofa, 1)]))
    ).status_code == 409

    await _relogin_owner(async_client)
    lowered = await _fill(async_client, full, [_line(sofa, 2), _line(chair, 2)])
    assert await _reservations(async_db, mine["id"]) == {sofa["id"]: 2, chair["id"]: 2}
    await _as(async_client, TILL_EMAIL)
    taken = await _fill(async_client, theirs, [_line(sofa, 1)])

    await _relogin_owner(async_client)
    emptied = await _fill(async_client, lowered, [])
    assert emptied["expires_at"] is None
    assert await _reservations(async_db, mine["id"]) == {}
    await _as(async_client, TILL_EMAIL)
    assert (await _fill(async_client, taken, [_line(sofa, 3), _line(chair, 3)]))["version"] == 3


async def test_sale_releases_reservations_and_deducts_as_before(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "RES-SALE", showroom, 5)
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 2)])
    assert await _reservations(async_db, basket["id"]) == {sofa["id"]: 2}
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
    assert await _reservations(async_db, basket["id"]) == {}
    assert await _inventory_on_hand(owner_client, sofa["id"], showroom) == 3
    emptied = await _get(owner_client, showroom)
    assert emptied["lines"] == [] and emptied["expires_at"] is None


async def test_expired_basket_is_emptied_on_read_and_frees_stock(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "RES-EXPIRE", showroom, 1)
    mine = await _get(owner_client, showroom)
    saved = await _fill(owner_client, mine, [_line(sofa, 1)], note="for Sam")
    await _second_user(async_client, async_db)
    await _lapse(async_db, mine["id"])

    # Expired reservations stop counting at once, before anything is pruned.
    await _as(async_client, TILL_EMAIL)
    assert (await async_client.get(RESERVATIONS, params={"location_id": showroom})).json() == []
    theirs = await _get(async_client, showroom)
    assert (await _fill(async_client, theirs, [_line(sofa, 1)]))["version"] == 2

    await _relogin_owner(async_client)
    gone = await _get(async_client, showroom)
    assert gone["lines"] == [] and gone["note"] is None and gone["expires_at"] is None
    assert gone["expired_at"] is not None and gone["version"] == saved["version"] + 1
    assert await _get(async_client, showroom) == gone
    assert await _reservations(async_db, mine["id"]) == {}


async def test_writes_prune_expired_rows_for_the_whole_tenant(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "RES-PRUNE", showroom, 1)
    chair = await _stocked(owner_client, "RES-PRUNE-CHAIR", showroom, 1)
    mine = await _get(owner_client, showroom)
    await _fill(owner_client, mine, [_line(sofa, 1)])
    await _second_user(async_client, async_db)
    await _lapse(async_db, mine["id"])

    await _as(async_client, TILL_EMAIL)
    theirs = await _get(async_client, showroom)
    await _fill(async_client, theirs, [_line(chair, 1)])
    assert (
        await async_db.scalar(
            select(func.count())
            .select_from(StockReservation)
            .where(StockReservation.holder_id == uuid.UUID(mine["id"]))
        )
        == 0
    )
    row = await async_db.scalar(
        select(TillBasket)
        .where(TillBasket.id == uuid.UUID(mine["id"]))
        .execution_options(populate_existing=True)
    )
    assert row.lines == [] and row.expired_at is not None


async def test_put_and_sale_on_an_expired_basket_are_refused(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "RES-LATE", showroom, 4)
    mine = await _get(owner_client, showroom)
    saved = await _fill(owner_client, mine, [_line(sofa, 2)])
    await _lapse(async_db, mine["id"])
    invoices = await async_db.scalar(select(func.count()).select_from(TaxInvoice))

    sale = await owner_client.post(
        SALES,
        json={
            "location_id": showroom,
            "lines": [{"sku_id": sofa["id"], "qty": 2}],
            "tender": "cash",
            "basket_id": mine["id"],
            "basket_version": saved["version"],
        },
    )
    assert sale.status_code == 409, sale.text
    detail = sale.json()["detail"]
    assert detail["code"] == "basket_expired"
    assert detail["message"].startswith("This sale expired at ")
    assert detail["message"].endswith(". Add the items again.")
    assert detail["basket"]["lines"] == [] and detail["basket"]["expired_at"] is not None
    assert await async_db.scalar(select(func.count()).select_from(TaxInvoice)) == invoices
    assert await _inventory_on_hand(owner_client, sofa["id"], showroom) == 4

    refilled = await _fill(owner_client, detail["basket"], [_line(sofa, 2)])
    await _lapse(async_db, mine["id"])
    late = await owner_client.put(f"{BASKET}/{mine['id']}", json=_put(refilled, [_line(sofa, 1)]))
    assert late.status_code == 409
    assert late.json()["detail"]["code"] == "basket_expired"
    assert late.json()["detail"]["basket"]["lines"] == []
    assert await _reservations(async_db, mine["id"]) == {}


async def test_every_change_restarts_the_clock_from_the_hold_time(
    owner_client: AsyncClient, async_db: AsyncSession
):
    assert (
        await owner_client.patch("/api/v1/settings", json={"till_hold_hours": 5})
    ).status_code == 200
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "RES-CLOCK", showroom, 4)
    basket = await _get(owner_client, showroom)
    assert basket["expires_at"] is None

    before = datetime.datetime.now(datetime.timezone.utc)
    first = await _fill(owner_client, basket, [_line(sofa, 1)])
    stamp = datetime.datetime.fromisoformat(first["expires_at"])
    assert (
        before + datetime.timedelta(hours=5)
        <= stamp
        <= datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5)
    )
    await asyncio.sleep(0.05)
    second = await _fill(owner_client, first, [_line(sofa, 2)])
    assert datetime.datetime.fromisoformat(second["expires_at"]) > stamp
    reservation = await async_db.scalar(
        select(StockReservation.expires_at).where(
            StockReservation.holder_id == uuid.UUID(basket["id"])
        )
    )
    assert (
        reservation.isoformat() == datetime.datetime.fromisoformat(second["expires_at"]).isoformat()
    )


async def test_kits_and_no_stock_needed_skus_reserve_nothing(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    part = await _stocked(owner_client, "RES-KIT-PART", showroom, 1)
    kit = await _sku(owner_client, "RES-KIT", retail_ex_vat="500.00")
    assert (
        await owner_client.put(
            f"/api/v1/skus/{kit['id']}/bom",
            json={"lines": [{"component_sku_id": part["id"], "qty": 1}]},
        )
    ).status_code == 200
    service = await _sku(owner_client, "RES-DELIVERY", retail_ex_vat="100.00")
    assert (
        await owner_client.patch(
            f"/api/v1/skus/{service['id']}", json={"till_no_stock_required": True}
        )
    ).status_code == 200

    basket = await _fill(
        owner_client,
        await _get(owner_client, showroom),
        [_line(kit, 3), _line(service, 2), _line(part, 1)],
    )
    assert await _reservations(async_db, basket["id"]) == {part["id"]: 1}


async def test_last_unit_race_has_exactly_one_winner(second_postgres_url):
    async with isolated_requests(second_postgres_url) as (maker, ids):
        second_user, first_basket, second_basket = uuid.uuid4(), None, None
        async with maker() as db:
            await LocationSeedService(db).seed_if_empty()
            async with unit_of_work(db):
                showroom = await db.scalar(
                    select(Location.id).where(Location.name == "Bedfordview")
                )
                db.add(
                    User(
                        id=second_user,
                        team_id=ids["team"],
                        email="racer@example.com",
                        password_hash="unused",
                        role="till",
                    )
                )
                db.add(
                    LocationStock(
                        sku_id=ids["sku"], location_id=showroom, on_hand=1, unit_cost_zar=40
                    )
                )
            first_basket = await TillBasketService(db).get_or_create(showroom, ids["actor"])
            second_basket = await TillBasketService(db).get_or_create(showroom, second_user)

        async def reserve(basket, user):
            body = TillBasketUpdate(
                version=basket.version,
                operation_id=uuid.uuid4(),
                lines=[{"sku_id": ids["sku"], "qty": 1}],
            )
            async with maker() as db:
                try:
                    await TillBasketService(db).replace(basket.id, body, user)
                    return "ok"
                except ConflictError as exc:
                    return exc.payload["code"]

        results = await asyncio.wait_for(
            asyncio.gather(
                reserve(first_basket, ids["actor"]), reserve(second_basket, second_user)
            ),
            15,
        )
        assert sorted(results) == ["ok", "stock_reserved"]
        async with maker() as db:
            total = await db.scalar(select(func.sum(StockReservation.qty)))
            assert total == 1
