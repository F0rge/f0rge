"""B6 repeating invoices: monthly schedule, manual run posts INV (#567)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.test_ledger_invoices import _create_customer


async def _create_telephone_schedule(owner_client: AsyncClient, customer_id: str) -> dict:
    resp = await owner_client.post(
        "/api/v1/repeating-invoices",
        json={
            "customer_id": customer_id,
            "name": "Monthly telephone",
            "day_of_month": 15,
            "next_date": "2026-01-15",
            "lines": [{"description": "Telephone", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_run_creates_posted_invoice(owner_client: AsyncClient) -> None:
    customer_id = await _create_customer(owner_client)
    schedule = await _create_telephone_schedule(owner_client, customer_id)

    resp = await owner_client.post(f"/api/v1/repeating-invoices/{schedule['id']}/run")
    assert resp.status_code in (200, 201)
    body = resp.json()
    invoice = body["invoice"]
    assert invoice["invoice_number"].startswith("INV-")
    assert invoice["customer_id"] == customer_id
    assert invoice["lines"][0]["description"] == "Telephone"
    assert invoice["lines"][0]["qty"] == 1
    assert invoice["lines"][0]["unit_ex_vat"] == "100.00"
    assert invoice["subtotal_ex_vat"] == "100.00"

    listed = await owner_client.get("/api/v1/invoices")
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert invoice["id"] in ids


async def test_second_run_advances_next_date(owner_client: AsyncClient) -> None:
    customer_id = await _create_customer(owner_client)
    schedule = await _create_telephone_schedule(owner_client, customer_id)

    first = await owner_client.post(f"/api/v1/repeating-invoices/{schedule['id']}/run")
    assert first.status_code in (200, 201)
    first_next = first.json()["schedule"]["next_date"]
    assert first_next != schedule["next_date"]

    second = await owner_client.post(f"/api/v1/repeating-invoices/{schedule['id']}/run")
    assert second.status_code in (200, 201)
    second_next = second.json()["schedule"]["next_date"]
    assert second_next > first_next
    assert second.json()["invoice"]["invoice_number"].startswith("INV-")
    assert second.json()["invoice"]["id"] != first.json()["invoice"]["id"]


async def test_unauthenticated_repeating_invoices_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/repeating-invoices",
        json={
            "customer_id": "00000000-0000-0000-0000-000000000001",
            "day_of_month": 15,
            "next_date": "2026-01-15",
            "lines": [{"description": "Telephone", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert resp.status_code == 401
