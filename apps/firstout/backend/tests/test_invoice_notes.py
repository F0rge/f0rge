"""Printed and internal notes on till sales and tax invoices."""

from __future__ import annotations

import uuid
from io import BytesIO

from httpx import AsyncClient
from pypdf import PdfReader

from tests.test_purchase_orders import _create_till, _location_id_by_name, _relogin_owner
from tests.test_till import _ready_showroom_sale
from tests.test_till_basket import BASKET, HELD, _fill, _get, _line, _stocked

PRINTED = "Deliver after 10:00. Call on arrival."
INTERNAL = "Agreed free re-delivery if the Saturday slot is missed."


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


async def test_till_sale_notes_reach_invoice_and_only_printed_note_is_printed(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _ready_showroom_sale(async_client, owner_client, "TILL-NOTES-1")
    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "card",
            "note_printed": f"  {PRINTED} ",
            "note_internal": INTERNAL,
        },
    )
    assert sale.status_code == 201, sale.text
    invoice_id = sale.json()["invoice_id"]

    # The till role reads the invoice but cannot edit its internal note.
    denied = await till.patch(f"/api/v1/invoices/{invoice_id}", json={"note_internal": "x"})
    assert denied.status_code == 403

    await _relogin_owner(owner_client)
    invoice = (await owner_client.get(f"/api/v1/invoices/{invoice_id}")).json()
    assert invoice["note_printed"] == PRINTED
    assert invoice["note_internal"] == INTERNAL

    pdf = await owner_client.get(f"/api/v1/invoices/{invoice_id}/pdf")
    assert pdf.status_code == 200
    text = " ".join(_pdf_text(pdf.content).split())
    assert "Note" in text and PRINTED in text
    assert "Saturday" not in text

    updated = await owner_client.patch(
        f"/api/v1/invoices/{invoice_id}", json={"note_internal": "Customer prefers email."}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["note_internal"] == "Customer prefers email."
    assert updated.json()["note_printed"] == PRINTED

    cleared = await owner_client.patch(
        f"/api/v1/invoices/{invoice_id}", json={"note_internal": " "}
    )
    assert cleared.json()["note_internal"] is None

    # The printed note is part of the issued document and is not editable.
    refused = await owner_client.patch(
        f"/api/v1/invoices/{invoice_id}", json={"note_printed": "changed"}
    )
    assert refused.status_code == 422
    too_long = await owner_client.patch(
        f"/api/v1/invoices/{invoice_id}", json={"note_internal": "x" * 2001}
    )
    assert too_long.status_code == 422


async def test_invoice_without_note_prints_no_note_block(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _ready_showroom_sale(async_client, owner_client, "TILL-NOTES-2")
    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "card",
            "note_internal": INTERNAL,
        },
    )
    assert sale.status_code == 201, sale.text
    await _relogin_owner(owner_client)
    pdf = await owner_client.get(f"/api/v1/invoices/{sale.json()['invoice_id']}/pdf")
    text = _pdf_text(pdf.content)
    assert "Note" not in text and "Saturday" not in text


async def test_basket_and_held_sale_keep_the_notes(owner_client: AsyncClient) -> None:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "NOTES-HOLD", location)
    notes = {"note_printed": PRINTED, "note_internal": INTERNAL}
    basket = await _fill(owner_client, await _get(owner_client, location), [_line(sofa)], **notes)
    assert {key: basket[key] for key in notes} == notes

    held = await owner_client.post(
        HELD,
        json={
            "id": str(uuid.uuid4()),
            "location_id": location,
            "lines": [_line(sofa)],
            "basket_id": basket["id"],
            **notes,
        },
    )
    assert held.status_code == 201, held.text
    assert {key: held.json()[key] for key in notes} == notes
    emptied = await _get(owner_client, location)
    assert emptied["note_printed"] is None and emptied["note_internal"] is None

    resumed = await owner_client.post(
        f"{HELD}/{held.json()['id']}/resume",
        json={
            "operation_id": str(uuid.uuid4()),
            "location_id": location,
            "version": held.json()["version"],
            "basket_id": basket["id"],
        },
    )
    assert resumed.status_code == 200, resumed.text
    assert {key: resumed.json()["basket"][key] for key in notes} == notes
    assert (await owner_client.get(BASKET, params={"location_id": location})).json()[
        "note_printed"
    ] == PRINTED
