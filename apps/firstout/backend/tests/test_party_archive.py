"""Archives retain history and prevent new business until the account is restored."""

from __future__ import annotations

import datetime
import json
import uuid

import pytest
from sqlalchemy import select

from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.team import Team
from app.models.sales_order import SalesOrder
from app.schemas.sales_order import SalesOrderCreate
from app.services.sales_orders import SalesOrdersService
from f0rge_core.exceptions import ValidationError
from tests.conftest import authenticate_as, create_test_staff, independent_request_sessions
from tests.test_customer_portal_clerk import invitation, personal_headers
from tests.test_customer_portal_clerk import portal_provider as portal_provider
from tests.test_ops_commerce_orders import _paid_order_payload
from tests.test_ops_commerce_orders import ops_headers as ops_headers
from tests.test_quotes import _priced_sku


async def create_party(client, kind: str, *, suffix: str = "", **fields) -> dict:
    response = await client.post(
        f"/api/v1/{kind}", json={"name": f"Archive {kind} {suffix}", **fields}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def archive_party(client, kind: str, party_id: str, archived: bool = True):
    return await client.patch(f"/api/v1/{kind}/{party_id}/archive", json={"is_archived": archived})


@pytest.mark.parametrize("kind", ["customers", "suppliers"])
async def test_archive_restore_lists_counts_and_preserves_detail(owner_client, kind):
    party = await create_party(owner_client, kind)
    assert party["is_archived"] is False
    before = (await owner_client.get(f"/api/v1/{kind}/archive-counts")).json()
    archived = await archive_party(owner_client, kind, party["id"])
    assert archived.status_code == 200, archived.text
    assert archived.json()["is_archived"] is True
    # Repeating the desired state must not move counts twice.
    assert (await archive_party(owner_client, kind, party["id"])).status_code == 200
    active_rows = (await owner_client.get(f"/api/v1/{kind}")).json()
    assert party["id"] not in {row["id"] for row in active_rows}
    archived_rows = (await owner_client.get(f"/api/v1/{kind}?archived=true")).json()
    assert party["id"] in {row["id"] for row in archived_rows}
    detail = await owner_client.get(f"/api/v1/{kind}/{party['id']}")
    assert detail.status_code == 200 and detail.json()["name"] == party["name"]
    assert (await owner_client.get(f"/api/v1/{kind}/archive-counts")).json() == {
        "active": before["active"] - 1,
        "archived": before["archived"] + 1,
    }
    restored = await archive_party(owner_client, kind, party["id"], False)
    assert restored.status_code == 200 and restored.json()["is_archived"] is False
    assert (await owner_client.get(f"/api/v1/{kind}/archive-counts")).json() == before
    assert party["id"] in {row["id"] for row in (await owner_client.get(f"/api/v1/{kind}")).json()}


async def test_archived_customer_filters_and_duplicate_detection(owner_client):
    party = await create_party(
        owner_client, "customers", email="archive-duplicate@example.com", phone="082 123 4567"
    )
    await owner_client.patch(f"/api/v1/customers/{party['id']}", json={"on_hold": True})
    await archive_party(owner_client, "customers", party["id"])
    rows = await owner_client.get("/api/v1/customers?archived=true&on_hold=true&q=archive")
    assert rows.status_code == 200 and [row["id"] for row in rows.json()] == [party["id"]]
    assert (await owner_client.get("/api/v1/customers?archived=true&on_hold=false")).json() == []
    duplicates = await owner_client.get(
        "/api/v1/customers/duplicates", params={"email": "ARCHIVE-DUPLICATE@example.com"}
    )
    assert duplicates.status_code == 200
    assert duplicates.json()[0]["id"] == party["id"]
    assert duplicates.json()[0]["is_archived"] is True


@pytest.mark.parametrize("kind", ["customers", "suppliers"])
async def test_archive_routes_require_authentication(async_client, kind):
    assert (await async_client.get(f"/api/v1/{kind}/archive-counts")).status_code == 401
    assert (await archive_party(async_client, kind, str(uuid.uuid4()))).status_code == 401


@pytest.mark.parametrize("kind", ["customers", "suppliers"])
async def test_warehouse_can_read_archive_but_cannot_mutate(owner_client, kind):
    party = await create_party(owner_client, kind)
    await create_test_staff(owner_client, email="archive-warehouse@example.com", role="warehouse")
    assert (await authenticate_as(owner_client, "archive-warehouse@example.com")).status_code == 200
    assert (await owner_client.get(f"/api/v1/{kind}/archive-counts")).status_code == 200
    assert (await archive_party(owner_client, kind, party["id"])).status_code == 403


@pytest.mark.parametrize("kind,model", [("customers", Customer), ("suppliers", Supplier)])
async def test_foreign_tenant_party_not_found_or_counted(owner_client, async_db, kind, model):
    before = (await owner_client.get(f"/api/v1/{kind}/archive-counts")).json()
    other = Team(name="Archive other organisation", slug="archive-other-org")
    async_db.add(other)
    await async_db.flush()
    foreign = model(team_id=other.id, name="Archive foreign party", is_archived=True)
    async_db.add(foreign)
    await async_db.flush()
    assert (await owner_client.get(f"/api/v1/{kind}/{foreign.id}")).status_code == 404
    assert (await archive_party(owner_client, kind, str(foreign.id), False)).status_code == 404
    assert (await owner_client.get(f"/api/v1/{kind}/archive-counts")).json() == before
    assert str(foreign.id) not in {
        row["id"] for row in (await owner_client.get(f"/api/v1/{kind}?archived=true")).json()
    }
    assert (await async_db.scalar(select(model).where(model.id == foreign.id))).is_archived is True


def invoice_payload(customer_id):
    return {
        "customer_id": customer_id,
        "issue_date": datetime.date.today().isoformat(),
        "lines": [{"description": "Archive history", "qty": 1, "unit_ex_vat": "100"}],
    }


@pytest.mark.parametrize(
    "document", ["invoices", "quotes", "sales-orders", "laybys", "repeating-invoices", "till/sales"]
)
async def test_new_customer_documents_reject_archive(owner_client, async_db, document):
    party = await create_party(owner_client, "customers")
    await archive_party(owner_client, "customers", party["id"])
    line = {"sku_id": str(uuid.uuid4()), "qty": 1}
    payload = {"customer_id": party["id"], "lines": [line]}
    if document == "invoices":
        payload = invoice_payload(party["id"])
    elif document == "repeating-invoices":
        payload = {
            **invoice_payload(party["id"]),
            "day_of_month": 1,
            "next_date": datetime.date.today().isoformat(),
        }
    elif document in ("laybys", "till/sales"):
        locations = (await owner_client.get("/api/v1/locations")).json()
        location = next(row for row in locations if row["type"] == "showroom")
        payload.update(location_id=location["id"], tender="cash")
        if document == "laybys":
            payload.update(
                due_date=datetime.date.today().isoformat(), hold_stock=False, deposit_amount="1"
            )
    if document == "sales-orders":
        # Staff orders originate from quotes; portal draft creation shares this service seam.
        with pytest.raises(ValidationError, match="Restore this customer"):
            await SalesOrdersService(async_db).create_draft(
                SalesOrderCreate.model_validate(payload)
            )
        return
    response = await owner_client.post(f"/api/v1/{document}", json=payload)
    assert response.status_code == 400, response.text
    assert "Restore this customer" in response.text


@pytest.mark.parametrize("document", ["purchase-orders", "bills", "proformas"])
async def test_new_supplier_documents_reject_archive(owner_client, document):
    party = await create_party(owner_client, "suppliers")
    await archive_party(owner_client, "suppliers", party["id"])
    today = datetime.date.today().isoformat()
    if document == "proformas":
        response = await owner_client.post(
            "/api/v1/proformas",
            data={"supplier_id": party["id"], "invoice_number": "archive", "invoice_date": today},
            files={"file": ("archive.pdf", b"%PDF-1.4 synthetic", "application/pdf")},
        )
    else:
        payload = {"supplier_id": party["id"]}
        if document == "bills":
            payload.update(
                supplier_ref="archive",
                issue_date=today,
                currency="ZAR",
                lines=[{"description": "Archive", "qty": 1, "unit_amount": "100"}],
            )
        else:
            payload["lines"] = [{"description": "Archive", "qty": 1, "factory_unit_amount": "100"}]
        response = await owner_client.post(f"/api/v1/{document}", json=payload)
    assert response.status_code == 400, response.text
    assert "Restore this supplier" in response.text


async def test_archived_history_keeps_balances_and_accepts_payment(owner_client):
    party = await create_party(owner_client, "customers")
    invoice = await owner_client.post("/api/v1/invoices", json=invoice_payload(party["id"]))
    assert invoice.status_code == 201, invoice.text
    await archive_party(owner_client, "customers", party["id"])
    historical = await owner_client.get(f"/api/v1/invoices/{invoice.json()['id']}")
    assert historical.status_code == 200 and historical.json()["customer_name"] == party["name"]
    detail = (await owner_client.get(f"/api/v1/customers/{party['id']}")).json()
    assert detail["open_invoices_count"] == 1
    payment = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice.json()["id"],
            "amount": "115",
            "currency": "ZAR",
            "paid_on": datetime.date.today().isoformat(),
        },
    )
    assert payment.status_code == 201, payment.text
    assert (await owner_client.get(f"/api/v1/customers/{party['id']}")).json()[
        "open_invoices_count"
    ] == 0
    await archive_party(owner_client, "customers", party["id"], False)
    assert (
        await owner_client.post("/api/v1/invoices", json=invoice_payload(party["id"]))
    ).status_code == 201


