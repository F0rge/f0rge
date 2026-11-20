"""The till sells from any location through an invoice-linked pick (spec #979, ticket #986)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_reservation import StockReservation
from tests.test_purchase_orders import _location_id_by_name
from tests.test_picks import _on_hand_or_zero as _inventory_on_hand
from tests.test_till_basket import BASKET, SALES, _fill, _get, _line, _put
from tests.test_till_no_stock_required import _inventory_accounts
from tests.test_till_reservations import (
    TILL_EMAIL,
    _as,
    _reservations,
    _second_user,
    _stocked,
)

PICKS = "/api/v1/picks"


async def _move(client: AsyncClient, sku: dict, source: str, target: str, qty: int) -> None:
    created = await client.post(
        "/api/v1/transfers",
        json={
            "from_location_id": source,
            "to_location_id": target,
            "lines": [{"sku_id": sku["id"], "qty": qty}],
        },
    )
    assert created.status_code == 201, created.text
    transfer = created.json()
    dispatched = await client.post(f"/api/v1/transfers/{transfer['id']}/dispatch")
    assert dispatched.status_code == 200, dispatched.text
    received = await client.post(
        f"/api/v1/transfers/{transfer['id']}/receive",
        json={
            "lines": [
                {"line_id": line["id"], "qty_received": line["qty_dispatched"]}
                for line in dispatched.json()["lines"]
            ]
        },
    )
    assert received.status_code == 200, received.text


async def _sell(
    client: AsyncClient, showroom: str, sku: dict, qty: int, *, with_basket: bool = True
) -> dict:
    payload: dict = {
        "location_id": showroom,
        "lines": [{"sku_id": sku["id"], "qty": qty}],
        "tender": "cash",
    }
    if with_basket:
        basket = await _fill(client, await _get(client, showroom), [_line(sku, qty)])
        payload |= {"basket_id": basket["id"], "basket_version": basket["version"]}
    return await client.post(SALES, json=payload)


async def _invoice_reservations(db: AsyncSession, invoice_id: str) -> list[StockReservation]:
    rows = await db.scalars(
        select(StockReservation)
        .where(StockReservation.holder_id == uuid.UUID(invoice_id))
        .execution_options(populate_existing=True)
    )
    return list(rows)


async def _accounts(client: AsyncClient) -> tuple[Decimal, Decimal]:
    return await _inventory_accounts(client)


async def test_warehouse_only_sku_sells_at_a_showroom_till_through_a_draft_pick(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    bench = await _stocked(owner_client, "ANY-WH-ONLY", warehouse, 5)
    inventory_before, cogs_before = await _accounts(owner_client)

    sale = await _sell(owner_client, showroom, bench, 2)
    assert sale.status_code == 201, sale.text
    body = sale.json()
    assert body["lines"][0]["qty"] == 2 and body["pick_id"]

    # Nothing deducted and no cost of sales yet: the units wait for their pick.
    assert await _inventory_on_hand(owner_client, bench["id"], warehouse) == 5
    assert await _accounts(owner_client) == (inventory_before, cogs_before)
    held = await _invoice_reservations(async_db, body["invoice_id"])
    assert [(r.sku_id, r.qty, r.holder_kind, r.expires_at, str(r.location_id)) for r in held] == [
        (uuid.UUID(bench["id"]), 2, "invoice", None, showroom)
    ]

    pick = (await owner_client.get(f"{PICKS}/{body['pick_id']}")).json()
    assert pick["status"] == "draft" and pick["source_type"] == "till"
    assert pick["invoice_id"] == body["invoice_id"] and pick["kit_sku_id"] is None
    (line,) = pick["lines"]
    assert line["sku_id"] == bench["id"] and line["qty_needed"] == 2
    assert [(a["location_id"], a["qty"]) for a in line["allocations"] if a["qty"]] == [
        (warehouse, 2)
    ]

    # The reservation blocks another till, with no expiry.
    await _second_user(async_client, async_db)
    await _as(async_client, TILL_EMAIL)
    theirs = await _get(async_client, showroom)
    blocked = await async_client.put(
        f"{BASKET}/{theirs['id']}", json=_put(theirs, [_line(bench, 4)])
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "stock_reserved" and detail["available"] == 3
    assert detail["blocking"]["holder_kind"] == "invoice"
    assert detail["blocking"]["expires_at"] is None


async def test_partial_line_deducts_here_and_reserves_the_rest(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    sofa = await _stocked(owner_client, "ANY-PARTIAL", warehouse, 6)
    await _move(owner_client, sofa, warehouse, showroom, 1)
    inventory_before, cogs_before = await _accounts(owner_client)

    sale = await _sell(owner_client, showroom, sofa, 3)
    assert sale.status_code == 201, sale.text
    body = sale.json()
    assert await _inventory_on_hand(owner_client, sofa["id"], showroom) == 0
    assert await _inventory_on_hand(owner_client, sofa["id"], warehouse) == 5
    # COGS only for the one unit sold here (cost 40.00).
    assert await _accounts(owner_client) == (inventory_before - 40, cogs_before + 40)
    held = await _invoice_reservations(async_db, body["invoice_id"])
    assert [r.qty for r in held] == [2]
    pick = (await owner_client.get(f"{PICKS}/{body['pick_id']}")).json()
    assert pick["lines"][0]["qty_needed"] == 2
    # The invoice is the full sale.
    assert body["lines"][0]["qty"] == 3


async def test_confirm_deducts_at_the_source_books_cogs_and_clears_the_reservation(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    bench = await _stocked(owner_client, "ANY-CONFIRM", warehouse, 5)
    inventory_before, cogs_before = await _accounts(owner_client)
    body = (await _sell(owner_client, showroom, bench, 2)).json()

    confirmed = await owner_client.post(f"{PICKS}/{body['pick_id']}/confirm", json={})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert await _inventory_on_hand(owner_client, bench["id"], warehouse) == 3
    assert await _accounts(owner_client) == (inventory_before - 80, cogs_before + 80)
    assert await _invoice_reservations(async_db, body["invoice_id"]) == []


async def test_confirm_deducts_at_an_overridden_source(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    sandton = (
        await owner_client.post("/api/v1/locations", json={"name": "Sandton", "type": "warehouse"})
    ).json()["id"]
    bench = await _stocked(owner_client, "ANY-OVERRIDE", warehouse, 5)
    await _move(owner_client, bench, warehouse, sandton, 3)
    body = (await _sell(owner_client, showroom, bench, 2)).json()

    patched = await owner_client.patch(
        f"{PICKS}/{body['pick_id']}",
        json={
            "lines": [{"sku_id": bench["id"], "allocations": [{"location_id": sandton, "qty": 2}]}]
        },
    )
    assert patched.status_code == 200, patched.text
    confirmed = await owner_client.post(f"{PICKS}/{body['pick_id']}/confirm", json={})
    assert confirmed.status_code == 200, confirmed.text
    assert await _inventory_on_hand(owner_client, bench["id"], sandton) == 1
    assert await _inventory_on_hand(owner_client, bench["id"], warehouse) == 2
    assert await _invoice_reservations(async_db, body["invoice_id"]) == []


async def test_confirm_is_refused_when_a_source_is_short_and_posts_nothing(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    other = (
        await owner_client.post("/api/v1/locations", json={"name": "Sandton", "type": "warehouse"})
    ).json()["id"]
    bench = await _stocked(owner_client, "ANY-SHORT", warehouse, 3)
    body = (await _sell(owner_client, showroom, bench, 2)).json()
    # The stock moves away after the sale; the pick still points at the warehouse.
    await _move(owner_client, bench, warehouse, other, 3)
    before = await _accounts(owner_client)

    refused = await owner_client.post(f"{PICKS}/{body['pick_id']}/confirm", json={})
    assert refused.status_code == 409, refused.text
    assert "ANY-SHORT" in refused.json()["detail"] and "Kramerville" in refused.json()["detail"]
    assert await _accounts(owner_client) == before
    assert await _inventory_on_hand(owner_client, bench["id"], other) == 3
    assert [r.qty for r in await _invoice_reservations(async_db, body["invoice_id"])] == [2]
    assert (await owner_client.get(f"{PICKS}/{body['pick_id']}")).json()["status"] == "draft"


async def test_unconfirmed_pick_cannot_be_cancelled_and_keeps_its_reservation(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    bench = await _stocked(owner_client, "ANY-CANCEL", warehouse, 3)
    body = (await _sell(owner_client, showroom, bench, 2)).json()
    cancelled = await owner_client.post(f"{PICKS}/{body['pick_id']}/cancel")
    assert cancelled.status_code == 409, cancelled.text
    assert [r.qty for r in await _invoice_reservations(async_db, body["invoice_id"])] == [2]


async def test_complete_skips_transfers_stages_and_creates_the_delivery(
    owner_client: AsyncClient,
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    bench = await _stocked(owner_client, "ANY-COMPLETE", warehouse, 3)
    body = (await _sell(owner_client, showroom, bench, 2)).json()
    assert (
        await owner_client.post(f"{PICKS}/{body['pick_id']}/confirm", json={})
    ).status_code == 200

    completed = await owner_client.post(f"{PICKS}/{body['pick_id']}/complete", json={})
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "staged"
    transfers = (await owner_client.get("/api/v1/transfers")).json()
    assert [t for t in transfers if t.get("pick_id") == body["pick_id"]] == []
    deliveries = (await owner_client.get("/api/v1/deliveries")).json()["items"]
    assert [d["invoice_id"] for d in deliveries if d["invoice_id"] == body["invoice_id"]] == [
        body["invoice_id"]
    ]


async def test_sale_without_a_basket_still_refuses_to_oversell(owner_client: AsyncClient):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    bench = await _stocked(owner_client, "ANY-NO-BASKET", warehouse, 5)
    refused = await _sell(owner_client, showroom, bench, 2, with_basket=False)
    assert refused.status_code == 409
    assert "Insufficient on-hand quantity" in refused.json()["detail"]
    assert await _inventory_on_hand(owner_client, bench["id"], warehouse) == 5


async def test_showroom_only_sale_has_no_pick(owner_client: AsyncClient, async_db: AsyncSession):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "ANY-HERE", showroom, 3)
    sale = await _sell(owner_client, showroom, sofa, 2)
    assert sale.status_code == 201, sale.text
    assert sale.json()["pick_id"] is None
    assert await _inventory_on_hand(owner_client, sofa["id"], showroom) == 1
    assert await _invoice_reservations(async_db, sale.json()["invoice_id"]) == []
    assert await _reservations(async_db, sale.json()["invoice_id"]) == {}


def _stored(pick: dict) -> list[tuple[str, int]]:
    return [(a["location_id"], a["qty"]) for a in pick["lines"][0]["allocations"] if a["qty"]]


def _defaults(body: dict) -> list[tuple[str, int]]:
    return [(a["location_id"], a["qty"]) for a in body["lines"][0]["allocations"]]


async def test_default_allocations_survive_an_override_and_restore_confirms(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    sandton = (
        await owner_client.post("/api/v1/locations", json={"name": "Sandton", "type": "warehouse"})
    ).json()["id"]
    bench = await _stocked(owner_client, "ANY-DEFAULTS", warehouse, 5)
    await _move(owner_client, bench, warehouse, sandton, 3)
    body = (await _sell(owner_client, showroom, bench, 2)).json()
    url = f"{PICKS}/{body['pick_id']}"

    pick = (await owner_client.get(url)).json()
    defaults = await owner_client.get(f"{url}/default-allocations")
    assert defaults.status_code == 200, defaults.text
    assert defaults.json()["lines"][0]["sku_id"] == bench["id"]
    assert _defaults(defaults.json()) == _stored(pick) == [(warehouse, 2)]
    assert defaults.json()["lines"][0]["allocations"][0]["location_name"] == "Kramerville"

    override = {
        "lines": [{"sku_id": bench["id"], "allocations": [{"location_id": sandton, "qty": 2}]}]
    }
    assert (await owner_client.patch(url, json=override)).status_code == 200
    assert _stored((await owner_client.get(url)).json()) == [(sandton, 2)]
    again = await owner_client.get(f"{url}/default-allocations")
    assert _defaults(again.json()) == [(warehouse, 2)]
    assert _stored((await owner_client.get(url)).json()) == [(sandton, 2)]

    restore = {
        "lines": [{"sku_id": bench["id"], "allocations": [{"location_id": warehouse, "qty": 2}]}]
    }
    assert (await owner_client.patch(url, json=restore)).status_code == 200
    confirmed = await owner_client.post(f"{url}/confirm", json={})
    assert confirmed.status_code == 200, confirmed.text
    assert await _inventory_on_hand(owner_client, bench["id"], warehouse) == 0
    assert await _invoice_reservations(async_db, body["invoice_id"]) == []

    pdf = await owner_client.get(f"{url}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert (await owner_client.get(f"{url}/default-allocations")).status_code == 409


async def test_default_allocations_need_a_session(owner_client: AsyncClient):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    bench = await _stocked(owner_client, "ANY-DEFAULTS-AUTH", warehouse, 3)
    body = (await _sell(owner_client, showroom, bench, 1)).json()
    url = f"{PICKS}/{body['pick_id']}/default-allocations"
    del owner_client.headers["Authorization"]
    assert (await owner_client.get(url)).status_code == 401


async def test_return_is_refused_until_the_off_site_pick_is_confirmed(
    owner_client: AsyncClient, async_db: AsyncSession
):
    from tests.test_stock_returns import _return_payload

    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    bench = await _stocked(owner_client, "ANY-RETURN", warehouse, 5)
    body = (await _sell(owner_client, showroom, bench, 2)).json()
    line_id = body["lines"][0]["id"]
    payload = _return_payload(body["invoice_id"], warehouse, line_id, "restock")

    refused = await owner_client.post("/api/v1/returns", json=payload)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"].startswith("Confirm the pick list for INV-")
    assert refused.json()["detail"].endswith("before processing a return.")
    assert await _inventory_on_hand(owner_client, bench["id"], warehouse) == 5
    held = await _invoice_reservations(async_db, body["invoice_id"])
    assert [(r.sku_id, r.qty) for r in held] == [(uuid.UUID(bench["id"]), 2)]

    confirmed = await owner_client.post(f"{PICKS}/{body['pick_id']}/confirm", json={})
    assert confirmed.status_code == 200, confirmed.text
    created = await owner_client.post("/api/v1/returns", json=payload)
    assert created.status_code == 201, created.text
    completed = await owner_client.post(f"/api/v1/returns/{created.json()['id']}/complete")
    assert completed.status_code == 200, completed.text


async def test_pick_priority_chooses_between_two_off_site_sources(
    owner_client: AsyncClient,
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    kramerville = await _location_id_by_name(owner_client, "Kramerville")
    second = (
        await owner_client.post(
            "/api/v1/locations", json={"name": "Kramerville-warehouse-2", "type": "warehouse"}
        )
    ).json()["id"]
    chair = await _stocked(owner_client, "ANY-PRIORITY", kramerville, 4)
    await _move(owner_client, chair, kramerville, second, 2)

    async def sell_and_source(priority: list[str], prefer_warehouse: bool) -> list[str]:
        patched = await owner_client.patch(
            "/api/v1/settings",
            json={"always_prefer_warehouse": prefer_warehouse, "pick_priority": priority},
        )
        assert patched.status_code == 200, patched.text
        sale = (await _sell(owner_client, showroom, chair, 1)).json()
        pick = (await owner_client.get(f"{PICKS}/{sale['pick_id']}")).json()
        (line,) = pick["lines"]
        return [a["location_id"] for a in line["allocations"] if a["qty"]]

    assert await sell_and_source([second, kramerville], False) == [second]
    assert await sell_and_source([kramerville, second], False) == [kramerville]
    # Both are warehouses, so preferring warehouses keeps the configured order.
    assert await sell_and_source([second, kramerville], True) == [second]
