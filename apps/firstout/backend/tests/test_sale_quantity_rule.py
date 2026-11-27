"""The sale quantity rule: a SKU's "sold in multiples of" and "minimum quantity".

Checked per line by Sale line pricing; sales.price_override may break it; a saved line
whose quantity is unchanged is not checked again (ADR 0002's kept-value rule).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_portal_user import CustomerPortalUser
from app.models.sku import Sku
from app.models.sku_bom_line import SkuBomLine
from app.schemas.customer_portal import PortalOrderCreate, PortalOrderLineCreate
from app.schemas.sales_order import SalesOrderCreate, SalesOrderLineCreate
from app.services.customer_portal import CustomerPortalService
from app.services.sale_line_pricing import (
    PricingAuthority,
    SaleLineRequest,
    SaleQuantityRuleError,
    quantity_rule_message,
)
from app.services.sales_orders import SalesOrdersService
from tests.conftest import authenticate_as, create_test_staff
from tests.test_laybys import _layby_payload, _stocked_sku_at_bedford
from tests.test_purchase_orders import _location_id_by_name, _relogin_owner
from tests.test_sale_line_pricing import _authority, _customer, _price, _Saved, _sku
from tests.test_till_basket import HELD, SALES, _fill, _get, _line, _stocked

D = Decimal


def _rule(multiple: int, minimum: int) -> Sku:
    return Sku(name="Oslo dining chair", sell_multiple=multiple, min_sell_qty=minimum)


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("multiple", "minimum", "qty", "message"),
    [
        # Default 1/1: every quantity is fine.
        (1, 1, 1, None),
        (1, 1, 7, None),
        # Multiples.
        (2, 2, 4, None),
        (2, 2, 3, "Oslo dining chair is sold in multiples of 2."),
        (2, 2, 1, "Oslo dining chair is sold in multiples of 2."),
        # Minimum only.
        (1, 4, 4, None),
        (1, 4, 3, "Oslo dining chair has a minimum quantity of 4."),
        # Both: a multiple below the minimum and a non-multiple above it both break it.
        (2, 4, 6, None),
        (2, 4, 2, "Oslo dining chair is sold in multiples of 2, minimum 4."),
        (2, 4, 5, "Oslo dining chair is sold in multiples of 2, minimum 4."),
    ],
)
def test_quantity_rule_message(multiple, minimum, qty, message) -> None:
    assert quantity_rule_message(_rule(multiple, minimum), qty) == message


async def _ruled_sku(db: AsyncSession, multiple: int, minimum: int) -> Sku:
    sku = await _sku(db, "100.00")
    sku.name, sku.sell_multiple, sku.min_sell_qty = "Oslo dining chair", multiple, minimum
    await db.flush()
    return sku


async def test_preview_reports_and_enforcing_refuses_with_the_offending_lines(async_db) -> None:
    sku = await _ruled_sku(async_db, 2, 4)
    fine = await _ruled_sku(async_db, 2, 2)
    customer = await _customer(async_db)
    lines = [SaleLineRequest(sku=sku, qty=3), SaleLineRequest(sku=fine, qty=2)]

    preview = await _price(async_db, customer, lines, _authority(), enforce=False)
    broken, ok = preview.lines
    assert broken.blocked_by == "quantity_rule"
    assert broken.quantity_rule == "Oslo dining chair is sold in multiples of 2, minimum 4."
    # The amounts are still the line's: the rule does not change a price.
    assert broken.ex_vat == D("300.00")
    assert (ok.blocked_by, ok.quantity_rule) == (None, None)

    with pytest.raises(SaleQuantityRuleError) as refused:
        await _price(async_db, customer, lines, _authority())
    assert refused.value.payload == {
        "code": "sale_quantity_rule",
        "message": "Oslo dining chair is sold in multiples of 2, minimum 4.",
        "lines": [
            {
                "sku_id": str(sku.id),
                "our_ref": sku.our_ref,
                "name": "Oslo dining chair",
                "qty": 3,
                "sell_multiple": 2,
                "min_sell_qty": 4,
                "message": "Oslo dining chair is sold in multiples of 2, minimum 4.",
            }
        ],
    }


async def test_price_override_may_break_the_rule_and_still_sees_it(async_db) -> None:
    sku = await _ruled_sku(async_db, 2, 2)
    customer = await _customer(async_db)
    line = SaleLineRequest(sku=sku, qty=1)
    for authority in (_authority(override=True), PricingAuthority.system()):
        priced = await _price(async_db, customer, [line], authority)
        assert priced.lines[0].blocked_by is None
        # The till shows this as a notice: a batch is being broken.
        assert priced.lines[0].quantity_rule == "Oslo dining chair is sold in multiples of 2."
    # A portal order has no authority.
    with pytest.raises(SaleQuantityRuleError):
        await _price(async_db, customer, [line], await PricingAuthority.of(async_db, None))


async def test_a_permission_refusal_comes_before_the_quantity_rule(async_db) -> None:
    sku = await _ruled_sku(async_db, 2, 2)
    customer = await _customer(async_db)
    line = SaleLineRequest(sku=sku, qty=1, discount_percent=D("5"))
    preview = await _price(async_db, customer, [line], _authority(), enforce=False)
    assert preview.lines[0].blocked_by == "till.discount"
    assert preview.lines[0].quantity_rule is not None


async def test_free_text_and_kit_lines(async_db) -> None:
    customer = await _customer(async_db)
    free = SaleLineRequest(sku=None, qty=3, unit_ex_vat=D("10.00"))
    assert (await _price(async_db, customer, [free], _authority())).lines[0].quantity_rule is None

    # A kit line is checked against the kit's own rule; its components' rules do not apply.
    kit = await _ruled_sku(async_db, 1, 1)
    component = await _ruled_sku(async_db, 4, 4)
    async_db.add(SkuBomLine(parent_sku_id=kit.id, component_sku_id=component.id, qty=D(1)))
    await async_db.flush()
    priced = await _price(async_db, customer, [SaleLineRequest(sku=kit, qty=1)], _authority())
    assert priced.lines[0].quantity_rule is None
    kit.sell_multiple = kit.min_sell_qty = 2
    await async_db.flush()
    with pytest.raises(SaleQuantityRuleError):
        await _price(async_db, customer, [SaleLineRequest(sku=kit, qty=1)], _authority())


async def test_a_saved_quantity_is_kept_and_a_changed_one_is_checked(async_db) -> None:
    sku = await _ruled_sku(async_db, 2, 2)
    customer = await _customer(async_db)
    kept = [
        SaleLineRequest(sku=sku, qty=3, saved=_Saved("100.00", "0", qty=3)),
        SaleLineRequest(sku=sku, qty=3, saved_qty=3),
    ]
    for line in kept:
        priced = await _price(async_db, customer, [line], _authority())
        assert (priced.lines[0].blocked_by, priced.lines[0].quantity_rule) == (None, None)
    for line in (
        SaleLineRequest(sku=sku, qty=5, saved=_Saved("100.00", "0", qty=3)),
        # Fewer units is a change too.
        SaleLineRequest(sku=sku, qty=1, saved_qty=3),
    ):
        with pytest.raises(SaleQuantityRuleError):
            await _price(async_db, customer, [line], _authority())


async def test_sales_order_and_trade_portal_refuse_an_off_rule_quantity(async_db) -> None:
    sku = await _ruled_sku(async_db, 2, 2)
    customer = await _customer(async_db)
    customer.customer_type = "trade"
    # The trade portal's only sales-order path: a draft with no staff member.
    with pytest.raises(SaleQuantityRuleError) as orders:
        await SalesOrdersService(async_db).create_draft(
            SalesOrderCreate(
                customer_id=customer.id, lines=[SalesOrderLineCreate(sku_id=sku.id, qty=3)]
            ),
            user_id=None,
        )
    assert orders.value.payload["code"] == "sale_quantity_rule"

    portal_user = CustomerPortalUser(
        customer_id=customer.id, email=f"{uuid.uuid4().hex[:8]}@trade.example", password_hash="x"
    )
    async_db.add(portal_user)
    await async_db.flush()
    portal = CustomerPortalService(async_db)
    with pytest.raises(SaleQuantityRuleError) as refused:
        await portal.place_order(
            portal_user.id,
            PortalOrderCreate(lines=[PortalOrderLineCreate(sku_id=sku.id, qty=1)]),
        )
    assert refused.value.payload["lines"][0]["qty"] == 1
    placed = await portal.place_order(
        portal_user.id, PortalOrderCreate(lines=[PortalOrderLineCreate(sku_id=sku.id, qty=2)])
    )
    assert placed.status == "draft"


# HTTP: every staff sale document, as a seller without sales.price_override.

SELLER = "qty-rule-seller@example.com"
SALE_PREVIEW = "/api/v1/till/price-preview"


async def _as_seller(client: AsyncClient) -> None:
    role = await client.post(
        "/api/v1/roles",
        json={
            "name": "Quantity rule seller",
            "permissions": ["till.sell", "sales.quotes", "sales.laybys", "books.mutate"],
        },
    )
    assert role.status_code == 201, role.text
    await create_test_staff(client, email=SELLER, role=role.json()["slug"])
    client.cookies.clear()
    client.headers.pop("Authorization", None)
    assert (await authenticate_as(client, SELLER)).status_code == 200


async def _set_rule(db: AsyncSession, sku_id: str, multiple: int, minimum: int) -> None:
    sku = await db.get(Sku, uuid.UUID(sku_id))
    assert sku is not None
    sku.sell_multiple, sku.min_sell_qty = multiple, minimum
    await db.flush()


def _assert_refused(response, sku_id: str, qty: int) -> None:
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "sale_quantity_rule"
    assert detail["message"].endswith("is sold in multiples of 2.")
    [line] = detail["lines"]
    assert (line["sku_id"], line["qty"], line["sell_multiple"], line["min_sell_qty"]) == (
        sku_id,
        qty,
        2,
        2,
    )
    assert set(line) == {
        "sku_id",
        "our_ref",
        "name",
        "qty",
        "sell_multiple",
        "min_sell_qty",
        "message",
    }


def _assert_previewed(response) -> None:
    assert response.status_code == 200, response.text
    line = response.json()["lines"][0]
    assert line["blocked_by"] == "quantity_rule"
    assert line["quantity_rule"].endswith("is sold in multiples of 2.")


async def test_every_sale_document_refuses_an_off_rule_quantity_without_override(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(async_client, owner_client, "QR-ALL", qty=4)
    customer = await owner_client.post("/api/v1/customers", json={"name": "Rule customer"})
    customer_id = customer.json()["id"]
    await _set_rule(async_db, sku_id, 2, 2)
    await _as_seller(owner_client)
    seller = owner_client
    cart = {"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": 3}]}
    till_sale = {**cart, "location_id": bedford_id, "tender": "cash"}
    invoice_lines = [{"description": "Chair", "sku_id": sku_id, "qty": 3}]
    invoice = {
        "customer_id": customer_id,
        "issue_date": datetime.date.today().isoformat(),
        "lines": invoice_lines,
    }
    layby = _layby_payload(customer_id, bedford_id, sku_id)
    layby["lines"] = [{"sku_id": sku_id, "qty": 3}]

    _assert_previewed(await seller.post("/api/v1/till/price-preview", json=cart))
    _assert_refused(await seller.post("/api/v1/till/sales", json=till_sale), sku_id, 3)
    _assert_previewed(await seller.post("/api/v1/quotes/preview", json=cart))
    _assert_refused(await seller.post("/api/v1/quotes", json=cart), sku_id, 3)
    _assert_previewed(await seller.post("/api/v1/laybys/preview", json=cart))
    _assert_refused(await seller.post("/api/v1/laybys", json=layby), sku_id, 3)
    preview = {"customer_id": customer_id, "lines": invoice_lines}
    _assert_previewed(await seller.post("/api/v1/invoices/preview", json=preview))
    _assert_refused(await seller.post("/api/v1/invoices", json=invoice), sku_id, 3)

    # A valid batch goes through.
    allowed = {"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": 4}]}
    assert (await seller.post("/api/v1/quotes", json=allowed)).status_code == 201

    # sales.price_override (the owner preset) may sell one chair from a pair.
    await _relogin_owner(owner_client)
    single = {**till_sale, "lines": [{"sku_id": sku_id, "qty": 1}]}
    shown = await owner_client.post("/api/v1/till/price-preview", json=single)
    assert shown.status_code == 200, shown.text
    line = shown.json()["lines"][0]
    assert line["blocked_by"] is None
    assert line["quantity_rule"].endswith("is sold in multiples of 2.")
    sold = await owner_client.post("/api/v1/till/sales", json=single)
    assert sold.status_code == 201, sold.text


async def test_documents_saved_before_the_rule_tightened_can_still_be_finished(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    sku_id, bedford_id = await _stocked_sku_at_bedford(async_client, owner_client, "QR-OLD", qty=4)
    customer = await owner_client.post("/api/v1/customers", json={"name": "Saved customer"})
    customer_id = customer.json()["id"]
    await _as_seller(owner_client)
    seller = owner_client
    line = {"sku_id": sku_id, "qty": 3}
    quote = await seller.post("/api/v1/quotes", json={"customer_id": customer_id, "lines": [line]})
    assert quote.status_code == 201, quote.text
    layby = _layby_payload(customer_id, bedford_id, sku_id, deposit="500.00")
    layby["lines"] = [line]
    created = await seller.post("/api/v1/laybys", json=layby)
    assert created.status_code == 201, created.text

    await _set_rule(async_db, sku_id, 2, 2)

    # The unchanged quote line saves again; a changed quantity is checked.
    quote_path = f"/api/v1/quotes/{quote.json()['id']}"
    kept = await seller.put(
        quote_path,
        json={"customer_id": customer_id, "lines": [line], "notes": "Saved again"},
    )
    assert kept.status_code == 200, kept.text
    grown = await seller.patch(quote_path, json={"lines": [{**line, "qty": 5}]})
    _assert_refused(grown, sku_id, 5)
    # Accepting copies the saved lines into a sales order without re-pricing them.
    accepted = await seller.post(f"{quote_path}/accept", json={})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["lines"][0]["qty"] == 3

    # The layby is paid up and completed with its saved quantity.
    layby_id = created.json()["id"]
    balance = created.json()["balance"]
    paid = await seller.post(
        f"/api/v1/laybys/{layby_id}/payments", json={"amount": balance, "tender": "card"}
    )
    assert paid.status_code == 201, paid.text
    completed = await seller.post(f"/api/v1/laybys/{layby_id}/complete")
    assert completed.status_code == 200, completed.text
    await _relogin_owner(owner_client)


async def test_repeating_invoices_run_their_stored_free_text_lines(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    """A schedule stores no SKU on its lines, so a rule tightened later never stops a run."""
    sku_id, _ = await _stocked_sku_at_bedford(async_client, owner_client, "QR-REPEAT")
    await _relogin_owner(owner_client)
    customer = await owner_client.post("/api/v1/customers", json={"name": "Monthly customer"})
    schedule = await owner_client.post(
        "/api/v1/repeating-invoices",
        json={
            "customer_id": customer.json()["id"],
            "day_of_month": 1,
            "next_date": datetime.date.today().isoformat(),
            "lines": [
                {"description": "Chair hire", "sku_id": sku_id, "qty": 3, "unit_ex_vat": "50"}
            ],
        },
    )
    assert schedule.status_code == 201, schedule.text
    await _set_rule(async_db, sku_id, 2, 2)
    run = await owner_client.post(f"/api/v1/repeating-invoices/{schedule.json()['id']}/run")
    assert run.status_code == 201, run.text
    assert run.json()["invoice"]["lines"][0]["qty"] == 3


async def test_portal_catalogue_carries_the_selling_rule(async_db) -> None:
    pair = await _ruled_sku(async_db, 2, 4)
    single = await _sku(async_db, "100.00")
    customer = await _customer(async_db)
    customer.customer_type = "trade"
    portal_user = CustomerPortalUser(
        customer_id=customer.id, email=f"{uuid.uuid4().hex[:8]}@trade.example", password_hash="x"
    )
    async_db.add(portal_user)
    await async_db.flush()
    items = {
        item.id: item for item in await CustomerPortalService(async_db).catalogue(portal_user.id)
    }
    assert (items[pair.id].sell_multiple, items[pair.id].min_sell_qty) == (2, 4)
    assert (items[single.id].sell_multiple, items[single.id].min_sell_qty) == (1, 1)


# The till honours quantities saved on a quote or a held sale (SPEC 5.3).


async def _till_setup(owner_client: AsyncClient, ref: str) -> tuple[str, dict, dict, str]:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    kept = await _stocked(owner_client, f"{ref}-A", location)
    added = await _stocked(owner_client, f"{ref}-B", location)
    customer = await owner_client.post("/api/v1/customers", json={"name": f"{ref} customer"})
    return location, kept, added, customer.json()["id"]


async def test_till_keeps_a_saved_quotes_quantity_after_the_rule_tightens(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    location, chair, other, customer = await _till_setup(owner_client, "QR-TQ")
    # Saved by the owner with a discount, while any quantity was fine.
    quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer, "lines": [_line(chair, qty=3, discount="10")]},
    )
    assert quote.status_code == 201, quote.text
    await _set_rule(async_db, chair["id"], 2, 2)
    await _set_rule(async_db, other["id"], 2, 2)
    await _as_seller(owner_client)
    seller = owner_client
    cart = {"customer_id": customer, "quote_id": quote.json()["id"]}
    sale = {**cart, "location_id": location, "tender": "cash"}

    kept = await seller.post(SALE_PREVIEW, json={**cart, "lines": [_line(chair, qty=3)]})
    assert kept.status_code == 200, kept.text
    assert (kept.json()["lines"][0]["blocked_by"], kept.json()["lines"][0]["quantity_rule"]) == (
        None,
        None,
    )
    loose = await seller.post(
        SALE_PREVIEW, json={"customer_id": customer, "lines": [_line(chair, qty=3)]}
    )
    _assert_previewed(loose)

    # A changed quantity and an added off-rule line are still checked.
    _assert_refused(
        await seller.post(SALES, json={**sale, "lines": [_line(chair, qty=5)]}), chair["id"], 5
    )
    _assert_refused(
        await seller.post(
            SALES, json={**sale, "lines": [_line(chair, qty=3), _line(other, qty=1)]}
        ),
        other["id"],
        1,
    )
    # Only the quantity is kept: the quote's discount still needs till.discount here.
    discounted = await seller.post(
        SALES, json={**sale, "lines": [_line(chair, qty=3, discount="10")]}
    )
    assert discounted.status_code == 403, discounted.text
    done = await seller.post(SALES, json={**sale, "lines": [_line(chair, qty=3)]})
    assert done.status_code == 201, done.text
    await _relogin_owner(owner_client)


async def test_till_keeps_a_held_sales_quantity_after_the_rule_tightens(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    location, chair, other, _ = await _till_setup(owner_client, "QR-TH")
    await _as_seller(owner_client)
    seller = owner_client

    async def hold_and_resume(lines: list[dict]) -> tuple[dict, dict]:
        basket = await _fill(seller, await _get(seller, location), lines)
        held = await seller.post(
            HELD,
            json={
                "id": str(uuid.uuid4()),
                "location_id": location,
                "lines": lines,
                "basket_id": basket["id"],
            },
        )
        assert held.status_code == 201, held.text
        return held.json(), basket

    async def resume(held: dict, basket: dict) -> dict:
        resumed = await seller.post(
            f"{HELD}/{held['id']}/resume",
            json={
                "operation_id": str(uuid.uuid4()),
                "location_id": location,
                "version": held["version"],
                "basket_id": basket["id"],
            },
        )
        assert resumed.status_code == 200, resumed.text
        return resumed.json()["basket"]

    async def sell(basket: dict, lines: list[dict]):
        basket = await _fill(seller, await _get(seller, location), lines)
        return await seller.post(
            SALES,
            json={
                "location_id": location,
                "lines": lines,
                "tender": "cash",
                "basket_id": basket["id"],
            },
        )

    # Held while 3 was a valid quantity: the held line keeps it.
    held, basket = await hold_and_resume([_line(chair, qty=3)])
    # The kept quantity is server-side state: never on a held sale or basket response.
    assert "kept_qty" not in held["lines"][0]
    await _set_rule(async_db, chair["id"], 2, 2)
    await _set_rule(async_db, other["id"], 2, 2)
    basket = await resume(held, basket)
    # The kept quantity stays on the server: clients never see or send it.
    assert set(basket["lines"][0]) == {"sku_id", "qty", "discount_percent"}
    preview = await seller.post(
        SALE_PREVIEW, json={"lines": [_line(chair, qty=3)], "basket_id": basket["id"]}
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["lines"][0]["blocked_by"] is None

    # A changed quantity, and an added off-rule line, are checked.
    _assert_refused(await sell(basket, [_line(chair, qty=5)]), chair["id"], 5)
    _assert_refused(await sell(basket, [_line(chair, qty=3), _line(other, qty=1)]), other["id"], 1)
    # Back at the held quantity, it is kept again, and the sale completes.
    done = await sell(basket, [_line(chair, qty=3)])
    assert done.status_code == 201, done.text

    # A line held when it already broke the rule earns no exemption by being held.
    held, basket = await hold_and_resume([_line(other, qty=1)])
    basket = await resume(held, basket)
    _assert_refused(await sell(basket, [_line(other, qty=1)]), other["id"], 1)
    await _relogin_owner(owner_client)


async def test_a_quote_keeps_its_quantities_only_for_its_own_customer_and_once(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    """Security re-check R1: naming a quote must not lift the rule for another sale."""
    location, chair, _, customer = await _till_setup(owner_client, "QR-QS")
    stranger = (await owner_client.post("/api/v1/customers", json={"name": "QR-QS other"})).json()
    quote = await owner_client.post(
        "/api/v1/quotes", json={"customer_id": customer, "lines": [_line(chair, qty=3)]}
    )
    assert quote.status_code == 201, quote.text
    quote_id = quote.json()["id"]
    await _set_rule(async_db, chair["id"], 2, 2)
    await _as_seller(owner_client)
    seller = owner_client
    sale = {"quote_id": quote_id, "location_id": location, "tender": "cash"}

    # The reviewer's probe: another customer, the quoted line twice.
    probe = await seller.post(
        SALES,
        json={
            **sale,
            "customer_id": stranger["id"],
            "lines": [_line(chair, qty=3), _line(chair, qty=3)],
        },
    )
    assert probe.status_code == 409, probe.text
    assert probe.json()["detail"]["code"] == "sale_quantity_rule"
    assert len(probe.json()["detail"]["lines"]) == 2
    # Another customer, the quoted line once: still checked (the customer may be changed at
    # the till with a quote loaded, but the quote's quantities then do not apply).
    _assert_refused(
        await seller.post(
            SALES, json={**sale, "customer_id": stranger["id"], "lines": [_line(chair, qty=3)]}
        ),
        chair["id"],
        3,
    )
    # Its own customer, the quoted line twice: the quote's quantity is handed out once.
    _assert_refused(
        await seller.post(
            SALES,
            json={
                **sale,
                "customer_id": customer,
                "lines": [_line(chair, qty=3), _line(chair, qty=3)],
            },
        ),
        chair["id"],
        3,
    )
    assert (await seller.get(f"/api/v1/quotes/{quote_id}")).json()["status"] == "draft"
    # Its own customer, as quoted: sold, and the quote is converted.
    done = await seller.post(
        SALES, json={**sale, "customer_id": customer, "lines": [_line(chair, qty=3)]}
    )
    assert done.status_code == 201, done.text

    # A converted quote keeps nothing, even on the preview.
    converted = await seller.post(
        SALE_PREVIEW,
        json={"customer_id": customer, "quote_id": quote_id, "lines": [_line(chair, qty=3)]},
    )
    _assert_previewed(converted)
    await _relogin_owner(owner_client)


async def test_a_cancelled_or_foreign_quote_keeps_nothing(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    from app.models.customer import Customer
    from app.models.quote import Quote, QuoteStatus
    from app.models.team import Team
    from app.models.user import User

    location, chair, _, customer = await _till_setup(owner_client, "QR-QC")
    quote = await owner_client.post(
        "/api/v1/quotes", json={"customer_id": customer, "lines": [_line(chair, qty=3)]}
    )
    quote_id = quote.json()["id"]
    assert (await owner_client.post(f"/api/v1/quotes/{quote_id}/cancel")).status_code == 200
    await _set_rule(async_db, chair["id"], 2, 2)
    await _as_seller(owner_client)
    cart = {"customer_id": customer, "quote_id": quote_id, "lines": [_line(chair, qty=3)]}
    _assert_previewed(await owner_client.post(SALE_PREVIEW, json=cart))

    # Another company's quote id is not found (the plain test database has no RLS, so this
    # is the code's own team filter).
    other = Team(name="Quote other company", slug="qr-other", clerk_org_id="org_qr_other")
    async_db.add(other)
    await async_db.flush()
    stranger = Customer(team_id=other.id, name="Other company customer")
    async_db.add(stranger)
    await async_db.flush()
    owner = await async_db.scalar(select(User).limit(1))
    foreign = Quote(
        team_id=other.id,
        quote_number="QT-OTHER-1",
        customer_id=stranger.id,
        status=QuoteStatus.DRAFT,
        subtotal_ex_vat=0,
        vat_amount=0,
        total_inc_vat=0,
        vat_rate=Decimal("0.15"),
        created_by_user_id=owner.id,
    )
    async_db.add(foreign)
    await async_db.flush()
    refused = await owner_client.post(
        SALES,
        json={
            "customer_id": customer,
            "quote_id": str(foreign.id),
            "location_id": location,
            "tender": "cash",
            "lines": [_line(chair, qty=2)],
        },
    )
    assert refused.status_code == 404, refused.text
    preview = await owner_client.post(SALE_PREVIEW, json={**cart, "quote_id": str(foreign.id)})
    _assert_previewed(preview)
    await _relogin_owner(owner_client)