async def test_archive_stops_repeating_occurrence_without_advancing_date(owner_client):
    party = await create_party(owner_client, "customers")
    next_date = datetime.date.today().isoformat()
    schedule = await owner_client.post(
        "/api/v1/repeating-invoices",
        json={**invoice_payload(party["id"]), "day_of_month": 1, "next_date": next_date},
    )
    assert schedule.status_code == 201, schedule.text
    await archive_party(owner_client, "customers", party["id"])
    blocked = await owner_client.post(f"/api/v1/repeating-invoices/{schedule.json()['id']}/run")
    assert blocked.status_code == 400 and "Restore this customer" in blocked.text
    persisted = await owner_client.get(f"/api/v1/repeating-invoices/{schedule.json()['id']}")
    assert persisted.status_code == 200 and persisted.json()["next_date"] == next_date


async def test_archive_blocks_new_portal_invites_but_existing_access_stays_manageable(owner_client):
    party = await create_party(owner_client, "customers", customer_type="trade")
    await archive_party(owner_client, "customers", party["id"])
    blocked = await owner_client.post(
        f"/api/v1/customers/{party['id']}/portal-invitations",
        json={"email": "archive-portal@example.com"},
    )
    assert blocked.status_code == 400 and "Restore this customer" in blocked.text
    assert (
        await owner_client.get(f"/api/v1/customers/{party['id']}/portal-invitations")
    ).status_code == 200


