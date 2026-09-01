"""S3 catalogue proformas API tests."""

from __future__ import annotations

from httpx import AsyncClient

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


async def _create_supplier(client: AsyncClient, name: str = "Proforma Supplier") -> str:
    resp = await client.post("/api/v1/suppliers", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_proforma_stores_pdf_and_metadata(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client)

    create_resp = await owner_client.post(
        "/api/v1/proformas",
        data={
            "supplier_id": supplier_id,
            "invoice_number": "INV-1001",
            "invoice_date": "2026-01-15",
            "currency": "usd",
        },
        files={"file": ("invoice.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["supplier_id"] == supplier_id
    assert body["supplier_name"] == "Proforma Supplier"
    assert body["invoice_number"] == "INV-1001"
    assert body["invoice_date"] == "2026-01-15"
    assert body["currency"] == "USD"
    assert body["pdf_storage_key"]

    file_resp = await owner_client.get(f"/api/v1/proformas/{body['id']}/file")
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"].startswith("application/pdf")
    assert file_resp.content == MINIMAL_PDF


async def test_proforma_file_unauthenticated_returns_401(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    supplier_id = await _create_supplier(owner_client, "Auth Supplier")
    create_resp = await owner_client.post(
        "/api/v1/proformas",
        data={
            "supplier_id": supplier_id,
            "invoice_number": "INV-AUTH",
            "invoice_date": "2026-02-01",
        },
        files={"file": ("invoice.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert create_resp.status_code == 201
    proforma_id = create_resp.json()["id"]

    async_client.cookies.clear()
    unauth_resp = await async_client.get(f"/api/v1/proformas/{proforma_id}/file")
    assert unauth_resp.status_code == 401


async def test_list_and_get_proforma(owner_client: AsyncClient) -> None:
    supplier_id = await _create_supplier(owner_client, "List Supplier")
    create_resp = await owner_client.post(
        "/api/v1/proformas",
        data={
            "supplier_id": supplier_id,
            "invoice_number": "INV-LIST",
            "invoice_date": "2026-03-01",
        },
        files={"file": ("invoice.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert create_resp.status_code == 201
    proforma_id = create_resp.json()["id"]

    list_resp = await owner_client.get("/api/v1/proformas")
    assert list_resp.status_code == 200
    ids = {row["id"] for row in list_resp.json()}
    assert proforma_id in ids

    get_resp = await owner_client.get(f"/api/v1/proformas/{proforma_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["invoice_number"] == "INV-LIST"
