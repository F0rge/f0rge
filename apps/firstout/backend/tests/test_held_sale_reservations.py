"""Held sales keep their reservations and expire (spec #979, ticket #985)."""

from __future__ import annotations

import datetime
import uuid

from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.held_sale import HeldSale
from app.models.stock_reservation import StockReservation
from tests.test_purchase_orders import _location_id_by_name, _relogin_owner
from tests.test_till_basket import BASKET, HELD, _fill, _get, _line, _put
from tests.test_till_reservations import TILL_EMAIL, _as, _reservations, _second_user, _stocked

HOUR = datetime.timedelta(hours=1)


def _when(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def _hold(client: AsyncClient, location: str, basket: dict, lines: list[dict]) -> dict:
    response = await client.post(
        HELD,
        json={
            "id": str(uuid.uuid4()),
            "location_id": location,
            "lines": lines,
            "basket_id": basket["id"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _resume(held: dict, basket: dict, **extra) -> dict:
    return {
        "operation_id": str(uuid.uuid4()),
        "location_id": held["location_id"],
        "version": held["version"],
        "basket_id": basket["id"],
        **extra,
    }


async def _list(client: AsyncClient, location: str) -> list[dict]:
    response = await client.get(HELD, params={"location_id": location})
    assert response.status_code == 200, response.text
    return response.json()


async def _lapse(db: AsyncSession, held_id: str) -> None:
    past = _now() - datetime.timedelta(minutes=5)
    holder = uuid.UUID(held_id)
    await db.execute(
        update(HeldSale)
        .where(HeldSale.id == holder)
        .values(expires_at=past)
        .execution_options(synchronize_session=False)
    )
    await db.execute(
        update(StockReservation)
        .where(StockReservation.holder_id == holder)
        .values(expires_at=past)
        .execution_options(synchronize_session=False)
    )
    await db.commit()


async def _held_rows(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(HeldSale))


async def _reserved_expiry(db: AsyncSession, holder_id: str) -> set[datetime.datetime]:
    rows = await db.scalars(
        select(StockReservation.expires_at).where(
            StockReservation.holder_id == uuid.UUID(holder_id)
        )
    )
    return set(rows)


async def test_hold_keeps_reservations_and_other_baskets_stay_blocked(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "HR-HOLD", showroom, 2)
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 2)])

    before = _now()
    held = await _hold(owner_client, showroom, basket, [_line(sofa, 2)])
    expires = _when(held["expires_at"])
    assert before + 3 * HOUR <= expires <= _now() + 3 * HOUR
    assert await _reservations(async_db, held["id"]) == {sofa["id"]: 2}
    assert await _reservations(async_db, basket["id"]) == {}
    assert await _reserved_expiry(async_db, held["id"]) == {expires}
    emptied = await _get(owner_client, showroom)
    assert emptied["lines"] == [] and emptied["expires_at"] is None

    await _second_user(async_client, async_db)
    await _as(async_client, TILL_EMAIL)
    theirs = await _get(async_client, showroom)
    blocked = await async_client.put(
        f"{BASKET}/{theirs['id']}", json=_put(theirs, [_line(sofa, 1)])
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "stock_reserved"
    assert detail["blocking"]["holder_kind"] == "held_sale"
    assert detail["blocking"]["location_name"] == "Bedfordview"
    assert _when(detail["blocking"]["expires_at"]) == expires


async def test_hold_without_basket_reserves_nothing_but_still_expires(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "HR-PLAIN", showroom, 2)
    held = await owner_client.post(
        HELD, json={"id": str(uuid.uuid4()), "location_id": showroom, "lines": [_line(sofa, 2)]}
    )
    assert held.status_code == 201, held.text
    assert _when(held.json()["expires_at"]) > _now() + 2 * HOUR
    assert await _reservations(async_db, held.json()["id"]) == {}


async def test_resume_moves_reservations_to_the_basket_and_restarts_the_clock(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "HR-RESUME", showroom, 2)
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 2)])
    held = await _hold(owner_client, showroom, basket, [_line(sofa, 2)])

    resumed = await owner_client.post(f"{HELD}/{held['id']}/resume", json=_resume(held, basket))
    assert resumed.status_code == 200, resumed.text
    loaded = resumed.json()["basket"]
    assert _when(loaded["expires_at"]) > _when(held["expires_at"])
    assert await _reservations(async_db, held["id"]) == {}
    assert await _reservations(async_db, basket["id"]) == {sofa["id"]: 2}
    assert await _reserved_expiry(async_db, basket["id"]) == {_when(loaded["expires_at"])}
    assert await _list(owner_client, showroom) == []

    await _second_user(async_client, async_db)
    await _as(async_client, TILL_EMAIL)
    theirs = await _get(async_client, showroom)
    blocked = await async_client.put(
        f"{BASKET}/{theirs['id']}", json=_put(theirs, [_line(sofa, 1)])
    )
    assert blocked.json()["detail"]["blocking"]["holder_kind"] == "basket"