async def test_existing_quote_can_be_accepted_after_archiving_customer(owner_client):
    party = await create_party(owner_client, "customers")
    sku_id = await _priced_sku(owner_client, "ARCHIVE-QUOTE")
    quote = await owner_client.post(
        "/api/v1/quotes", json={"customer_id": party["id"], "lines": [{"sku_id": sku_id, "qty": 1}]}
    )
    assert quote.status_code == 201, quote.text
    await archive_party(owner_client, "customers", party["id"])
    accepted = await owner_client.post(
        f"/api/v1/quotes/{quote.json()['id']}/accept", json={"hold_stock": False}
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["customer_id"] == party["id"]
    assert (await owner_client.get(f"/api/v1/quotes/{quote.json()['id']}/pdf")).status_code == 200


async def test_paid_storefront_handoff_retains_archived_customer(
    owner_client,
    async_db,
    ops_headers,  # noqa: F811 — imported pytest fixture
):
    payload, _sku_id = await _paid_order_payload(owner_client, fixture_tag="archive")
    payload["company_id"] = ops_headers["X-Ops-Company-ID"]
    party = await create_party(owner_client, "customers", email=payload["customer"]["email"])
    await archive_party(owner_client, "customers", party["id"])
    imported = await owner_client.post(
        "/api/v1/ops-commerce/v1/orders", json=payload, headers=ops_headers
    )
    assert imported.status_code == 201, imported.text
    order = await async_db.get(SalesOrder, uuid.UUID(imported.json()["sales_order_id"]))
    assert str(order.customer_id) == party["id"]
    assert (await owner_client.get(f"/api/v1/customers/{party['id']}")).json()[
        "is_archived"
    ] is True


@pytest.mark.parametrize("before_accept", [True, False])
async def test_archived_portal_account_cannot_enroll_or_create_orders(
    owner_client,
    async_db,
    portal_provider,  # noqa: F811 — imported pytest fixture
    before_accept,
):
    async with independent_request_sessions(async_db):
        customer_id, _invite, raw = await invitation(owner_client)
        if before_accept:
            await archive_party(owner_client, "customers", customer_id)
        accepted = await owner_client.post(
            "/api/v1/portal/invitations/accept", headers=personal_headers(), json={"token": raw}
        )
        if before_accept:
            assert accepted.status_code == 400 and "Restore this customer" in accepted.text
            return
        assert accepted.status_code == 201, accepted.text
        await archive_party(owner_client, "customers", customer_id)
        headers = personal_headers(access=accepted.json()["id"])
        placed = await owner_client.post(
            "/api/v1/portal/orders",
            headers=headers,
            json={"lines": [{"sku_id": str(uuid.uuid4()), "qty": 1}]},
        )
        assert placed.status_code == 400 and "Restore this customer" in placed.text
        assert (await owner_client.get("/api/v1/portal/orders", headers=headers)).status_code == 200


async def test_existing_po_can_resolve_sku_with_archived_supplier(owner_client):
    supplier = await create_party(owner_client, "suppliers")
    po = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier["id"],
            "lines": [
                {"description": "Unmatched archive chair", "qty": 1, "factory_unit_amount": "100"}
            ],
        },
    )
    assert po.status_code == 201, po.text
    await archive_party(owner_client, "suppliers", supplier["id"])
    resolved = await owner_client.post(
        f"/api/v1/purchase-orders/{po.json()['id']}/lines/{po.json()['lines'][0]['id']}/sku",
        json={
            "our_ref": "ARCHIVE-PO-SKU",
            "our_barcode": "ARCHIVE-PO-SKU",
            "name": "Archive chair",
            "design": "Archive chair",
            "fabric": "Archive fabric",
        },
    )
    assert resolved.status_code == 200, resolved.text
    sku_id = resolved.json()["lines"][0]["sku_id"]
    sku = await owner_client.get(f"/api/v1/skus/{sku_id}")
    assert sku.status_code == 200 and sku.json()["preferred_supplier_id"] == supplier["id"]
    listed = await owner_client.get("/api/v1/skus?q=ARCHIVE-PO-SKU")
    assert [row["id"] for row in listed.json()] == [sku_id]


