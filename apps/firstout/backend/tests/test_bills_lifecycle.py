"""Bill due dates, approval before posting and paying, attachments, archiving and KPIs."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bill import Bill, BillAttachment
from app.services.stored_pdf import _content_disposition
from tests.conftest import authenticate_as, create_test_staff
from tests.pdf_fixture import MINIMAL_PDF

TODAY = date.today()
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


async def _supplier(client: AsyncClient, name: str) -> str:
    resp = await client.post("/api/v1/suppliers", json={"name": name, "default_currency": "ZAR"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _bill(client: AsyncClient, supplier_id: str, ref: str, **extra) -> object:
    return await client.post(
        "/api/v1/bills",
        json={
            "supplier_id": supplier_id,
            "supplier_ref": ref,
            "issue_date": TODAY.isoformat(),
            "currency": "ZAR",
            "lines": [{"description": "Fabric", "qty": 2, "unit_amount": "50.00"}],
            **extra,
        },
    )


async def _ap_balance(client: AsyncClient) -> str:
    accounts = (await client.get("/api/v1/accounts")).json()
    return next(account["balance_zar"] for account in accounts if account["code"] == "2100")


async def _pay(client: AsyncClient, bill_id: str) -> object:
    return await client.post(
        "/api/v1/payments",
        json={
            "direction": "out",
            "bill_id": bill_id,
            "amount": "10.00",
            "currency": "ZAR",
            "paid_on": TODAY.isoformat(),
        },
    )


async def _open_bill_ids(client: AsyncClient) -> set[str]:
    resp = await client.get("/api/v1/payments/open-documents", params={"direction": "out"})
    assert resp.status_code == 200
    return {item["document_id"] for item in resp.json()}


async def test_draft_posts_nothing_until_approved_and_cannot_be_paid(
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _supplier(owner_client, "Draft Supplier")
    before = await _ap_balance(owner_client)
    created = await _bill(owner_client, supplier_id, "DRAFT-1", approval_status="draft")
    assert created.status_code == 201
    draft = created.json()
    assert draft["approval_status"] == "draft" and draft["status"] == "draft"
    assert draft["due_date"] == (TODAY + timedelta(days=30)).isoformat()
    assert await _ap_balance(owner_client) == before

    refused = await _pay(owner_client, draft["id"])
    assert refused.status_code == 400 and "Approve this bill" in refused.json()["detail"]
    assert draft["id"] not in await _open_bill_ids(owner_client)

    submitted = await owner_client.post(f"/api/v1/bills/{draft['id']}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "awaiting_approval"
    assert (await _pay(owner_client, draft["id"])).status_code == 400

    approved = await owner_client.post(f"/api/v1/bills/{draft['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"
    assert approved.json()["status"] == "unpaid"
    assert await _ap_balance(owner_client) != before
    again = await owner_client.post(f"/api/v1/bills/{draft['id']}/approve")
    assert again.status_code == 400

    assert draft["id"] in await _open_bill_ids(owner_client)
    assert (await _pay(owner_client, draft["id"])).status_code == 201
    events = await owner_client.get(
        "/api/v1/books-events", params={"document_type": "bill", "document_id": draft["id"]}
    )
    assert sorted(event["action"] for event in events.json()) == ["created", "posted"]


async def test_saved_and_approved_bill_posts_on_create_with_its_due_date(
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _supplier(owner_client, "Approved Supplier")
    before = await _ap_balance(owner_client)
    due = (TODAY + timedelta(days=10)).isoformat()
    created = await _bill(owner_client, supplier_id, "APPROVED-1", due_date=due, notes=" Net 10 ")
    assert created.status_code == 201
    body = created.json()
    assert body["approval_status"] == "approved" and body["due_date"] == due
    assert body["notes"] == "Net 10"
    assert await _ap_balance(owner_client) != before

    early = await _bill(
        owner_client,
        supplier_id,
        "APPROVED-2",
        due_date=(TODAY - timedelta(days=1)).isoformat(),
    )
    assert early.status_code == 422

    overdue = await owner_client.patch(
        f"/api/v1/bills/{body['id']}",
        json={"due_date": TODAY.isoformat(), "notes": ""},
    )
    assert overdue.status_code == 200
    assert overdue.json()["notes"] is None and overdue.json()["due_date"] == TODAY.isoformat()
    cleared = await owner_client.patch(f"/api/v1/bills/{body['id']}", json={"due_date": None})
    assert cleared.status_code == 400


async def test_attachments_upload_list_download_and_remove(owner_client: AsyncClient) -> None:
    supplier_id = await _supplier(owner_client, "Attachment Supplier")
    bill = (await _bill(owner_client, supplier_id, "ATT-1")).json()

    first = await owner_client.post(
        f"/api/v1/bills/{bill['id']}/attachments",
        files={"file": ("invoice.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert first.status_code == 200
    second = await owner_client.post(
        f"/api/v1/bills/{bill['id']}/attachments",
        files={"file": ("delivery note.png", PNG, "image/png")},
    )
    assert second.status_code == 200
    attachments = second.json()["attachments"]
    assert [(item["filename"], item["content_type"]) for item in attachments] == [
        ("invoice.pdf", "application/pdf"),
        ("delivery note.png", "image/png"),
    ]
    assert second.json()["attachment_count"] == 2

    image = await owner_client.get(f"/api/v1/bills/{bill['id']}/attachments/{attachments[1]['id']}")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png" and image.content == PNG

    rejected = await owner_client.post(
        f"/api/v1/bills/{bill['id']}/attachments",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    assert rejected.status_code == 400

    removed = await owner_client.delete(
        f"/api/v1/bills/{bill['id']}/attachments/{attachments[0]['id']}"
    )
    assert removed.status_code == 200
    assert [item["filename"] for item in removed.json()["attachments"]] == ["delivery note.png"]
    gone = await owner_client.get(f"/api/v1/bills/{bill['id']}/attachments/{attachments[0]['id']}")
    assert gone.status_code == 404


async def test_attachment_names_outside_latin_1_download(owner_client: AsyncClient) -> None:
    supplier_id = await _supplier(owner_client, "Unicode Supplier")
    bill = (await _bill(owner_client, supplier_id, "UNI-1")).json()
    uploaded = await owner_client.post(
        f"/api/v1/bills/{bill['id']}/attachments",
        files={"file": ("Invoice – März.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    attachment = uploaded.json()["attachments"][0]

    resp = await owner_client.get(f"/api/v1/bills/{bill['id']}/attachments/{attachment['id']}")
    assert resp.status_code == 200
    assert resp.headers["content-disposition"] == (
        'attachment; filename="Invoice _ M_rz.pdf"; '
        "filename*=UTF-8''Invoice%20%E2%80%93%20M%C3%A4rz.pdf"
    )
    assert _content_disposition('a\r\n"b\x00\\.pdf') == (
        "attachment; filename=\"a_b_.pdf\"; filename*=UTF-8''a%22b%5C.pdf"
    )


async def test_attachment_type_comes_from_the_file_bytes(owner_client: AsyncClient) -> None:
    supplier_id = await _supplier(owner_client, "Magic Supplier")
    bill = (await _bill(owner_client, supplier_id, "MAGIC-1")).json()
    for name, content, declared in (
        ("invoice.pdf", b"<html>not a pdf</html>", "application/pdf"),
        ("photo.png", b"GIF89a" + b"\x00" * 16, "image/png"),
        ("photo.jpg", b"plain text", "image/jpeg"),
    ):
        resp = await owner_client.post(
            f"/api/v1/bills/{bill['id']}/attachments",
            files={"file": (name, content, declared)},
        )
        assert resp.status_code == 400, name

    renamed = await owner_client.post(
        f"/api/v1/bills/{bill['id']}/attachments",
        files={"file": ("scan.pdf", PNG, "application/pdf")},
    )
    assert renamed.status_code == 200
    assert renamed.json()["attachments"][0]["content_type"] == "image/png"


async def test_previous_release_file_shows_as_read_only_attachment(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    supplier_id = await _supplier(owner_client, "Legacy Supplier")
    bill = (await _bill(owner_client, supplier_id, "LEGACY-1")).json()
    uploaded = await owner_client.post(
        f"/api/v1/bills/{bill['id']}/attachments",
        files={"file": ("invoice.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert uploaded.status_code == 200
    # The previous release stored its one file on the bill, with no attachment row.
    row = await async_db.get(BillAttachment, UUID(uploaded.json()["attachments"][0]["id"]))
    key = row.storage_key
    await async_db.execute(delete(BillAttachment).where(BillAttachment.id == row.id))
    await async_db.execute(
        update(Bill).where(Bill.id == UUID(bill["id"])).values(pdf_storage_key=key)
    )
    await async_db.flush()

    detail = (await owner_client.get(f"/api/v1/bills/{bill['id']}")).json()
    assert detail["attachment_count"] == 1
    [legacy] = detail["attachments"]
    assert legacy["read_only"] is True
    assert legacy["filename"] == f"{bill['bill_number']}.pdf"
    assert legacy["content_type"] == "application/pdf"

    download = await owner_client.get(f"/api/v1/bills/{bill['id']}/attachments/{legacy['id']}")
    assert download.status_code == 200 and download.content == MINIMAL_PDF
    removed = await owner_client.delete(f"/api/v1/bills/{bill['id']}/attachments/{legacy['id']}")
    assert removed.status_code == 404

    # New uploads list after it and stay removable.
    added = await owner_client.post(
        f"/api/v1/bills/{bill['id']}/attachments",
        files={"file": ("other.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert [item["read_only"] for item in added.json()["attachments"]] == [True, False]


async def test_archive_hides_bill_from_workspace_payments_and_kpis(
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _supplier(owner_client, "Archive Supplier")
    overdue = (
        await _bill(
            owner_client,
            supplier_id,
            "KPI-OVERDUE",
            issue_date=(TODAY - timedelta(days=40)).isoformat(),
        )
    ).json()
    soon = (
        await _bill(
            owner_client, supplier_id, "KPI-SOON", due_date=(TODAY + timedelta(days=3)).isoformat()
        )
    ).json()
    await _bill(owner_client, supplier_id, "KPI-WAIT", approval_status="awaiting_approval")
    await _bill(owner_client, supplier_id, "KPI-DRAFT", approval_status="draft")
    assert overdue["status"] == "overdue"

    summary = (await owner_client.get("/api/v1/bills/summary")).json()
    assert summary["overdue_count"] == 1 and summary["overdue_zar"] == "100.00"
    assert summary["due_soon_count"] == 1 and summary["due_soon_zar"] == "100.00"
    assert summary["awaiting_approval_count"] == 1 and summary["draft_count"] == 1
    # Approved and awaiting approval are owed; drafts are not yet.
    assert summary["owing_count"] == 3 and summary["owing_zar"] == "300.00"

    query = await owner_client.post(
        "/api/v1/record-workspaces/bills/query",
        json={"filters": [{"field": "status", "operator": "eq", "value": "overdue"}]},
    )
    assert query.status_code == 200
    assert [row["id"] for row in query.json()["items"]] == [overdue["id"]]

    archived = await owner_client.post(f"/api/v1/bills/{overdue['id']}/archive")
    assert archived.status_code == 200 and archived.json()["is_archived"] is True
    assert (await owner_client.post(f"/api/v1/bills/{overdue['id']}/archive")).status_code == 400
    assert overdue["id"] not in await _open_bill_ids(owner_client)
    assert (await _pay(owner_client, overdue["id"])).status_code == 400
    assert (await owner_client.post(f"/api/v1/bills/{overdue['id']}/approve")).status_code == 400
    assert (await owner_client.get("/api/v1/bills/summary")).json()["overdue_count"] == 0

    lifecycle = await owner_client.post(
        "/api/v1/record-workspaces/bills/query", json={"lifecycle": "archived"}
    )
    assert [row["id"] for row in lifecycle.json()["items"]] == [overdue["id"]]
    assert lifecycle.json()["counts"] == {"active": 3, "archived": 1}

    restored = await owner_client.post(f"/api/v1/bills/{overdue['id']}/restore")
    assert restored.status_code == 200 and restored.json()["is_archived"] is False
    assert soon["id"] in await _open_bill_ids(owner_client)


async def test_bill_changes_need_books_permission(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    supplier_id = await _supplier(owner_client, "Permission Supplier")
    draft = (await _bill(owner_client, supplier_id, "PERM-1", approval_status="draft")).json()

    await create_test_staff(owner_client, email="till-bills@example.com", role="till")
    async_client.headers.pop("Authorization", None)
    assert (await authenticate_as(async_client, "till-bills@example.com")).status_code == 200
    assert (await async_client.post(f"/api/v1/bills/{draft['id']}/approve")).status_code == 403
    assert (await async_client.post(f"/api/v1/bills/{draft['id']}/archive")).status_code == 403
    upload = await async_client.post(
        f"/api/v1/bills/{draft['id']}/attachments",
        files={"file": ("bill.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert upload.status_code == 403
    # Reading bills stays open to staff.
    assert (await async_client.get("/api/v1/bills/summary")).status_code == 200


async def test_supplier_invoice_reading_is_gone_and_proforma_reading_stays(
    owner_client: AsyncClient,
) -> None:
    for path in (
        "/api/v1/document-intake/invoices/extract",
        "/api/v1/document-intake/invoices/process",
    ):
        resp = await owner_client.post(
            path, files={"file": ("invoice.pdf", MINIMAL_PDF, "application/pdf")}
        )
        assert resp.status_code == 404
    settings = (await owner_client.get("/api/v1/settings")).json()
    assert "auto_process_exact_supplier_invoices" not in settings
    # The proforma route still exists (validation fails before any model call).
    proforma = await owner_client.post("/api/v1/document-intake/proformas/extract")
    assert proforma.status_code == 422
