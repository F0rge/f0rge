"""Sale line pricing at its interface (Firstout ADR 0001 and 0002), without HTTP."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

import pytest

from app.exceptions import ForbiddenError
from app.models.customer import Customer
from app.models.price_list import PriceList, PriceListItem
from app.models.sku import Sku
from app.services.sale_line_pricing import (
    PricingAuthority,
    SaleLinePricing,
    SaleLineRequest,
    line_amounts,
)
from app.services.suspect_price import RESTRICTED_SUSPECT_PRICE_WARNING
from f0rge_core.exceptions import ConflictError

D = Decimal
STAFF = PricingAuthority(
    can_discount=True, can_exceed_cap=False, can_override=False, sees_cost=False, discount_cap=None
)


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("unit", "qty", "discount", "expected"),
    [
        # Rounded once per line. Rounding the discounted unit first (R30.00 × 3) gave R90.00.
        ("33.33", 3, "10", ("89.99", "13.50", "103.49")),
        # One unit: both rules agree.
        ("33.33", 1, "10", ("30.00", "4.50", "34.50")),
        ("250.00", 2, "100", ("0.00", "0.00", "0.00")),
        ("999.99", 2, "0", ("1999.98", "300.00", "2299.98")),
        # A line stored before discounts were kept: its unit is already net.
        ("30.00", 3, None, ("90.00", "13.50", "103.50")),
    ],
)
def test_line_amounts_round_each_line_once(unit, qty, discount, expected) -> None:
    # The till, quotes, orders and laybys take whole quantities only (qty: int), so there
    # is no fractional-quantity case.
    amounts = line_amounts(D(unit), qty, D(discount) if discount is not None else None)
    assert amounts == tuple(D(value) for value in expected)


async def _sku(db, retail: str, **tiers: str) -> Sku:
    ref = f"SLP-{uuid.uuid4().hex[:8]}"
    sku = Sku(
        our_ref=ref,
        our_barcode=ref,
        name=ref,
        design=ref,
        fabric=ref,
        retail_ex_vat=D(retail),
        **{key: D(value) for key, value in tiers.items()},
    )
    db.add(sku)
    await db.flush()
    return sku


async def _customer(db, classification: str = "Retail", list_name: Optional[str] = None):
    customer = Customer(name=f"Pricing {uuid.uuid4().hex[:6]}", price_classification=classification)
    if list_name is not None:
        price_list = PriceList(name=list_name)
        db.add(price_list)
        await db.flush()
        customer.price_list_id = price_list.id
    db.add(customer)
    await db.flush()
    return customer


async def _price(db, customer, lines, authority=STAFF, *, enforce=True):
    pricing = await SaleLinePricing.for_customer(db, customer, authority)
    return await pricing.price(lines, enforce=enforce)


async def test_price_list_beats_tier_beats_retail_and_cin7_lists_are_skipped(async_db) -> None:
    sku = await _sku(async_db, "100.00", wholesale_ex_vat="80.00")
    no_tier = await _sku(async_db, "100.00")
    listed = await _customer(async_db, "Wholesale", "Hand-made trade list")
    async_db.add(
        PriceListItem(price_list_id=listed.price_list_id, sku_id=sku.id, unit_ex_vat=D("70.00"))
    )
    cin7 = await _customer(async_db, "Wholesale", "Cin7 Tier 7")
    async_db.add(
        PriceListItem(price_list_id=cin7.price_list_id, sku_id=sku.id, unit_ex_vat=D("50.00"))
    )
    await async_db.flush()

    by_list = await _price(async_db, listed, [SaleLineRequest(sku=sku, qty=1)])
    assert (by_list.lines[0].unit_ex_vat, by_list.lines[0].source) == (D("70.00"), "price_list")
    assert by_list.price_list_name == "Hand-made trade list"

    missing = (await _price(async_db, listed, [SaleLineRequest(sku=no_tier, qty=1)])).lines[0]
    assert (missing.unit_ex_vat, missing.source) == (D("100.00"), "retail_fallback")
    assert missing.price_warning.startswith("No price in Hand-made trade list")

    by_tier = (await _price(async_db, cin7, [SaleLineRequest(sku=sku, qty=1)])).lines[0]
    assert (by_tier.unit_ex_vat, by_tier.source) == (D("80.00"), "wholesale")
    retail = await _price(async_db, await _customer(async_db), [SaleLineRequest(sku=sku, qty=1)])
    assert (retail.lines[0].unit_ex_vat, retail.lines[0].source) == (D("100.00"), "retail")
    assert retail.prices_include_vat is True


class _Saved:
    def __init__(self, unit: str, discount: str, qty: int = 1) -> None:
        self.qty = qty
        self.unit_ex_vat = D(unit)
        self.discount_percent = D(discount)
        self.price_warning = None


def _authority(*, discount=False, manage=False, override=False, cap="10"):
    return PricingAuthority(
        can_discount=discount,
        can_exceed_cap=manage,
        can_override=override,
        sees_cost=False,
        discount_cap=D(cap) if cap is not None else None,
    )


@pytest.mark.parametrize(
    ("authority", "discount", "saved", "blocked", "error"),
    [
        (_authority(), "5", None, "till.discount", ForbiddenError),
        (_authority(discount=True), "10", None, None, None),
        (_authority(discount=True), "15", None, "users.manage", ConflictError),
        (_authority(discount=True, manage=True), "15", None, None, None),
        (_authority(discount=True, cap=None), "60", None, None, None),
        # A discount the document already carries was authorised when it was given.
        (_authority(), "20", _Saved("100.00", "20"), None, None),
        (_authority(), "25", _Saved("100.00", "20"), "till.discount", ForbiddenError),
        # Removing a discount raises the price: no authority needed.
        (_authority(), "0", _Saved("100.00", "20"), None, None),
        # A kept discount on more units than were authorised needs the permission again.
        (_authority(), "20", _Saved("100.00", "20", qty=0), "till.discount", ForbiddenError),
    ],
)
async def test_discount_authority(async_db, authority, discount, saved, blocked, error) -> None:
    sku = await _sku(async_db, "100.00")
    customer = await _customer(async_db)
    line = SaleLineRequest(sku=sku, qty=1, discount_percent=D(discount), saved=saved)
    preview = await _price(async_db, customer, [line], authority, enforce=False)
    assert preview.lines[0].blocked_by == blocked
    if blocked is not None:
        # A refused discount is left out of the amounts.
        assert (preview.lines[0].discount_percent, preview.subtotal_ex_vat) == (0, D(100))
    if error is None:
        priced = await _price(async_db, customer, [line], authority)
        assert priced.subtotal_ex_vat == D(100) - D(discount)
    else:
        with pytest.raises(error):
            await _price(async_db, customer, [line], authority)


async def test_price_override_needs_its_own_permission(async_db) -> None:
    sku = await _sku(async_db, "100.00")
    customer = await _customer(async_db)
    override = SaleLineRequest(sku=sku, qty=2, unit_ex_vat=D("90.00"))

    refused = await _price(async_db, customer, [override], _authority(discount=True), enforce=False)
    assert refused.lines[0].blocked_by == "sales.price_override"
    with pytest.raises(ForbiddenError, match="sales.price_override"):
        await _price(async_db, customer, [override], _authority(discount=True))

    allowed = (await _price(async_db, customer, [override], _authority(override=True))).lines[0]
    assert (allowed.unit_ex_vat, allowed.resolved_unit_ex_vat) == (D("90.00"), D("100.00"))
    assert (allowed.source, allowed.ex_vat) == ("override", D("180.00"))

    # Sending the resolved price, or the price the document already holds, is no override.
    same = SaleLineRequest(sku=sku, qty=1, unit_ex_vat=D("100.00"))
    kept = SaleLineRequest(sku=sku, qty=1, unit_ex_vat=D("90.00"), saved=_Saved("90.00", "0"))
    priced = await _price(async_db, customer, [same, kept], _authority())
    assert [line.source for line in priced.lines] == ["retail", "saved"]


async def test_free_text_line_charges_its_unit(async_db) -> None:
    customer = await _customer(async_db)
    priced = await _price(
        async_db, customer, [SaleLineRequest(sku=None, qty=3, unit_ex_vat=D("33.33"))]
    )
    line = priced.lines[0]
    assert (line.sku_id, line.source, line.resolved_unit_ex_vat) == (None, "manual", None)
    assert (priced.subtotal_ex_vat, priced.vat_amount, priced.total_inc_vat) == (
        D("99.99"),
        D("15.00"),
        D("114.99"),
    )


async def test_suspect_price_warning_follows_the_viewer(async_db) -> None:
    sku = await _sku(async_db, "1.00")
    fine = await _sku(async_db, "500.00")
    customer = await _customer(async_db)
    lines = [SaleLineRequest(sku=sku, qty=1), SaleLineRequest(sku=fine, qty=1)]

    hidden = await _price(async_db, customer, lines)
    assert [line.suspect_price_warning for line in hidden.lines] == [
        RESTRICTED_SUSPECT_PRICE_WARNING,
        None,
    ]
    shown = await _price(
        async_db,
        customer,
        lines,
        PricingAuthority(
            can_discount=False,
            can_exceed_cap=False,
            can_override=False,
            sees_cost=True,
            discount_cap=None,
        ),
    )
    assert "R1.15 incl. VAT (R1.00 excl.)" in shown.lines[0].suspect_price_warning
    # The till's price revision ignores viewer-only warnings.
    assert hidden.price_revision == shown.price_revision


async def test_saved_override_is_kept_only_up_to_the_saved_quantity(async_db) -> None:
    sku = await _sku(async_db, "100.00")
    customer = await _customer(async_db)
    saved = _Saved("60.00", "0", qty=2)

    kept = await _price(async_db, customer, [SaleLineRequest(sku=sku, qty=2, saved=saved)])
    assert (kept.lines[0].unit_ex_vat, kept.lines[0].source) == (D("60.00"), "saved")
    # More units: an omitted unit takes today's price; asking for the old one is an override.
    grown = await _price(async_db, customer, [SaleLineRequest(sku=sku, qty=3, saved=saved)])
    assert (grown.lines[0].unit_ex_vat, grown.lines[0].source) == (D("100.00"), "retail")
    asked = SaleLineRequest(sku=sku, qty=3, unit_ex_vat=D("60.00"), saved=saved)
    refused = await _price(async_db, customer, [asked], _authority(), enforce=False)
    assert refused.lines[0].blocked_by == "sales.price_override"
    # A refused override is priced at the resolved unit.
    assert (refused.lines[0].unit_ex_vat, refused.subtotal_ex_vat) == (D("100.00"), D("300.00"))
    with pytest.raises(ForbiddenError):
        await _price(async_db, customer, [asked], _authority())


async def test_no_staff_member_means_no_authority(async_db) -> None:
    """A portal order (no user) may not discount or override; only system() may."""
    sku = await _sku(async_db, "100.00")
    customer = await _customer(async_db)
    nobody = await PricingAuthority.of(async_db, None)
    assert (nobody.can_discount, nobody.can_override, nobody.can_exceed_cap) == (False,) * 3
    assert nobody.sees_cost is False
    for line in (
        SaleLineRequest(sku=sku, qty=1, discount_percent=D("5")),
        SaleLineRequest(sku=sku, qty=1, unit_ex_vat=D("50.00")),
    ):
        with pytest.raises(ForbiddenError):
            await _price(async_db, customer, [line], nobody)
        assert (await _price(async_db, customer, [line], PricingAuthority.system())).lines[
            0
        ].blocked_by is None


async def test_draft_reprice_keeps_legacy_net_order_lines(async_db) -> None:
    """A draft order line stored before discounts were kept (NULL) has a net unit."""
    from app.models.sales_order import SalesOrder, SalesOrderLine, SalesOrderStatus
    from app.services.draft_reprice import DraftRepriceService

    legacy_sku = await _sku(async_db, "100.00")
    sku = await _sku(async_db, "100.00")
    customer = await _customer(async_db)
    order = SalesOrder(
        so_number=f"SO-T{uuid.uuid4().hex[:6]}",
        customer_id=customer.id,
        hold_stock=False,
        awaiting_stock=False,
        status=SalesOrderStatus.DRAFT,
        subtotal_ex_vat=D("130.00"),
        vat_amount=D("19.50"),
        total_inc_vat=D("149.50"),
        amount_paid=D(0),
        prices_include_vat=True,
        lines=[
            SalesOrderLine(sku_id=legacy_sku.id, qty=1, unit_ex_vat=D("50.00"), description="L"),
            SalesOrderLine(
                sku_id=sku.id,
                qty=1,
                unit_ex_vat=D("80.00"),
                discount_percent=D("0"),
                description="N",
            ),
        ],
    )
    async_db.add(order)
    await async_db.flush()

    await DraftRepriceService(async_db).reprice(customer.id)
    await async_db.refresh(order, ["lines", "subtotal_ex_vat", "total_inc_vat"])
    units = {line.sku_id: line.unit_ex_vat for line in order.lines}
    assert units == {legacy_sku.id: D("50.00"), sku.id: D("100.00")}
    assert (order.subtotal_ex_vat, order.total_inc_vat) == (D("150.00"), D("172.50"))
