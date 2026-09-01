"""VAT201 bi-monthly periods: lock snapshot, reopen, live vs frozen."""

from __future__ import annotations

from httpx import AsyncClient

from app.config import settings


async def _create_customer(owner_client: AsyncClient, name: str) -> str:
    resp = await owner_client.post("/api/v1/contacts", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_invoice(
    owner_client: AsyncClient,
    customer_id: str,
    issue_date: str,
    ex_vat: str,
    description: str,
) -> dict:
    resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": issue_date,
            "lines": [{"description": description, "qty": 1, "unit_ex_vat": ex_vat}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_period(owner_client: AsyncClient, period_from: str, period_to: str) -> dict:
    resp = await owner_client.post(
        "/api/v1/vat201/periods",
        json={"period_from": period_from, "period_to": period_to},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login(client: AsyncClient, email: str, password: str) -> None:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def test_lock_freezes_one_period_other_stays_live(owner_client: AsyncClient) -> None:
    customer_id = await _create_customer(owner_client, "VAT201 Period Customer")
    await _create_invoice(owner_client, customer_id, "2026-05-10", "1000.00", "May table")
    await _create_invoice(owner_client, customer_id, "2026-07-10", "2000.00", "July sofa")

    may_jun = await _create_period(owner_client, "2026-05-01", "2026-06-30")
    jul_aug = await _create_period(owner_client, "2026-07-01", "2026-08-31")

    listed = await owner_client.get("/api/v1/vat201/periods")
    assert listed.status_code == 200
    assert {row["id"] for row in listed.json()} == {may_jun["id"], jul_aug["id"]}

    before_lock = await owner_client.get(f"/api/v1/vat201/periods/{jul_aug['id']}")
    assert before_lock.status_code == 200
    assert before_lock.json()["draft"]["standard_rated_supplies_ex_vat"] == "2000.00"

    locked = await owner_client.post(f"/api/v1/vat201/periods/{jul_aug['id']}/lock")
    assert locked.status_code == 200
    assert locked.json()["status"] == "locked"
    assert locked.json()["draft"]["standard_rated_supplies_ex_vat"] == "2000.00"
    locked_output = locked.json()["draft"]["output_tax"]

    second_lock = await owner_client.post(f"/api/v1/vat201/periods/{jul_aug['id']}/lock")
    assert second_lock.status_code == 409

    await _create_invoice(owner_client, customer_id, "2026-07-20", "500.00", "July after lock")
    await _create_invoice(owner_client, customer_id, "2026-05-20", "300.00", "May after lock")

    frozen = await owner_client.get(f"/api/v1/vat201/periods/{jul_aug['id']}")
    assert frozen.status_code == 200
    assert frozen.json()["status"] == "locked"
    assert frozen.json()["draft"]["standard_rated_supplies_ex_vat"] == "2000.00"
    assert frozen.json()["draft"]["output_tax"] == locked_output

    csv_resp = await owner_client.get(f"/api/v1/vat201/periods/{jul_aug['id']}/csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert b"2000.00" in csv_resp.content
    assert b"2500.00" not in csv_resp.content

    pdf_resp = await owner_client.get(f"/api/v1/vat201/periods/{jul_aug['id']}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")

    live_may = await owner_client.get(f"/api/v1/vat201/periods/{may_jun['id']}")
    assert live_may.status_code == 200
    assert live_may.json()["status"] != "locked"
    assert live_may.json()["draft"]["standard_rated_supplies_ex_vat"] == "1300.00"

    reports_live = await owner_client.get(
        "/api/v1/reports/vat201",
        params={"from": "2026-07-01", "to": "2026-08-31"},
    )
    assert reports_live.status_code == 200
    assert reports_live.json()["standard_rated_supplies_ex_vat"] == "2500.00"


async def test_till_and_books_cannot_reopen_owner_can(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    period = await _create_period(owner_client, "2026-01-01", "2026-02-28")
    locked = await owner_client.post(f"/api/v1/vat201/periods/{period['id']}/lock")
    assert locked.status_code == 200

    await _login(async_client, "till@example.com", settings.seed_till_password)
    till_resp = await async_client.post(
        f"/api/v1/vat201/periods/{period['id']}/reopen",
        json={"reason": "till reopen"},
    )
    assert till_resp.status_code == 403

    await _login(async_client, "books@example.com", settings.seed_books_password)
    books_resp = await async_client.post(
        f"/api/v1/vat201/periods/{period['id']}/reopen",
        json={"reason": "books reopen"},
    )
    assert books_resp.status_code == 403

    await _login(async_client, settings.seed_owner_email, settings.seed_owner_password)
    owner_resp = await async_client.post(
        f"/api/v1/vat201/periods/{period['id']}/reopen",
        json={"reason": "correct figures"},
    )
    assert owner_resp.status_code == 200
    assert owner_resp.json()["status"] != "locked"
    assert owner_resp.json()["reopen_reason"] == "correct figures"


async def test_reports_vat201_still_200(owner_client: AsyncClient) -> None:
    resp = await owner_client.get(
        "/api/v1/reports/vat201",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert resp.status_code == 200
    assert "eFiling" in resp.json()["disclaimer"]


async def test_invalid_range_returns_400(owner_client: AsyncClient) -> None:
    one_month = await owner_client.post(
        "/api/v1/vat201/periods",
        json={"period_from": "2026-07-01", "period_to": "2026-07-31"},
    )
    assert one_month.status_code == 400

    mid_month = await owner_client.post(
        "/api/v1/vat201/periods",
        json={"period_from": "2026-07-15", "period_to": "2026-09-14"},
    )
    assert mid_month.status_code == 400

    created = await _create_period(owner_client, "2026-09-01", "2026-10-31")
    duplicate = await owner_client.post(
        "/api/v1/vat201/periods",
        json={"period_from": "2026-09-01", "period_to": "2026-10-31"},
    )
    assert duplicate.status_code == 409
    assert created["period_from"] == "2026-09-01"
