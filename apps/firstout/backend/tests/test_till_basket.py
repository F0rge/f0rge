"""The open till basket lives on the server, one per user per showroom."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tax_invoice import TaxInvoice
from tests.test_purchase_orders import _create_till, _location_id_by_name, _relogin_owner
from tests.test_sku_bom import _sku
from tests.test_till import _inventory_on_hand

BASKET = "/api/v1/till/basket"
HELD = "/api/v1/till/held-sales"
SALES = "/api/v1/till/sales"


def _line(sku: dict, qty: int = 2, discount: str = "0") -> dict:
    return {"sku_id": sku["id"], "qty": qty, "discount_percent": discount}


def _put(basket: dict, lines: list[dict], **overrides) -> dict:
    return {
        "version": basket["version"],
        "operation_id": str(uuid.uuid4()),
        "linked_pick_ids": {},
        "lines": lines,
        **overrides,
    }


async def _get(client: AsyncClient, location: str) -> dict:
    response = await client.get(BASKET, params={"location_id": location})
    assert response.status_code == 200, response.text
    return response.json()


async def _fill(client: AsyncClient, basket: dict, lines: list[dict], **overrides) -> dict:
    response = await client.put(f"{BASKET}/{basket['id']}", json=_put(basket, lines, **overrides))
    assert response.status_code == 200, response.text
    return response.json()


async def _stocked(client: AsyncClient, ref: str, location: str) -> dict:
    return await _sku(
        client,
        ref,
        opening_location_id=location,
        opening_qty=10,
        opening_cost="40.00",
        retail_ex_vat="100.00",
    )


async def test_get_or_create_is_idempotent_and_per_user(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    first = await _get(owner_client, location)
    assert first["location_id"] == location
    assert first["lines"] == [] and first["version"] == 1
    assert first["customer_id"] is None and first["note"] is None and first["pick_id"] is None
    assert first["linked_pick_ids"] == {}
    assert await _get(owner_client, location) == first

    till = await _create_till(async_client, owner_client)
    await async_db.commit()
    other = await _get(till, location)
    assert other["id"] != first["id"]

    # Another user can neither read nor write someone else's basket.
    response = await till.put(f"{BASKET}/{first['id']}", json=_put(first, []))
    assert response.status_code == 404
    await _relogin_owner(async_client)
    assert (
        await async_client.put(f"{BASKET}/{other['id']}", json=_put(other, []))
    ).status_code == 404


async def test_replace_bumps_version_validates_and_rejects_stale(owner_client: AsyncClient):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "BASKET-SOFA", location)
    basket = await _get(owner_client, location)

    saved = await _fill(
        owner_client, basket, [_line(sofa, 3, "10")], note="  collect Saturday ", customer_id=None
    )
    assert saved["version"] == 2 and saved["note"] == "collect Saturday"
    assert saved["lines"][0]["qty"] == 3 and float(saved["lines"][0]["discount_percent"]) == 10
    assert await _get(owner_client, location) == saved

    stale = await owner_client.put(f"{BASKET}/{basket['id']}", json=_put(basket, []))
    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["code"] == "basket_version_conflict"
    assert detail["basket"]["version"] == 2 and detail["basket"]["lines"][0]["qty"] == 3

    unknown = await owner_client.put(
        f"{BASKET}/{basket['id']}", json=_put(saved, [_line({"id": str(uuid.uuid4())})])
    )
    assert unknown.status_code == 404
    zero = await owner_client.put(f"{BASKET}/{basket['id']}", json=_put(saved, [_line(sofa, 0)]))
    assert zero.status_code == 422
    assert (await _get(owner_client, location))["version"] == 2

    emptied = await _fill(owner_client, saved, [])
    assert emptied["lines"] == [] and emptied["version"] == 3


async def test_retried_operation_returns_current_basket_without_bumping(
    owner_client: AsyncClient,
):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "BASKET-RETRY", location)
    basket = await _get(owner_client, location)
    request = _put(basket, [_line(sofa)])

    first = await owner_client.put(f"{BASKET}/{basket['id']}", json=request)
    retry = await owner_client.put(f"{BASKET}/{basket['id']}", json=request)
    assert first.status_code == 200 and retry.status_code == 200
    assert retry.json() == first.json() and retry.json()["version"] == 2


async def test_sale_from_basket_empties_it_and_mismatch_posts_nothing(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "BASKET-SALE", location)
    basket = await _fill(owner_client, await _get(owner_client, location), [_line(sofa, 2)])
    invoices = await async_db.scalar(select(func.count()).select_from(TaxInvoice))
    body = {
        "location_id": location,
        "lines": [{"sku_id": sofa["id"], "qty": 1}],
        "tender": "cash",
        "basket_id": basket["id"],
        "basket_version": basket["version"],
    }

    mismatch = await owner_client.post(SALES, json=body)
    assert mismatch.status_code == 409
    assert mismatch.json()["detail"]["code"] == "basket_changed"
    assert await async_db.scalar(select(func.count()).select_from(TaxInvoice)) == invoices
    assert await _inventory_on_hand(owner_client, sofa["id"], location) == 10
    assert (await _get(owner_client, location))["lines"] != []

    stale_version = await owner_client.post(
        SALES, json={**body, "lines": [{"sku_id": sofa["id"], "qty": 2}], "basket_version": 1}
    )
    assert stale_version.status_code == 409
    assert stale_version.json()["detail"]["code"] == "basket_changed"

    sale = await owner_client.post(
        SALES, json={**body, "lines": [{"sku_id": sofa["id"], "qty": 2}]}
    )
    assert sale.status_code == 201, sale.text
    assert await _inventory_on_hand(owner_client, sofa["id"], location) == 8
    emptied = await _get(owner_client, location)
    assert emptied["id"] == basket["id"] and emptied["lines"] == []
    assert emptied["version"] == basket["version"] + 1

    # Another user's basket id is not theirs to complete from.
    till = await _create_till(async_client, owner_client)
    await async_db.commit()
    foreign = await till.post(SALES, json={**body, "lines": [{"sku_id": sofa["id"], "qty": 2}]})
    assert foreign.status_code == 404


async def test_sale_without_basket_is_unchanged(owner_client: AsyncClient):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "BASKET-PLAIN", location)
    basket = await _fill(owner_client, await _get(owner_client, location), [_line(sofa, 2)])
    sale = await owner_client.post(
        SALES,
        json={
            "location_id": location,
            "lines": [{"sku_id": sofa["id"], "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201, sale.text
    assert await _get(owner_client, location) == basket


async def test_hold_empties_basket_and_resume_fills_it(owner_client: AsyncClient):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "BASKET-HOLD", location)
    chair = await _stocked(owner_client, "BASKET-CHAIR", location)
    basket = await _fill(
        owner_client, await _get(owner_client, location), [_line(sofa, 2, "5")], note="held note"
    )
    held_body = {
        "id": str(uuid.uuid4()),
        "location_id": location,
        "lines": [_line(sofa, 2, "5")],
        "note": "held note",
        "basket_id": basket["id"],
    }

    wrong = await owner_client.post(
        HELD, json={**held_body, "lines": [_line(sofa, 1, "5")], "id": str(uuid.uuid4())}
    )
    assert wrong.status_code == 409
    assert wrong.json()["detail"]["code"] == "basket_changed"
    assert (await owner_client.get(HELD, params={"location_id": location})).json() == []

    held = await owner_client.post(HELD, json=held_body)
    assert held.status_code == 201, held.text
    after_hold = await _get(owner_client, location)
    assert after_hold["lines"] == [] and after_hold["note"] is None
    assert after_hold["version"] == basket["version"] + 1

    # A retried hold must not wipe a basket the cashier refilled meanwhile.
    refilled = await _fill(owner_client, after_hold, [_line(chair, 1)])
    retry = await owner_client.post(HELD, json=held_body)
    assert retry.status_code == 201 and retry.json()["id"] == held.json()["id"]
    assert await _get(owner_client, location) == refilled

    resume = {
        "operation_id": str(uuid.uuid4()),
        "location_id": location,
        "version": held.json()["version"],
        "basket_id": basket["id"],
        "current": {
            "id": str(uuid.uuid4()),
            "location_id": location,
            "lines": [_line(chair, 1)],
        },
    }
    resumed = await owner_client.post(f"{HELD}/{held.json()['id']}/resume", json=resume)
    assert resumed.status_code == 200, resumed.text
    result = resumed.json()
    assert result["held_current_id"] == resume["current"]["id"]
    assert result["basket"]["id"] == basket["id"]
    assert result["basket"]["note"] == "held note"
    assert [(line["sku_id"], line["qty"]) for line in result["basket"]["lines"]] == [
        (sofa["id"], 2)
    ]
    assert await _get(owner_client, location) == result["basket"]
    replay = await owner_client.post(f"{HELD}/{held.json()['id']}/resume", json=resume)
    assert replay.status_code == 200 and replay.json()["basket"] == result["basket"]