async def test_resume_of_a_sale_held_before_reservations_reserves_and_rechecks_stock(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "HR-LEGACY", showroom, 2)
    held = (
        await owner_client.post(
            HELD, json={"id": str(uuid.uuid4()), "location_id": showroom, "lines": [_line(sofa, 2)]}
        )
    ).json()
    mine = await _get(owner_client, showroom)

    await _second_user(async_client, async_db)
    await _as(async_client, TILL_EMAIL)
    theirs = await _get(async_client, showroom)
    taken = await _fill(async_client, theirs, [_line(sofa, 2)])

    await _relogin_owner(async_client)
    refused = await async_client.post(f"{HELD}/{held['id']}/resume", json=_resume(held, mine))
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["code"] == "stock_reserved"
    assert [sale["id"] for sale in await _list(async_client, showroom)] == [held["id"]]

    await _as(async_client, TILL_EMAIL)
    await _fill(async_client, taken, [])
    await _relogin_owner(async_client)
    resumed = await async_client.post(f"{HELD}/{held['id']}/resume", json=_resume(held, mine))
    assert resumed.status_code == 200, resumed.text
    assert await _reservations(async_db, mine["id"]) == {sofa["id"]: 2}
    assert await _list(async_client, showroom) == []


async def test_hold_current_then_resume_moves_each_side_with_its_basket(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "HR-SWAP-SOFA", showroom, 2)
    chair = await _stocked(owner_client, "HR-SWAP-CHAIR", showroom, 1)
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(chair, 1)])
    first = await _hold(owner_client, showroom, basket, [_line(chair, 1)])
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 2)])
    current = {"id": str(uuid.uuid4()), "location_id": showroom, "lines": [_line(sofa, 2)]}

    request = _resume(first, basket, current=current)
    resumed = await owner_client.post(f"{HELD}/{first['id']}/resume", json=request)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["held_current_id"] == current["id"]
    assert await _reservations(async_db, first["id"]) == {}
    assert await _reservations(async_db, current["id"]) == {sofa["id"]: 2}
    assert await _reservations(async_db, basket["id"]) == {chair["id"]: 1}

    replay = await owner_client.post(f"{HELD}/{first['id']}/resume", json=request)
    assert replay.status_code == 200 and replay.json() == resumed.json()
    assert await _reservations(async_db, current["id"]) == {sofa["id"]: 2}
    assert await _reservations(async_db, basket["id"]) == {chair["id"]: 1}
    assert [sale["id"] for sale in await _list(owner_client, showroom)] == [current["id"]]


async def test_resume_without_a_basket_frees_the_stock(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "HR-NOBASKET", showroom, 2)
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 2)])
    held = await _hold(owner_client, showroom, basket, [_line(sofa, 2)])
    resume = {k: v for k, v in _resume(held, basket).items() if k != "basket_id"}
    assert (await owner_client.post(f"{HELD}/{held['id']}/resume", json=resume)).status_code == 200
    assert await _reservations(async_db, held["id"]) == {}


