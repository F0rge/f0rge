"""Staff quote documents — QT numbering, Walk-in customer, Quote PDF labels."""

from __future__ import annotations

from io import BytesIO

from httpx import AsyncClient
from pypdf import PdfReader

from app.config import settings
from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from tests.test_purchase_orders import _location_id_by_name, _relogin_owner
from tests.test_sku_bom import _sku
from tests.test_till import _set_retail_price
from tests.test_transfers import _receive_qty_at_location


async def _walk_in_id(client: AsyncClient) -> str:
    resp = await client.get("/api/v1/customers")
    assert resp.status_code == 200
    row = next(item for item in resp.json() if item["name"] == WALK_IN_CUSTOMER_NAME)
    return row["id"]


async def _named_customer(client: AsyncClient, name: str) -> str:
    resp = await client.post("/api/v1/customers", json={"name": name, "customer_type": "retail"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _priced_sku(owner_client: AsyncClient, our_ref: str) -> str:
    sku = await _sku(owner_client, our_ref, retail_ex_vat="1000.00")
    return sku["id"]


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


async def test_walk_in_quote_numbered_qt(
    owner_client: AsyncClient,
) -> None:
    customer_id = await _walk_in_id(owner_client)
    sku_id = await _priced_sku(owner_client, "QT-WALK")
    created = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": 1}]},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["quote_number"].startswith("QT-")
    assert body["customer_id"] == customer_id
    assert body["customer_name"] == WALK_IN_CUSTOMER_NAME
    assert body["status"] == "draft"


async def test_named_customer_quote_and_pdf_says_quote(
    owner_client: AsyncClient,
) -> None:
    customer_id = await _named_customer(owner_client, "Quote Named")
    sku_id = await _priced_sku(owner_client, "QT-NAMED")
    created = await owner_client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer_id,
            "lines": [{"sku_id": sku_id, "qty": 1, "notes": "Boucle fabric"}],
        },
    )
    assert created.status_code == 201, created.text
    quote_id = created.json()["id"]
    sent = await owner_client.post(f"/api/v1/quotes/{quote_id}/mark-sent")
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"

    pdf = await owner_client.get(f"/api/v1/quotes/{quote_id}/pdf")
    assert pdf.status_code == 200
    text = _pdf_text(pdf.content)
    assert "Quote" in text
    assert "Quote No" in text
    assert "Invoice No" not in text
    assert "Tax Invoice" not in text


async def test_quote_requires_customer(owner_client: AsyncClient) -> None:
    sku_id = await _priced_sku(owner_client, "QT-NOCUST")
    resp = await owner_client.post(
        "/api/v1/quotes",
        json={"lines": [{"sku_id": sku_id, "qty": 1}]},
    )
    assert resp.status_code == 422


async def test_till_can_create_quote_buyer_cannot(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    customer_id = await _walk_in_id(owner_client)
    sku_id = await _priced_sku(owner_client, "QT-RBAC")
    payload = {"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": 1}]}

    async_client.cookies.clear()
    till_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till@example.com", "password": settings.seed_till_password},
    )
    assert till_login.status_code == 200
    till_create = await async_client.post("/api/v1/quotes", json=payload)
    assert till_create.status_code == 201, till_create.text

    async_client.cookies.clear()
    buyer_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer@example.com", "password": settings.seed_buyer_password},
    )
    assert buyer_login.status_code == 200
    buyer_create = await async_client.post("/api/v1/quotes", json=payload)
    assert buyer_create.status_code == 403
    await _relogin_owner(owner_client)


async def test_accept_quote_creates_sales_order(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref="QT-ACCEPT",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "1000.00")
    customer_id = await _named_customer(owner_client, "Quote Accept Customer")
    created = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": 1}]},
    )
    assert created.status_code == 201, created.text
    quote_id = created.json()["id"]
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    accepted = await owner_client.post(
        f"/api/v1/quotes/{quote_id}/accept",
        json={
            "location_id": location_id,
            "hold_stock": True,
            "deposit": {"amount": "575.00", "tender": "eft"},
        },
    )
    assert accepted.status_code == 200, accepted.text
    order = accepted.json()
    assert order["so_number"].startswith("SO-")
    assert order["quote_id"] == quote_id
    assert order["status"] == "open"
    assert order["hold_stock"] is True
    assert order["payments"][0]["tender"] == "eft"

    quote = await owner_client.get(f"/api/v1/quotes/{quote_id}")
    assert quote.json()["status"] == "accepted"

    card = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": 1}]},
    )
    assert card.status_code == 201
    bad = await owner_client.post(
        f"/api/v1/quotes/{card.json()['id']}/accept",
        json={"deposit": {"amount": "10.00", "tender": "card"}},
    )
    assert bad.status_code == 422
