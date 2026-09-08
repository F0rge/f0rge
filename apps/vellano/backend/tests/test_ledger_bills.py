"""S6 supplier bill tests."""

from __future__ import annotations

from httpx import AsyncClient

MINIMAL_PDF = b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


async def _create_supplier(owner_client: AsyncClient) -> str:
    resp = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "Bill Supplier", "default_currency": "USD"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_bill_posts_inventory_and_ap(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client)
    resp = await owner_client.post(
        "/api/v1/bills",
        json={
            "supplier_id": supplier_id,
            "supplier_ref": "FAC-88",
            "issue_date": "2026-09-01",
            "currency": "USD",
            "fx_to_zar": "18.00",
            "lines": [{"description": "Factory invoice", "qty": 1, "unit_amount": "100.00"}],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["bill_number"] == "BILL-0001"
    assert body["amount_foreign"] == "100.00"
    assert body["amount_zar"] == "1800.00"

    accounts = (await owner_client.get("/api/v1/accounts")).json()
    balances = {a["code"]: a["balance_zar"] for a in accounts}
    assert balances["1300"] == "1800.00"
    assert balances["2100"] == "-1800.00"


async def test_bill_attachment_upload_and_download(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client)
    create_resp = await owner_client.post(
        "/api/v1/bills",
        json={
            "supplier_id": supplier_id,
            "supplier_ref": "FAC-99",
            "issue_date": "2026-09-01",
            "currency": "ZAR",
            "lines": [{"description": "Local", "qty": 1, "unit_amount": "50.00"}],
        },
    )
    assert create_resp.status_code == 201
    bill_id = create_resp.json()["id"]

    upload_resp = await owner_client.post(
        f"/api/v1/bills/{bill_id}/attachment",
        files={"file": ("bill.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["pdf_storage_key"] is not None

    download_resp = await owner_client.get(f"/api/v1/bills/{bill_id}/attachment")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    assert download_resp.content == MINIMAL_PDF
    assert "attachment" in download_resp.headers.get("content-disposition", "")
