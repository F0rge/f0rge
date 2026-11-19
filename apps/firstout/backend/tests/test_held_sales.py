"""Held till baskets survive beyond a browser and never post a sale."""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journal import JournalEntry
from app.models.payment import Payment
from app.models.tax_invoice import TaxInvoice
from tests.test_purchase_orders import _create_buyer, _create_till, _location_id_by_name
from tests.test_sku_archive_operations import archive_fixture
from tests.test_sku_bom import _sku
from tests.test_till import _inventory_on_hand

HELD = "/api/v1/till/held-sales"


def _basket(location: str, sku: dict, **overrides) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "location_id": location,
        "lines": [{"sku_id": sku["id"], "qty": 2, "discount_percent": "10"}],
        **overrides,
    }


async def _list(client: AsyncClient, location: str) -> list[dict]:
    response = await client.get(HELD, params={"location_id": location})
    assert response.status_code == 200, response.text
    return response.json()


async def _save(client: AsyncClient, basket: dict) -> dict:
    response = await client.post(HELD, json=basket)
    assert response.status_code == 201, response.text
    return response.json()


def _resume(hold: dict, **overrides) -> dict:
    return {
        "operation_id": str(uuid.uuid4()),
        "location_id": hold["location_id"],
        "version": hold["version"],
        **overrides,
    }


async def _financial_counts(db: AsyncSession) -> tuple:
    return tuple(
        [
            await db.scalar(select(func.count()).select_from(model))
            for model in (TaxInvoice, Payment, JournalEntry)
        ]
    )


async def test_holding_preserves_estimates_and_notes_without_posting(
    owner_client: AsyncClient, async_db: AsyncSession
):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _sku(
        owner_client,
        "HOLD-SOFA",
        opening_location_id=location,
        opening_qty=1,
        opening_cost="40.00",
        retail_ex_vat="100.55",
    )
    unpriced = await _sku(owner_client, "HOLD-UNPRICED-SOFA")
    priced_basket = _basket(location, sofa, note="  collect Saturday  ")
    before = await _financial_counts(async_db)

    saved = await _save(owner_client, priced_basket)
    assert saved == await _save(owner_client, priced_basket)
    assert saved["reference"].startswith("HS-") and saved["version"] == 1
    assert saved["note"] == "collect Saturday"
    assert saved["customer_id"] is None and saved["customer_name"] == "Walk-in customer"
    assert saved["held_by_name"]
    assert Decimal(saved["estimated_total_inc_vat"]) == Decimal("208.14")
    assert saved["lines"][0]["sku_code"] == "HOLD-SOFA"
    assert saved["lines"][0]["qty"] == 2 and Decimal(saved["lines"][0]["discount_percent"]) == 10
    unknown = await _save(owner_client, _basket(location, unpriced))
    assert unknown["estimated_total_inc_vat"] is None
    assert unknown["lines"][0]["estimated_total_inc_vat"] is None
    assert [item["id"] for item in await _list(owner_client, location)] == [
        unknown["id"],
        saved["id"],
    ]

    note = {"location_id": location, "version": 1, "note": "Ring on arrival"}
    edit_url = f"{HELD}/{saved['id']}"
    updated = await owner_client.patch(edit_url, json=note)
    assert updated.status_code == 200, updated.text
    assert updated.json()["note"] == "Ring on arrival" and updated.json()["version"] == 2
    assert (await owner_client.patch(edit_url, json=note)).json()["version"] == 2
    stale = await owner_client.patch(edit_url, json={**note, "note": "Different note"})
    assert stale.status_code == 409
    assert await _financial_counts(async_db) == before
    assert await _inventory_on_hand(owner_client, sofa["id"], location) == 1


