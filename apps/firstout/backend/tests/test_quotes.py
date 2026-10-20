"""Staff quote documents — QT numbering, Walk-in customer, Quote PDF labels."""

from __future__ import annotations

from decimal import Decimal
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


async def test_quote_line_price_follows_customer_and_accepts_override(
    owner_client: AsyncClient,
) -> None:
    sku = await _priced_sku(owner_client, "QT-PRICE")
    priced = await owner_client.patch(
        f"/api/v1/skus/{sku}",
        json={"wholesale_ex_vat": "800.00"},
    )
    assert priced.status_code == 200, priced.text

    retail = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Quote Retail", "customer_type": "retail"},
    )
    assert retail.status_code == 201
    trade = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Quote Trade", "customer_type": "trade"},
    )
    assert trade.status_code == 201

    price_list = await owner_client.post("/api/v1/price-lists", json={"name": "Quote decorator"})
    assert price_list.status_code == 201
    price_list_id = price_list.json()["id"]
    listed = await owner_client.put(
        f"/api/v1/price-lists/{price_list_id}/items",
        json={"sku_id": sku, "unit_ex_vat": "900.00"},
    )
    assert listed.status_code == 200, listed.text
    on_list = await owner_client.post(
        "/api/v1/customers",
        json={
            "name": "Quote Trade List",
            "customer_type": "trade",
            "price_list_id": price_list_id,
        },
    )
    assert on_list.status_code == 201

    async def quote_unit(customer_id: str, line: dict) -> Decimal:
        created = await owner_client.post(
            "/api/v1/quotes",
            json={"customer_id": customer_id, "lines": [line]},
        )
        assert created.status_code == 201, created.text
        return Decimal(created.json()["lines"][0]["unit_ex_vat"])

    base_line = {"sku_id": sku, "qty": 1}
    assert await quote_unit(retail.json()["id"], base_line) == Decimal("1000.00")
    assert await quote_unit(trade.json()["id"], base_line) == Decimal("800.00")
    assert await quote_unit(on_list.json()["id"], base_line) == Decimal("900.00")
    assert await quote_unit(
        on_list.json()["id"],
        {**base_line, "unit_ex_vat": "750.50"},
    ) == Decimal("750.50")

    rejected = await owner_client.post(
        "/api/v1/quotes",
        json={
            "customer_id": trade.json()["id"],
            "lines": [{**base_line, "unit_ex_vat": "0"}],
        },
    )
    assert rejected.status_code == 422


async def _login(client: AsyncClient, email: str, password: str) -> None:
    client.cookies.clear()
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text


async def test_only_owner_can_change_quote_unit_price(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    """Unit price overrides are owner-only. Discounts are covered separately."""
    sku_id = await _priced_sku(owner_client, "QT-OWNER")
    customer_id = await _named_customer(owner_client, "Quote Owner Retail")
    line = {"sku_id": sku_id, "qty": 1}

    overridden = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{**line, "unit_ex_vat": "750.00"}]},
    )
    assert overridden.status_code == 201, overridden.text
    quote_id = overridden.json()["id"]
    assert Decimal(overridden.json()["lines"][0]["unit_ex_vat"]) == Decimal("750.00")

    await _login(async_client, "till@example.com", settings.seed_till_password)
    matched = await async_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{**line, "unit_ex_vat": "1000.00"}]},
    )
    assert matched.status_code == 201, matched.text
    assert Decimal(matched.json()["lines"][0]["unit_ex_vat"]) == Decimal("1000.00")

    omitted = await async_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [line]},
    )
    assert omitted.status_code == 201, omitted.text
    assert Decimal(omitted.json()["lines"][0]["unit_ex_vat"]) == Decimal("1000.00")

    denied = await async_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{**line, "unit_ex_vat": "750.00"}]},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Only the owner can change the unit price for QT-OWNER"

    till_edit = await async_client.patch(
        f"/api/v1/quotes/{quote_id}",
        json={"lines": [{**line, "unit_ex_vat": "700.00"}]},
    )
    assert till_edit.status_code == 403
    assert till_edit.json()["detail"] == "Only the owner can change the unit price for QT-OWNER"

    till_keep = await async_client.patch(
        f"/api/v1/quotes/{quote_id}",
        json={"lines": [{**line, "unit_ex_vat": "1000.00"}]},
    )
    assert till_keep.status_code == 200, till_keep.text
    assert Decimal(till_keep.json()["lines"][0]["unit_ex_vat"]) == Decimal("1000.00")

    await _relogin_owner(owner_client)
    owner_edit = await owner_client.patch(
        f"/api/v1/quotes/{quote_id}",
        json={"lines": [{**line, "unit_ex_vat": "700.00"}]},
    )
    assert owner_edit.status_code == 200, owner_edit.text
    assert Decimal(owner_edit.json()["lines"][0]["unit_ex_vat"]) == Decimal("700.00")

    for email, password in (
        ("buyer@example.com", settings.seed_buyer_password),
        ("warehouse@example.com", settings.seed_warehouse_password),
        ("books@example.com", settings.seed_books_password),
    ):
        await _login(async_client, email, password)
        blocked = await async_client.post(
            "/api/v1/quotes",
            json={"customer_id": customer_id, "lines": [{**line, "unit_ex_vat": "1.00"}]},
        )
        assert blocked.status_code == 403
        edit_blocked = await async_client.patch(
            f"/api/v1/quotes/{quote_id}",
            json={"lines": [{**line, "unit_ex_vat": "1.00"}]},
        )
        assert edit_blocked.status_code == 403
    await _relogin_owner(owner_client)


