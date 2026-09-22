"""Books period lock independent of VAT201."""

from __future__ import annotations

import datetime

from httpx import AsyncClient
from tests.test_purchase_orders import (
    MINIMAL_PDF,
    _create_sku,
    _create_supplier,
    _create_warehouse,
    _location_id_by_name,
    _relogin_owner,
)
from tests.test_transfers import _draft_payload, _receive_qty_at_location
from tests.test_vat201_periods import _create_period as _create_vat201_period


async def _create_named_customer(owner_client: AsyncClient, name: str) -> str:
    resp = await owner_client.post("/api/v1/customers", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_books_period(owner_client: AsyncClient, period_from: str, period_to: str) -> dict:
    resp = await owner_client.post(
        "/api/v1/books-periods",
        json={"period_from": period_from, "period_to": period_to},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _lock_books_period_for_today(owner_client: AsyncClient) -> dict:
    today = datetime.date.today().isoformat()
    period = await _create_books_period(owner_client, today, today)
    locked = await owner_client.post(f"/api/v1/books-periods/{period['id']}/lock")
    assert locked.status_code == 200, locked.text
    return locked.json()


async def _reopen_books_period(owner_client: AsyncClient, period_id: str) -> None:
    reopened = await owner_client.post(
        f"/api/v1/books-periods/{period_id}/reopen",
        json={"reason": "Test reopen"},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "open"


async def _landed_po_ready_to_receive(
    owner_client: AsyncClient,
    our_ref: str = "BOOKS-PO",
) -> tuple[str, str]:
    supplier_id = await _create_supplier(owner_client, f"Books PO Supplier {our_ref}")
    sku = await _create_sku(
        owner_client,
        our_ref,
        f"{our_ref}-BAR",
        f"Books PO {our_ref}",
        "Books Design",
        "Books Fabric",
    )
    po_resp = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "100.00"}],
        },
    )
    assert po_resp.status_code == 201, po_resp.text
    po_id = po_resp.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    land_resp = await owner_client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "18.50",
            "factory_invoice_number": "F",
            "factory_amount": "500.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FR",
            "freight_amount": "100.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CL",
            "clearance_amount": "50.00",
            "clearance_currency": "USD",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert land_resp.status_code == 200, land_resp.text
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    return po_id, location_id


