"""Unified audit hub."""

from __future__ import annotations

import datetime

from httpx import AsyncClient

from app.config import settings
from app.schemas.audit import AuditEventItem
from app.services.audit_hub import _as_utc
from tests.test_ledger_invoices import _create_customer
from tests.test_purchase_orders import _relogin_owner


def test_as_utc_sorts_mixed_naive_and_aware() -> None:
    naive = datetime.datetime(2026, 9, 1, 12, 0, 0)
    aware = datetime.datetime(2026, 9, 2, 12, 0, 0, tzinfo=datetime.timezone.utc)
    items = [
        AuditEventItem(
            at=_as_utc(naive),
            source="books",
            actor="a",
            summary="books",
            href="/invoices/x",
        ),
        AuditEventItem(
            at=_as_utc(aware),
            source="cost",
            actor="b",
            summary="cost",
            href="/catalogue/y",
        ),
    ]
    items.sort(key=lambda item: item.at, reverse=True)
    assert items[0].source == "cost"
    assert items[1].source == "books"


async def test_invoice_creates_books_audit_row(owner_client: AsyncClient) -> None:
    customer_id = await _create_customer(owner_client)
    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Audit line", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert invoice.status_code == 201
    invoice_id = invoice.json()["id"]

    resp = await owner_client.get("/api/v1/audit/events", params={"limit": 20})
    assert resp.status_code == 200
    body = resp.json()
    books_rows = [row for row in body["items"] if row["source"] == "books"]
    assert any(row["href"] == f"/invoices/{invoice_id}" for row in books_rows)


async def test_till_user_does_not_see_cost_rows(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    locations = (await owner_client.get("/api/v1/locations")).json()
    warehouse_id = next(loc["id"] for loc in locations if loc["name"] == "Kramerville")
    sku_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "AUDIT-COST",
            "our_barcode": "AUDIT-COST-BAR",
            "name": "Audit cost SKU",
            "design": "Audit",
            "fabric": "Fabric",
            "opening_location_id": warehouse_id,
            "opening_qty": 1,
            "opening_unit_cost_zar": "100.00",
        },
    )
    assert sku_resp.status_code == 201
    sku_id = sku_resp.json()["id"]

    corrected = await owner_client.patch(
        f"/api/v1/skus/{sku_id}/unit-cost",
        json={
            "location_id": warehouse_id,
            "unit_cost_zar": "110.00",
            "note": "audit hub test",
        },
    )
    assert corrected.status_code == 200

    async_client.cookies.clear()
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till@example.com", "password": settings.seed_till_password},
    )
    assert login.status_code == 200

    till_view = await async_client.get("/api/v1/audit/events")
    assert till_view.status_code == 200
    assert all(row["source"] != "cost" for row in till_view.json()["items"])

    await _relogin_owner(owner_client)
    customer_id = await _create_customer(owner_client)
    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Audit merge", "qty": 1, "unit_ex_vat": "50.00"}],
        },
    )
    assert invoice.status_code == 201

    owner_view = await owner_client.get("/api/v1/audit/events")
    assert owner_view.status_code == 200
    sources = {row["source"] for row in owner_view.json()["items"]}
    assert "books" in sources
    assert "cost" in sources