async def _grant_sales_quotes(db, slug: str) -> None:
    from app.crud.role import RoleCRUD
    from app.models.role import RolePermission
    from app.permissions import SALES_QUOTES

    role = await RoleCRUD(db).get_by_slug(slug)
    assert role is not None
    if any(permission.key == SALES_QUOTES for permission in role.permissions):
        return
    role.permissions.append(RolePermission(role_id=role.id, key=SALES_QUOTES))
    await db.flush()
    db.expire_all()


async def test_quote_line_discount_by_role(async_client, owner_client, async_db) -> None:
    """There is no whole-quote discount. The percent is per line and does not change unit price."""
    sku_id = await _priced_sku(owner_client, "QT-DISC")
    customer_id = await _named_customer(owner_client, "Quote Discount Retail")
    line = {"sku_id": sku_id, "qty": 1}

    owner = await owner_client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer_id,
            "lines": [{**line, "unit_ex_vat": "750.00", "discount_percent": "10"}],
        },
    )
    assert owner.status_code == 201, owner.text
    owner_body = owner.json()
    quote_id = owner_body["id"]
    assert Decimal(owner_body["lines"][0]["unit_ex_vat"]) == Decimal("750.00")
    assert Decimal(owner_body["lines"][0]["discount_percent"]) == Decimal("10.00")
    assert Decimal(owner_body["subtotal_ex_vat"]) == Decimal("675.00")
    assert Decimal(owner_body["total_inc_vat"]) == Decimal("776.25")

    await _login(async_client, "till@example.com", settings.seed_till_password)
    till = await async_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{**line, "discount_percent": "10"}]},
    )
    assert till.status_code == 201, till.text
    assert Decimal(till.json()["lines"][0]["unit_ex_vat"]) == Decimal("1000.00")
    assert Decimal(till.json()["lines"][0]["discount_percent"]) == Decimal("10.00")
    assert Decimal(till.json()["subtotal_ex_vat"]) == Decimal("900.00")
    assert Decimal(till.json()["total_inc_vat"]) == Decimal("1035.00")
    till_price = await async_client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer_id,
            "lines": [{**line, "unit_ex_vat": "750.00", "discount_percent": "10"}],
        },
    )
    assert till_price.status_code == 403
    assert till_price.json()["detail"] == "Only the owner can change the unit price for QT-DISC"
    till_edit = await async_client.patch(
        f"/api/v1/quotes/{quote_id}",
        json={"lines": [{**line, "discount_percent": "5"}]},
    )
    assert till_edit.status_code == 200, till_edit.text
    assert Decimal(till_edit.json()["lines"][0]["unit_ex_vat"]) == Decimal("750.00")
    assert Decimal(till_edit.json()["lines"][0]["discount_percent"]) == Decimal("5.00")
    assert Decimal(till_edit.json()["subtotal_ex_vat"]) == Decimal("712.50")

    await _grant_sales_quotes(async_db, "warehouse")
    await _login(async_client, "warehouse@example.com", settings.seed_warehouse_password)
    warehouse = await async_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{**line, "discount_percent": "10"}]},
    )
    assert warehouse.status_code == 201, warehouse.text
    assert Decimal(warehouse.json()["lines"][0]["discount_percent"]) == Decimal("10.00")
    assert Decimal(warehouse.json()["lines"][0]["unit_ex_vat"]) == Decimal("1000.00")
    warehouse_price = await async_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer_id, "lines": [{**line, "unit_ex_vat": "800.00"}]},
    )
    assert warehouse_price.status_code == 403
    assert (
        warehouse_price.json()["detail"] == "Only the owner can change the unit price for QT-DISC"
    )

    for slug, email, password in (
        ("buyer", "buyer@example.com", settings.seed_buyer_password),
        ("books", "books@example.com", settings.seed_books_password),
    ):
        await _grant_sales_quotes(async_db, slug)
        await _login(async_client, email, password)
        denied = await async_client.post(
            "/api/v1/quotes",
            json={"customer_id": customer_id, "lines": [{**line, "discount_percent": "10"}]},
        )
        assert denied.status_code == 403
        assert denied.json()["detail"] == (
            "Only the owner, till, or warehouse can change the discount for QT-DISC"
        )
        plain = await async_client.post(
            "/api/v1/quotes",
            json={"customer_id": customer_id, "lines": [line]},
        )
        assert plain.status_code == 201, plain.text
        assert Decimal(plain.json()["lines"][0]["discount_percent"]) == Decimal("0.00")
        assert Decimal(plain.json()["lines"][0]["unit_ex_vat"]) == Decimal("1000.00")
        wiped = await async_client.patch(
            f"/api/v1/quotes/{quote_id}",
            json={"lines": [{**line, "discount_percent": "0"}]},
        )
        assert wiped.status_code == 403
        assert wiped.json()["detail"] == (
            "Only the owner, till, or warehouse can change the discount for QT-DISC"
        )

    await _relogin_owner(owner_client)
    accepted = await owner_client.post(f"/api/v1/quotes/{quote_id}/accept", json={})
    assert accepted.status_code == 200, accepted.text
    assert Decimal(accepted.json()["lines"][0]["unit_ex_vat"]) == Decimal("712.50")
    assert Decimal(accepted.json()["subtotal_ex_vat"]) == Decimal("712.50")
    stored = await owner_client.get(f"/api/v1/quotes/{quote_id}")
    assert Decimal(stored.json()["lines"][0]["unit_ex_vat"]) == Decimal("750.00")
    assert Decimal(stored.json()["lines"][0]["discount_percent"]) == Decimal("5.00")
