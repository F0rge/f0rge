"""Document template: validation, defaults, save, live preview and what prints."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team_settings import TeamSettings

from app.schemas.document_template import DocumentTemplate
from app.services.document_pdf import render_document_pdf, sample_document
from app.services.invoice_pdf import SellerDetails
from tests.conftest import authenticate_as
from tests.pdf_fixture import assert_pdf_openable
from tests.test_ledger_invoices import _create_customer, _pdf_text

URL = "/api/v1/settings/document-template"
PRINTED = "Deliver after 10am please."
INTERNAL = "Customer haggled hard."
SELLER = SellerDetails(
    name="Example Pty Ltd",
    address="1 Test Street",
    vat_number="4000000001",
    vat_percent_label="15.00%",
    bank_name="Example Bank",
    bank_account="000000",
)


def _flat(pdf: bytes) -> str:
    return " ".join(_pdf_text(pdf).split())


async def _invoice(owner_client: AsyncClient, **extra) -> dict:
    resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": await _create_customer(owner_client),
            "issue_date": "2026-09-01",
            "lines": [{"description": "Oak table", "qty": 1, "unit_ex_vat": "1000.00"}],
            "note_printed": PRINTED,
            "note_internal": INTERNAL,
            **extra,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_defaults_when_nothing_saved(owner_client: AsyncClient) -> None:
    resp = await owner_client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_default"] is True
    assert body["template"] == body["defaults"]
    assert body["template"]["wording"]["invoice"]["title"] == "Tax invoice"
    assert [s["key"] for s in body["template"]["sections"]] == [
        "parties",
        "lines",
        "totals",
        "notes",
        "payments",
        "bank",
        "terms",
    ]


async def test_template_validation(owner_client: AsyncClient) -> None:
    base = DocumentTemplate().model_dump(mode="json")
    for bad in (
        {"accent_colour": "blue"},
        {"accent_colour": "#12345"},
        {"logo_height": 200},
        {"font": "comic"},
        {"sections": [{"key": "signature", "visible": True}]},
        {"sections": [{"key": "lines"}, {"key": "lines"}]},
        {"surprise": True},
    ):
        resp = await owner_client.put(URL, json={**base, **bad})
        assert resp.status_code == 422, bad
    blank_title = {
        **base,
        "wording": {**base["wording"], "quote": {"title": " ", "number_label": "No"}},
    }
    assert (await owner_client.put(URL, json=blank_title)).status_code == 422


async def test_save_and_reload(owner_client: AsyncClient) -> None:
    template = DocumentTemplate(
        accent_colour="#0F62FE", sections=[{"key": "terms"}, {"key": "lines", "visible": False}]
    ).model_dump(mode="json")
    saved = await owner_client.put(URL, json=template)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["is_default"] is False
    assert body["template"]["accent_colour"] == "#0f62fe"
    # Sections it did not list come back, visible, after the ones it did.
    keys = [s["key"] for s in body["template"]["sections"]]
    assert keys[:2] == ["terms", "lines"] and len(keys) == 7
    assert (await owner_client.get(URL)).json()["template"] == body["template"]


async def test_permissions(async_client: AsyncClient, owner_client: AsyncClient) -> None:
    template = DocumentTemplate().model_dump(mode="json")
    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    assert (
        await async_client.post(f"{URL}/preview", json={"template": template})
    ).status_code == 401
    assert (await authenticate_as(async_client, "books@example.com")).status_code == 200
    assert (await async_client.get(URL)).status_code == 200
    assert (await async_client.put(URL, json=template)).status_code == 403
    assert (
        await async_client.post(f"{URL}/preview", json={"template": template})
    ).status_code == 403


async def test_preview_without_a_document_uses_sample_data(owner_client: AsyncClient) -> None:
    template = DocumentTemplate().model_dump(mode="json")
    template["wording"]["quote"]["title"] = "Estimate"
    for kind, title in (
        ("invoice", "Tax invoice"),
        ("quote", "Estimate"),
        ("credit_note", "Credit note"),
        ("receipt", "Payment receipt"),
    ):
        resp = await owner_client.post(f"{URL}/preview", json={"template": template, "kind": kind})
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/pdf"
        assert_pdf_openable(resp.content)
        text = _flat(resp.content)
        assert title in text and "Sample Customer" in text, kind
    # The draft was only previewed, never saved.
    assert (await owner_client.get(URL)).json()["is_default"] is True


async def test_preview_on_a_real_invoice(owner_client: AsyncClient) -> None:
    staff = await owner_client.post(
        "/api/v1/sales-staff", json={"name": "Thandiwe Mokoena", "short_name": "Thandi"}
    )
    assert staff.status_code == 201, staff.text
    invoice = await _invoice(owner_client, sales_staff_id=staff.json()["id"])
    template = DocumentTemplate().model_dump(mode="json")
    template["wording"]["invoice"]["terms"] = "Strictly 30 days."
    preview = await owner_client.post(
        f"{URL}/preview", json={"template": template, "kind": "invoice", "sample_id": invoice["id"]}
    )
    assert preview.status_code == 200, preview.text
    text = _flat(preview.content)
    assert invoice["invoice_number"] in text
    assert "Served by Thandi" in text
    assert "Seller" in text and "Buyer" in text
    assert "Paid" in text and "Balance owing" in text
    assert PRINTED in text and "Strictly 30 days." in text
    assert "ON STATEMENT" in text
    assert INTERNAL not in text

    # Hidden sections and the stamp setting are honoured.
    for section in template["sections"]:
        if section["key"] in ("notes", "terms", "payments"):
            section["visible"] = False
    template["paid_stamp"] = False
    hidden = _flat(
        (
            await owner_client.post(
                f"{URL}/preview",
                json={"template": template, "kind": "invoice", "sample_id": invoice["id"]},
            )
        ).content
    )
    assert PRINTED not in hidden and "Strictly 30 days." not in hidden
    assert "Balance owing" not in hidden and "ON STATEMENT" not in hidden
    assert INTERNAL not in hidden

    # An id of another kind is not found through that kind's service.
    wrong = await owner_client.post(
        f"{URL}/preview", json={"template": template, "kind": "quote", "sample_id": invoice["id"]}
    )
    assert wrong.status_code == 404


async def test_saved_template_drives_the_invoice_pdf(owner_client: AsyncClient) -> None:
    template = DocumentTemplate().model_dump(mode="json")
    template["wording"]["invoice"]["title"] = "Invoice of sale"
    template["footer"] = "Registered in South Africa."
    assert (await owner_client.put(URL, json=template)).status_code == 200
    invoice = await _invoice(owner_client)
    pdf = await owner_client.get(f"/api/v1/invoices/{invoice['id']}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    text = _flat(pdf.content)
    assert "Invoice of sale" in text and "Registered in South Africa." in text
    assert PRINTED in text and INTERNAL not in text


async def test_a_bad_stored_template_never_breaks_the_pdf(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    template = DocumentTemplate().model_dump(mode="json")
    template["footer"] = "Registered in South Africa."
    assert (await owner_client.put(URL, json=template)).status_code == 200
    invoice = await _invoice(owner_client)
    settings = (await async_db.execute(select(TeamSettings))).scalar_one()

    async def printed(stored: dict) -> str:
        settings.document_template = stored
        await async_db.flush()
        pdf = await owner_client.get(f"/api/v1/invoices/{invoice['id']}/pdf")
        assert pdf.status_code == 200, pdf.text
        return _flat(pdf.content)

    # A key from another release is ignored; the rest of the saved template still prints.
    assert "Registered in South Africa." in await printed({**template, "watermark": "x"})
    # An invalid value falls back to the defaults.
    text = await printed({**template, "logo_height": 5000})
    assert "Thank you for your business." in text and "Registered in South Africa." not in text
    # Saving stays strict.
    assert (await owner_client.put(URL, json={**template, "watermark": "x"})).status_code == 422


def test_every_layout_option_renders() -> None:
    for kind in ("invoice", "quote", "credit_note", "receipt"):
        for options in (
            {},
            {"logo_position": "left", "font": "serif", "table_header": "lines"},
            {"logo_position": "centre", "font": "mono", "density": "compact"},
            {"table_header": "solid", "accent_colour": "#198038", "columns": {"line_vat": False}},
        ):
            pdf = render_document_pdf(sample_document(kind), DocumentTemplate(**options), SELLER)
            assert_pdf_openable(pdf)
    text = _flat(render_document_pdf(sample_document("quote"), DocumentTemplate(), SELLER))
    assert "Disc." in text and "5.00%" in text and "SOFA-001" in text
    assert "Use QUO-0001 as your payment reference." in text
    hidden = DocumentTemplate(columns={"discount": False, "sku_ref": False})
    text = _flat(render_document_pdf(sample_document("quote"), hidden, SELLER))
    assert "Disc." not in text and "(5.00% discount)" in text and "SOFA-001" not in text