async def test_delete_releases_reservations_single_and_batch(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "HR-DEL-SOFA", showroom, 1)
    chair = await _stocked(owner_client, "HR-DEL-CHAIR", showroom, 1)
    holds = []
    for sku in (sofa, chair):
        basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sku, 1)])
        holds.append(await _hold(owner_client, showroom, basket, [_line(sku, 1)]))
    for held in holds:
        assert await _reservations(async_db, held["id"])

    one = await owner_client.post(
        f"{HELD}/delete", json={"location_id": showroom, "ids": [holds[0]["id"]]}
    )
    assert one.status_code == 200 and one.json() == {"deleted_count": 1}
    assert await _reservations(async_db, holds[0]["id"]) == {}
    assert await _reservations(async_db, holds[1]["id"]) == {chair["id"]: 1}

    rest = await owner_client.post(
        f"{HELD}/delete", json={"location_id": showroom, "ids": [holds[1]["id"]], "all": True}
    )
    assert rest.status_code == 200 and rest.json() == {"deleted_count": 1}
    assert await _reservations(async_db, holds[1]["id"]) == {}
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 1)])
    assert basket["lines"]


async def test_expired_held_sale_is_hidden_refused_and_deleted_with_its_stock(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "HR-EXPIRE", showroom, 1)
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 1)])
    held = await _hold(owner_client, showroom, basket, [_line(sofa, 1)])
    await _second_user(async_client, async_db)
    await _lapse(async_db, held["id"])

    # Hidden at once, and its stock counts as free before anything is deleted.
    assert await _list(owner_client, showroom) == []
    assert await _held_rows(async_db) == 1
    await _as(async_client, TILL_EMAIL)
    assert (
        await async_client.get("/api/v1/till/reservations", params={"location_id": showroom})
    ).json() == []

    await _relogin_owner(async_client)
    mine = await _get(async_client, showroom)
    expired = await async_client.post(f"{HELD}/{held['id']}/resume", json=_resume(held, mine))
    assert expired.status_code == 409, expired.text
    detail = expired.json()["detail"]
    assert detail["code"] == "held_sale_expired"
    assert detail["message"].startswith("This held sale expired at ")
    assert detail["message"].endswith(".") and len(detail["message"]) == len(
        "This held sale expired at 00:00."
    )
    assert await _held_rows(async_db) == 0
    assert await _reservations(async_db, held["id"]) == {}
    assert (await _get(async_client, showroom))["lines"] == []


async def test_next_till_write_deletes_expired_held_sales_tenant_wide(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "HR-PRUNE", showroom, 1)
    basket = await _fill(owner_client, await _get(owner_client, showroom), [_line(sofa, 1)])
    held = await _hold(owner_client, showroom, basket, [_line(sofa, 1)])
    await _second_user(async_client, async_db)
    await _lapse(async_db, held["id"])
    assert await _held_rows(async_db) == 1

    await _as(async_client, TILL_EMAIL)
    theirs = await _get(async_client, showroom)
    assert (await _fill(async_client, theirs, [_line(sofa, 1)]))["lines"]
    assert await _held_rows(async_db) == 0
    assert await _reservations(async_db, held["id"]) == {}


async def test_list_is_soonest_to_expire_first_and_setting_change_keeps_expiries(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "HR-ORDER-SOFA", showroom, 1)
    chair = await _stocked(owner_client, "HR-ORDER-CHAIR", showroom, 1)
    first, second = [
        await _hold(
            owner_client,
            showroom,
            await _fill(owner_client, await _get(owner_client, showroom), [_line(sku, 1)]),
            [_line(sku, 1)],
        )
        for sku in (sofa, chair)
    ]
    assert [sale["id"] for sale in await _list(owner_client, showroom)] == [
        first["id"],
        second["id"],
    ]

    await async_db.execute(
        update(HeldSale)
        .where(HeldSale.id == uuid.UUID(first["id"]))
        .values(expires_at=_now() + 9 * HOUR)
        .execution_options(synchronize_session=False)
    )
    await async_db.commit()
    assert (
        await owner_client.patch("/api/v1/settings", json={"till_hold_hours": 8})
    ).status_code == 200
    listed = await _list(owner_client, showroom)
    assert [sale["id"] for sale in listed] == [second["id"], first["id"]]
    assert _when(listed[0]["expires_at"]) == _when(second["expires_at"])
    assert _when(listed[1]["expires_at"]) > _now() + 8 * HOUR + datetime.timedelta(minutes=30)
