"""Company logo upload and PDF embedding."""

from __future__ import annotations

from io import BytesIO

from httpx import AsyncClient
from PIL import Image
from pypdf import PdfReader

from app.config import settings
from tests.test_ledger_invoices import _create_customer, _pdf_text


def _tiny_jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (40, 30), color=(120, 80, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


async def test_upload_get_replace_logo(owner_client: AsyncClient) -> None:
    jpeg = _tiny_jpeg()
    first = await owner_client.post(
        "/api/v1/settings/logo",
        files={"logo": ("logo.jpg", jpeg, "image/jpeg")},
    )
    assert first.status_code == 200
    assert first.json()["has_logo"] is True

    logo_get = await owner_client.get("/api/v1/settings/logo")
    assert logo_get.status_code == 200
    assert logo_get.headers["content-type"].startswith("image/jpeg")
    assert len(logo_get.content) > 0

    second = await owner_client.post(
        "/api/v1/settings/logo",
        files={"logo": ("logo2.jpg", jpeg, "image/jpeg")},
    )
    assert second.status_code == 200
    assert second.json()["has_logo"] is True


async def test_books_cannot_upload_logo(async_client: AsyncClient) -> None:
    async_client.cookies.clear()
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books@example.com", "password": settings.seed_books_password},
    )
    assert login.status_code == 200

    resp = await async_client.post(
        "/api/v1/settings/logo",
        files={"logo": ("logo.jpg", _tiny_jpeg(), "image/jpeg")},
    )
    assert resp.status_code == 403


async def test_invoice_pdf_ok_with_and_without_logo(owner_client: AsyncClient) -> None:
    customer_id = await _create_customer(owner_client)
    without = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Table", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert without.status_code == 201
    pdf_without = await owner_client.get(f"/api/v1/invoices/{without.json()['id']}/pdf")
    assert pdf_without.status_code == 200
    assert _pdf_text(pdf_without.content)

    upload = await owner_client.post(
        "/api/v1/settings/logo",
        files={"logo": ("logo.jpg", _tiny_jpeg(), "image/jpeg")},
    )
    assert upload.status_code == 200

    with_logo = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-02",
            "lines": [{"description": "Chair", "qty": 1, "unit_ex_vat": "500.00"}],
        },
    )
    assert with_logo.status_code == 201
    pdf_with = await owner_client.get(f"/api/v1/invoices/{with_logo.json()['id']}/pdf")
    assert pdf_with.status_code == 200
    assert PdfReader(BytesIO(pdf_with.content)).pages