async def test_archived_supplier_cannot_be_new_catalogue_assignment_until_restored(owner_client):
    supplier = await create_party(owner_client, "suppliers")
    sku_id = await _priced_sku(owner_client, "ARCHIVE-SUPPLIER-ASSIGN")
    await archive_party(owner_client, "suppliers", supplier["id"])
    blocked = await owner_client.patch(
        f"/api/v1/skus/{sku_id}", json={"preferred_supplier_id": supplier["id"]}
    )
    assert blocked.status_code == 400 and "Restore this supplier" in blocked.text
    assert (await owner_client.get(f"/api/v1/skus/{sku_id}")).json()[
        "preferred_supplier_id"
    ] is None
    await archive_party(owner_client, "suppliers", supplier["id"], False)
    assigned = await owner_client.patch(
        f"/api/v1/skus/{sku_id}", json={"preferred_supplier_id": supplier["id"]}
    )
    assert assigned.status_code == 200
    await archive_party(owner_client, "suppliers", supplier["id"])
    # Existing references can remain in a later edit without becoming new assignments.
    unchanged = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"preferred_supplier_id": supplier["id"], "lead_time_days": 21},
    )
    assert unchanged.status_code == 200


async def test_incoming_invoice_for_existing_po_accepts_archived_supplier(owner_client, async_db):
    from tests.test_document_intake_invoice import (
        INVOICE_PDF,
        INVOICE_JSON,
        _open_order,
        _process_payload,
        _document,
        _usage,
    )
    from app.services.document_intake.service import DocumentIntakeService

    po = await _open_order(owner_client)
    await archive_party(owner_client, "suppliers", po["supplier_id"])
    intake = DocumentIntakeService(async_db)
    new_proforma = await intake.build_proforma_review(_document(INVOICE_JSON), _usage())
    assert new_proforma.supplier.supplier_id is None
    incoming = await intake.build_proforma_review(
        _document(INVOICE_JSON), _usage(), include_archived_suppliers=True
    )
    assert str(incoming.supplier.supplier_id) == po["supplier_id"]
    processed = await owner_client.post(
        "/api/v1/document-intake/invoices/process",
        data={"payload": json.dumps(_process_payload(po))},
        files={"file": ("archive.pdf", INVOICE_PDF, "application/pdf")},
    )
    assert processed.status_code == 200, processed.text
    bill = await owner_client.get(f"/api/v1/bills/{processed.json()['bill_id']}")
    assert bill.status_code == 200 and bill.json()["purchase_order_id"] == po["po_id"]