async def test_resume_and_current_basket_are_atomic_and_actor_idempotent(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _sku(owner_client, "HOLD-RESUME-SOFA", retail_ex_vat="100.00")
    current = await _sku(owner_client, "HOLD-CURRENT-SOFA", retail_ex_vat="200.00")
    target = _basket(location, sofa)
    held = await _save(owner_client, target)
    resume_url = f"{HELD}/{held['id']}/resume"
    candidate = _basket(location, current)
    before = await _financial_counts(async_db)

    stale = await owner_client.post(resume_url, json=_resume(held, version=2, current=candidate))
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "held_resume_target_changed"
    invalid = _basket(location, {"id": str(uuid.uuid4())})
    invalid_swap = await owner_client.post(resume_url, json=_resume(held, current=invalid))
    assert invalid_swap.status_code == 404
    assert [item["id"] for item in await _list(owner_client, location)] == [held["id"]]

    request = _resume(held, current=candidate)
    resumed = await owner_client.post(resume_url, json=request)
    assert resumed.status_code == 200, resumed.text
    result = {"resumed_id": held["id"], "held_current_id": candidate["id"]}
    assert resumed.json() == result
    replay = await owner_client.post(resume_url, json=request)
    assert replay.status_code == 200 and replay.json() == result
    changed_replay = await owner_client.post(resume_url, json={**request, "version": 2})
    assert changed_replay.status_code == 409
    assert (await owner_client.post(HELD, json=target)).status_code == 409

    till = await _create_till(async_client, owner_client)
    await async_db.commit()
    wrong_actor = await till.post(resume_url, json=request)
    assert wrong_actor.status_code == 409
    assert wrong_actor.json()["detail"]["code"] == "held_resume_target_changed"
    assert [item["id"] for item in await _list(till, location)] == [candidate["id"]]
    assert await _financial_counts(async_db) == before


async def test_delete_exact_batch_fails_closed_when_list_changes(
    async_client: AsyncClient, owner_client: AsyncClient
):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    other = await owner_client.post(
        "/api/v1/locations", json={"name": "Held showroom", "type": "showroom"}
    )
    assert other.status_code == 201, other.text
    other_location = other.json()["id"]
    sku = await _sku(owner_client, "HOLD-DELETE-SOFA")
    first_basket = _basket(location, sku)
    first = await _save(owner_client, first_basket)
    first_ids = [first["id"]]
    second = await _save(owner_client, _basket(location, sku))
    other_sale = await _save(owner_client, _basket(other_location, sku))
    invalid = await owner_client.post(
        f"{HELD}/delete", json={"location_id": location, "ids": [*first_ids, other_sale["id"]]}
    )
    assert invalid.status_code == 409
    stale_all = await owner_client.post(
        f"{HELD}/delete", json={"location_id": location, "ids": first_ids, "all": True}
    )
    assert stale_all.status_code == 409
    assert len(await _list(owner_client, location)) == 2
    assert (await owner_client.get(HELD, params={"location_id": warehouse})).status_code == 404
    deleted = await owner_client.post(
        f"{HELD}/delete", json={"location_id": location, "ids": first_ids}
    )
    assert deleted.status_code == 200 and deleted.json() == {"deleted_count": 1}
    assert (await owner_client.post(HELD, json=first_basket)).status_code == 409
    rest = await owner_client.post(
        f"{HELD}/delete", json={"location_id": location, "ids": [second["id"]], "all": True}
    )
    assert rest.status_code == 200 and rest.json() == {"deleted_count": 1}
    assert await _list(owner_client, location) == []
    assert [item["id"] for item in await _list(owner_client, other_location)] == [other_sale["id"]]
    buyer = await _create_buyer(async_client, owner_client)
    assert (await buyer.get(HELD, params={"location_id": location})).status_code == 403
    assert (await buyer.post(HELD, json=_basket(location, sku))).status_code == 403


async def test_resume_preserves_hold_when_sku_is_archived_after_save(
    owner_client: AsyncClient, async_db: AsyncSession
):
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sku = await _sku(owner_client, "HOLD-STALE-SKU")
    held = await _save(owner_client, _basket(location, sku))
    await archive_fixture(async_db, sku["id"])
    response = await owner_client.post(f"{HELD}/{held['id']}/resume", json=_resume(held))
    assert response.status_code == 400
    assert "Restore SKU" in response.text
    assert [row["id"] for row in await _list(owner_client, location)] == [held["id"]]


async def test_exact_unconsumed_archived_kit_commitment_can_be_held_and_resumed(
    owner_client: AsyncClient, async_db: AsyncSession
):
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _location_id_by_name(owner_client, "Kramerville")
    part = await _sku(
        owner_client,
        "HOLD-ARCHIVED-PART",
        opening_location_id=warehouse,
        opening_qty=2,
        opening_cost="40.00",
    )
    kit = await _sku(owner_client, "HOLD-ARCHIVED-KIT", retail_ex_vat="300.00")
    recipe = await owner_client.put(
        f"/api/v1/skus/{kit['id']}/bom",
        json={"lines": [{"component_sku_id": part["id"], "qty": 1}]},
    )
    assert recipe.status_code == 200, recipe.text
    pick = await owner_client.post("/api/v1/picks", json={"sku_id": kit["id"], "qty": 1})
    assert pick.status_code == 201, pick.text
    pick_id = pick.json()["id"]
    confirmed = await owner_client.post(f"/api/v1/picks/{pick_id}/confirm", json={})
    assert confirmed.status_code == 200, confirmed.text
    await archive_fixture(async_db, kit["id"])

    basket = _basket(showroom, kit, pick_id=pick_id, linked_pick_ids={kit["id"]: pick_id})
    assert (await owner_client.post(HELD, json=basket)).status_code == 400
    basket["lines"][0]["qty"] = 1
    held = await _save(owner_client, basket)
    assert held["pick_id"] == pick_id
    assert held["linked_pick_ids"] == {kit["id"]: pick_id}
    response = await owner_client.post(f"{HELD}/{held['id']}/resume", json=_resume(held))
    assert response.status_code == 200, response.text
    assert await _list(owner_client, showroom) == []
    pick = await owner_client.get(f"/api/v1/picks/{pick_id}")
    assert pick.json()["invoice_id"] is None
    assert pick.json()["status"] == "confirmed"
