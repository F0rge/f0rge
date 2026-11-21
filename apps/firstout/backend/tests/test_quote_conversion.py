"""Quotes edited like the till: replace, delete, price preview, and conversion at the till."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from httpx import AsyncClient

from tests.conftest import authenticate_as
from tests.test_purchase_orders import _location_id_by_name, _relogin_owner
from tests.test_quotes import _named_customer
from tests.test_record_workspace import execute, prepare
from tests.test_till_basket import BASKET, HELD, SALES, _fill, _get, _line, _stocked

QUOTES = "/api/v1/quotes"
WORKSPACE = "/api/v1/record-workspaces/quotes/query"


async def _quote(client: AsyncClient, customer_id: str, sku: dict, **fields) -> dict:
    response = await client.post(
        QUOTES,
        json={"customer_id": customer_id, "lines": [_line(sku, qty=2, discount="10")], **fields},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _staff(client: AsyncClient, name: str) -> dict:
    response = await client.post("/api/v1/sales-staff", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def _workspace(client: AsyncClient, lifecycle: str) -> list[dict]:
    response = await client.post(
        WORKSPACE,
        json={
            "q": "",
            "lifecycle": lifecycle,
            "match": "all",
            "filters": [],
            "limit": 100,
            "offset": 0,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_replace_preview_and_delete_an_open_quote(owner_client: AsyncClient) -> None:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "QC-SOFA", location)
    lamp = await _stocked(owner_client, "QC-LAMP", location)
    customer = await _named_customer(owner_client, "Quote replace")
    thandi = await _staff(owner_client, "Thandi")

    created = await _quote(owner_client, customer, sofa, sales_staff_id=thandi["id"])
    today = datetime.date.today()
    assert created["valid_until"] == (today + datetime.timedelta(days=14)).isoformat()
    assert created["issue_date"] == today.isoformat()
    assert created["sales_staff_id"] == thandi["id"]

    lines = [_line(sofa, qty=3, discount="10"), _line(lamp, qty=1)]
    preview = await owner_client.post(
        f"{QUOTES}/preview",
        json={"customer_id": customer, "quote_id": created["id"], "lines": lines},
    )
    assert preview.status_code == 200, preview.text

    valid_until = (today + datetime.timedelta(days=30)).isoformat()
    replaced = await owner_client.put(
        f"{QUOTES}/{created['id']}",
        json={
            "customer_id": customer,
            "lines": lines,
            "notes": "Delivery in March",
            "internal_note": "  Call before delivery  ",
            "valid_until": valid_until,
        },
    )
    assert replaced.status_code == 200, replaced.text
    body = replaced.json()
    assert [line["qty"] for line in body["lines"]] == [3, 1]
    assert body["notes"] == "Delivery in March"
    assert body["internal_note"] == "Call before delivery"
    assert body["valid_until"] == valid_until
    # PUT replaces the whole quote: the omitted colleague is cleared.
    assert body["sales_staff_id"] is None
    # The preview priced the cart exactly as saving it did.
    assert Decimal(preview.json()["total_inc_vat"]) == Decimal(body["total_inc_vat"])
    assert Decimal(preview.json()["subtotal_ex_vat"]) == Decimal(body["subtotal_ex_vat"])

    # PATCH still changes only what it sends.
    patched = await owner_client.patch(
        f"{QUOTES}/{created['id']}", json={"sales_staff_id": thandi["id"]}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["notes"] == "Delivery in March"
    assert patched.json()["sales_staff_id"] == thandi["id"]

    inactive = await owner_client.patch(
        f"/api/v1/sales-staff/{thandi['id']}", json={"is_active": False}
    )
    assert inactive.status_code == 200
    assert (
        await owner_client.post(
            QUOTES,
            json={
                "customer_id": customer,
                "lines": [_line(sofa)],
                "sales_staff_id": thandi["id"],
            },
        )
    ).status_code == 400

    deleted = await owner_client.delete(f"{QUOTES}/{created['id']}")
    assert deleted.status_code == 204
    assert (await owner_client.get(f"{QUOTES}/{created['id']}")).status_code == 404
    assert (await owner_client.delete(f"{QUOTES}/{created['id']}")).status_code == 404


async def test_quote_editing_needs_the_quotes_permission(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "QC-RBAC", location)
    customer = await _named_customer(owner_client, "Quote RBAC")
    quote = await _quote(owner_client, customer, sofa)

    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    assert (await authenticate_as(async_client, "buyer@example.com")).status_code == 200
    body = {"customer_id": customer, "lines": [_line(sofa)]}
    assert (await async_client.put(f"{QUOTES}/{quote['id']}", json=body)).status_code == 403
    assert (await async_client.delete(f"{QUOTES}/{quote['id']}")).status_code == 403
    assert (await async_client.post(f"{QUOTES}/preview", json=body)).status_code == 403
    assert (await async_client.get("/api/v1/sales-staff/options")).status_code == 403

    # Warehouse quotes without the till, so it lists colleagues for the quote editor.
    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    assert (await authenticate_as(async_client, "warehouse@example.com")).status_code == 200
    assert (await async_client.get("/api/v1/sales-staff/options")).status_code == 200
    await _relogin_owner(owner_client)

    bad = await owner_client.put(f"{QUOTES}/{quote['id']}", json={**body, "lines": []})
    assert bad.status_code == 422
    assert (await owner_client.get(f"{QUOTES}/{quote['id']}")).json()["lines"][0]["qty"] == 2


async def test_till_sale_converts_the_quote_and_locks_it(owner_client: AsyncClient) -> None:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "QC-CONVERT", location)
    customer = await _named_customer(owner_client, "Quote convert")
    quote = await _quote(owner_client, customer, sofa, notes="Printed", internal_note="Staff")

    sale = {
        "location_id": location,
        "customer_id": customer,
        "lines": [_line(sofa, qty=2, discount="10")],
        "tender": "card",
        "quote_id": quote["id"],
    }
    unknown = await owner_client.post(SALES, json={**sale, "quote_id": str(uuid.uuid4())})
    assert unknown.status_code == 404
    assert (await owner_client.get(f"{QUOTES}/{quote['id']}")).json()["status"] == "draft"

    done = await owner_client.post(SALES, json=sale)
    assert done.status_code == 201, done.text
    assert done.json()["quote_number"] == quote["quote_number"]
    invoice_id = done.json()["invoice_id"]

    converted = (await owner_client.get(f"{QUOTES}/{quote['id']}")).json()
    assert converted["status"] == "converted"
    assert converted["converted_invoice_id"] == invoice_id
    assert converted["converted_invoice_number"] == done.json()["invoice_number"]

    # Converted quotes are read-only, cannot be deleted, and sell only once.
    body = {"customer_id": customer, "lines": [_line(sofa)]}
    assert (await owner_client.put(f"{QUOTES}/{quote['id']}", json=body)).status_code == 409
    assert (
        await owner_client.patch(f"{QUOTES}/{quote['id']}", json={"notes": "x"})
    ).status_code == 409
    assert (await owner_client.delete(f"{QUOTES}/{quote['id']}")).status_code == 409
    again = await owner_client.post(SALES, json=sale)
    assert again.status_code == 409, again.text

    # The standard table lists it under Converted, never under Open.
    open_ids = [row["id"] for row in await _workspace(owner_client, "active")]
    converted_rows = await _workspace(owner_client, "archived")
    assert quote["id"] not in open_ids
    row = next(row for row in converted_rows if row["id"] == quote["id"])
    assert row["state"] == "converted" and row["item_count"] == 2


async def test_basket_and_held_sale_keep_the_quote(owner_client: AsyncClient) -> None:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "QC-HOLD", location)
    customer = await _named_customer(owner_client, "Quote hold")
    quote = await _quote(owner_client, customer, sofa)
    linked = {"quote_id": quote["id"], "customer_id": customer}
    basket = await _fill(owner_client, await _get(owner_client, location), [_line(sofa)], **linked)
    assert basket["quote_id"] == quote["id"]

    held = await owner_client.post(
        HELD,
        json={
            "id": str(uuid.uuid4()),
            "location_id": location,
            "lines": [_line(sofa)],
            "basket_id": basket["id"],
            **linked,
        },
    )
    assert held.status_code == 201, held.text
    assert held.json()["quote_id"] == quote["id"]
    assert (await _get(owner_client, location))["quote_id"] is None

    resumed = await owner_client.post(
        f"{HELD}/{held.json()['id']}/resume",
        json={
            "operation_id": str(uuid.uuid4()),
            "location_id": location,
            "version": held.json()["version"],
            "basket_id": basket["id"],
        },
    )
    assert resumed.status_code == 200, resumed.text
    assert (await owner_client.get(BASKET, params={"location_id": location})).json()[
        "quote_id"
    ] == quote["id"]


async def test_workspace_deletes_open_quotes_and_keeps_converted(owner_client: AsyncClient) -> None:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "QC-BULK", location)
    customer = await _named_customer(owner_client, "Quote bulk")
    keep = await _quote(owner_client, customer, sofa)
    drop = await _quote(owner_client, customer, sofa)
    sold = await owner_client.post(
        SALES,
        json={
            "location_id": location,
            "lines": [_line(sofa, qty=2, discount="10")],
            "tender": "cash",
            "quote_id": keep["id"],
        },
    )
    assert sold.status_code == 201, sold.text

    prepared = await prepare(owner_client, "quotes", ids=[keep["id"], drop["id"]], action="delete")
    assert [row["id"] for row in prepared["eligible"]] == [drop["id"]]
    assert prepared["blocked"][0]["id"] == keep["id"]
    result = await execute(owner_client, prepared, "quotes")
    assert result["succeeded"] == [drop["id"]]
    assert (await owner_client.get(f"{QUOTES}/{drop['id']}")).status_code == 404
    assert (await owner_client.get(f"{QUOTES}/{keep['id']}")).status_code == 200