async def test_locked_books_period_blocks_gl_postings(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    customer_id = await _create_named_customer(owner_client, "Books Period Customer")
    period = await _create_books_period(owner_client, "2026-05-01", "2026-05-31")
    locked = await owner_client.post(f"/api/v1/books-periods/{period['id']}/lock")
    assert locked.status_code == 200

    invoice_blocked = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-05-15",
            "lines": [{"description": "Locked month", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert invoice_blocked.status_code == 409

    outside = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-06-01",
            "lines": [{"description": "Open month", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert outside.status_code == 201


async def test_reopen_requires_reason(owner_client: AsyncClient) -> None:
    period = await _create_books_period(owner_client, "2026-07-01", "2026-07-31")
    await owner_client.post(f"/api/v1/books-periods/{period['id']}/lock")

    bad = await owner_client.post(
        f"/api/v1/books-periods/{period['id']}/reopen",
        json={"reason": "   "},
    )
    assert bad.status_code == 400

    ok = await owner_client.post(
        f"/api/v1/books-periods/{period['id']}/reopen",
        json={"reason": "Correcting May accrual"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "open"


async def test_vat201_lock_does_not_block_invoice(
    owner_client: AsyncClient,
) -> None:
    customer_id = await _create_named_customer(owner_client, "VAT201 vs Books")
    vat_period = await _create_vat201_period(owner_client, "2026-03-01", "2026-04-30")
    locked = await owner_client.post(f"/api/v1/vat201/periods/{vat_period['id']}/lock", json={})
    assert locked.status_code == 200

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-03-15",
            "lines": [{"description": "VAT201 locked only", "qty": 1, "unit_ex_vat": "250.00"}],
        },
    )
    assert invoice.status_code == 201


async def test_vat201_lock_books_blocks_invoice(
    owner_client: AsyncClient,
) -> None:
    customer_id = await _create_named_customer(owner_client, "VAT201 lock books")
    vat_period = await _create_vat201_period(owner_client, "2026-04-01", "2026-05-31")
    locked = await owner_client.post(
        f"/api/v1/vat201/periods/{vat_period['id']}/lock",
        json={"lock_books": True},
    )
    assert locked.status_code == 200

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-04-15",
            "lines": [
                {"description": "Books locked via VAT201", "qty": 1, "unit_ex_vat": "100.00"}
            ],
        },
    )
    assert invoice.status_code == 409
    assert invoice.json()["detail"] == "Books period is locked for this date"


async def test_vat201_lock_books_overlap_conflict_leaves_vat201_open(
    owner_client: AsyncClient,
) -> None:
    await _create_books_period(owner_client, "2026-02-01", "2026-03-31")
    vat_period = await _create_vat201_period(owner_client, "2026-03-01", "2026-04-30")

    locked = await owner_client.post(
        f"/api/v1/vat201/periods/{vat_period['id']}/lock",
        json={"lock_books": True},
    )
    assert locked.status_code == 409
    assert locked.json()["detail"] == "Books period overlaps an existing period"

    detail = await owner_client.get(f"/api/v1/vat201/periods/{vat_period['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] != "locked"


async def test_vat201_reopen_leaves_books_locked(
    owner_client: AsyncClient,
) -> None:
    customer_id = await _create_named_customer(owner_client, "VAT201 reopen books")
    vat_period = await _create_vat201_period(owner_client, "2026-06-01", "2026-07-31")
    locked = await owner_client.post(
        f"/api/v1/vat201/periods/{vat_period['id']}/lock",
        json={"lock_books": True},
    )
    assert locked.status_code == 200

    reopened = await owner_client.post(
        f"/api/v1/vat201/periods/{vat_period['id']}/reopen",
        json={"reason": "Adjust VAT figures"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] != "locked"

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-06-15",
            "lines": [{"description": "Books still locked", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert invoice.status_code == 409
    assert invoice.json()["detail"] == "Books period is locked for this date"


async def test_locked_books_period_blocks_po_receive(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    po_id, location_id = await _landed_po_ready_to_receive(owner_client, "BOOKS-RECV")
    period = await _lock_books_period_for_today(owner_client)

    warehouse = await _create_warehouse(async_client, owner_client)
    await _relogin_owner(owner_client)

    blocked = await warehouse.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_id, "location_id": location_id},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Books period is locked for this date"

    await _reopen_books_period(owner_client, period["id"])

    ok = await warehouse.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_id, "location_id": location_id},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "received"


async def test_locked_books_period_blocks_transfer_dispatch(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="BOOKS-XFER-D",
    )
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)
    draft = await warehouse.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], bedford_id, data["sku"]["id"], 1),
    )
    assert draft.status_code == 201, draft.text
    transfer_id = draft.json()["id"]

    await _relogin_owner(owner_client)
    period = await _lock_books_period_for_today(owner_client)

    blocked = await warehouse.post(f"/api/v1/transfers/{transfer_id}/dispatch")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Books period is locked for this date"

    await _reopen_books_period(owner_client, period["id"])

    ok = await warehouse.post(f"/api/v1/transfers/{transfer_id}/dispatch")
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "in_transit"


async def test_locked_books_period_blocks_transfer_receive(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="BOOKS-XFER-R",
    )
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    warehouse = await _create_warehouse(async_client, owner_client)
    draft = await warehouse.post(
        "/api/v1/transfers",
        json=_draft_payload(data["location_id"], bedford_id, data["sku"]["id"], 1),
    )
    assert draft.status_code == 201, draft.text
    transfer_id = draft.json()["id"]

    dispatched = await warehouse.post(f"/api/v1/transfers/{transfer_id}/dispatch")
    assert dispatched.status_code == 200, dispatched.text
    line = dispatched.json()["lines"][0]

    await _relogin_owner(owner_client)
    period = await _lock_books_period_for_today(owner_client)

    blocked = await warehouse.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        json={"lines": [{"line_id": line["id"], "qty_received": line["qty_dispatched"]}]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Books period is locked for this date"

    await _reopen_books_period(owner_client, period["id"])

    ok = await warehouse.post(
        f"/api/v1/transfers/{transfer_id}/receive",
        json={"lines": [{"line_id": line["id"], "qty_received": line["qty_dispatched"]}]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "received"
