"""Sale line pricing: the one rule that prices a line on every sale document.

Firstout ADR 0001 (one price rule) and 0002 (discount and price-override authority).
Till sales and their preview, quotes, sales orders, laybys, books invoices and the draft
reprice all price through ``SaleLinePricing.price``; readers of stored lines use
``line_amounts`` / ``document_totals``. Behind the interface: unit price resolution
(hand-made price list, classification tier, Retail), override and discount authority,
rounding once per line, VAT per line at one rate, and the suspect-price warning.

The sale quantity rule (a SKU's "sold in multiples of" and "minimum quantity") is checked
here too, per line; see ``quantity_rule_message``.

ADR 0003: the rate is the team's ``vat_rate`` setting, read once when pricing starts, or
the stored rate of the document being repriced; the preview returns it for the document
to keep.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.price_list import PriceListCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.exceptions import ForbiddenError, TillPriceConflictError
from app.models.customer import Customer
from app.models.sku import Sku
from app.permissions import SALES_PRICE_OVERRIDE, STOCK_COST_VIEW, TILL_DISCOUNT, USERS_MANAGE
from app.schemas.sale_line_pricing import SaleLinePrice, SalePricePreview
from app.services.permissions import PermissionService
from app.services.pricing import (
    RETAIL_CLASSIFICATION,
    classification_of,
    is_cin7_generated_price_list,
    price_list_missing_note,
    resolve_unit_price,
)
from app.services.suspect_price import average_costs_by_sku_id, suspect_line_warning
from app.services.vat import CENT, current_vat_rate, ex_to_inc
from f0rge_core.exceptions import ConflictError

_HUNDRED = Decimal(100)

# ``blocked_by`` for a line whose quantity breaks its SKU's selling rule.
QUANTITY_RULE = "quantity_rule"


def quantity_rule_message(sku: Sku, qty: int) -> Optional[str]:
    """The plain refusal when ``qty`` breaks the SKU's selling rule, else None.

    A line breaks it when its quantity is not a multiple of ``sell_multiple`` or is
    below ``min_sell_qty``. The message states the whole rule.
    """
    multiple, minimum = sku.sell_multiple or 1, sku.min_sell_qty or 1
    if qty % multiple == 0 and qty >= minimum:
        return None
    if multiple == 1:
        return f"{sku.name} has a minimum quantity of {minimum}."
    if minimum > multiple:
        return f"{sku.name} is sold in multiples of {multiple}, minimum {minimum}."
    return f"{sku.name} is sold in multiples of {multiple}."


class SaleQuantityRuleError(ConflictError):
    """Lines break their SKU's selling rule and the actor may not break it. HTTP 409."""

    def __init__(self, lines: list[tuple[Sku, int, str]]) -> None:
        message = " ".join(text for _, _, text in lines)
        super().__init__(message)
        self.payload = {
            "code": "sale_quantity_rule",
            "message": message,
            "lines": [
                {
                    "sku_id": str(sku.id),
                    "our_ref": sku.our_ref,
                    "name": sku.name,
                    "qty": qty,
                    "sell_multiple": sku.sell_multiple,
                    "min_sell_qty": sku.min_sell_qty,
                    "message": text,
                }
                for sku, qty, text in lines
            ],
        }


def _cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def line_amounts(
    unit_ex_vat: Decimal, qty: int, discount_percent: Optional[Decimal], vat_rate: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    """A line's (ex VAT, VAT, incl. VAT): rounded once, half-up, VAT from the rounded amount.

    A None discount is a line stored before this rule, whose unit is already net.
    """
    discount = discount_percent or Decimal(0)
    ex_vat = _cents(unit_ex_vat * qty * (_HUNDRED - discount) / _HUNDRED)
    inc_vat = ex_to_inc(ex_vat, vat_rate)
    return ex_vat, inc_vat - ex_vat, inc_vat


def document_totals(
    lines: Iterable[tuple[Decimal, int, Optional[Decimal]]],
    vat_rate: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """(subtotal ex VAT, VAT, total incl. VAT) of (unit, qty, discount %) lines."""
    subtotal = vat = total = Decimal(0)
    for unit, qty, discount in lines:
        ex_vat, line_vat, inc_vat = line_amounts(unit, qty, discount, vat_rate)
        subtotal += ex_vat
        vat += line_vat
        total += inc_vat
    return subtotal, vat, total


@dataclass(frozen=True)
class PricingAuthority:
    """What the acting staff member may do to a price, from their permissions (ADR 0002)."""

    can_discount: bool
    can_exceed_cap: bool
    # sales.price_override: a unit other than the resolved one, and a quantity that breaks
    # the SKU's selling rule.
    can_override: bool
    sees_cost: bool
    discount_cap: Optional[Decimal]

    @classmethod
    async def of(cls, db: AsyncSession, user_id: Optional[uuid.UUID]) -> PricingAuthority:
        """The staff member's authority. No user (a portal order, a schedule) may lower nothing."""
        cap = await _discount_cap(db)
        keys = set(await PermissionService(db).keys_for_user(user_id)) if user_id else set()
        return cls(
            can_discount=TILL_DISCOUNT in keys,
            can_exceed_cap=USERS_MANAGE in keys,
            can_override=SALES_PRICE_OVERRIDE in keys,
            sees_cost=STOCK_COST_VIEW in keys,
            discount_cap=cap,
        )

    @classmethod
    def system(cls) -> PricingAuthority:
        """Firstout itself repricing what staff already authorised (the draft reprice).

        Explicit, never implied by a missing user.
        """
        return cls(True, True, True, False, None)


async def _discount_cap(db: AsyncSession) -> Optional[Decimal]:
    team = await TeamCRUD(db).get_first()
    settings = await TeamSettingsCRUD(db).get_by_team_id(team.id) if team else None
    return settings.max_till_discount_percent if settings else None


class SavedLine(Protocol):
    """A line as its document already stores it; its price and discount were authorised then."""

    qty: int
    unit_ex_vat: Decimal
    discount_percent: Decimal
    price_warning: Optional[str]


@dataclass(frozen=True)
class SaleLineRequest:
    # None: a free-text books line, charged at unit_ex_vat.
    sku: Optional[Sku]
    qty: int
    discount_percent: Decimal = Decimal(0)
    # A Price override for a SKU line; the unit of a free-text line.
    unit_ex_vat: Optional[Decimal] = None
    # The document's stored line for the same customer. Its unit and discount need no new
    # authority while the quantity does not grow (ADR 0002); the caller passes None when
    # the customer changed.
    saved: Optional[SavedLine] = None
    # The quantity the document already stores for this SKU's line, when ``saved`` is not
    # passed (another customer). An unchanged saved quantity is not checked against the
    # SKU's selling rule, so tightening a rule never blocks finishing a saved document.
    saved_qty: Optional[int] = None


class SaleLinePricing:
    """Prices a customer's sale lines for one acting staff member."""

    def __init__(
        self,
        db: AsyncSession,
        customer: Customer,
        authority: PricingAuthority,
        price_list_name: Optional[str],
        require_listed_price: bool,
        vat_rate: Decimal,
    ) -> None:
        self.db = db
        self.customer = customer
        self.authority = authority
        self.price_list_name = price_list_name
        self.require_listed_price = require_listed_price
        self.vat_rate = vat_rate

    @classmethod
    async def for_customer(
        cls,
        db: AsyncSession,
        customer: Customer,
        authority: PricingAuthority,
        *,
        enforce_required_list: bool = False,
        vat_rate: Optional[Decimal] = None,
    ) -> SaleLinePricing:
        """``enforce_required_list`` applies the list's "till must use a listed price" switch.

        The till and books invoices set it; other documents fall back to tier and Retail.
        ``vat_rate`` is a stored document's rate when repricing it; None takes the team's
        rate today.
        """
        if vat_rate is None:
            vat_rate = await current_vat_rate(db)
        if customer.price_list_id is not None:
            policy = await PriceListCRUD(db).get_till_policy(customer.price_list_id)
            if policy is not None and not is_cin7_generated_price_list(policy[0]):
                name, archived, required = policy
                required = required and enforce_required_list
                if archived and required:
                    raise TillPriceConflictError(
                        f"Assign an active price list instead of {name} before selling"
                    )
                return cls(db, customer, authority, name, required, vat_rate)
        return cls(db, customer, authority, None, False, vat_rate)

    async def price(
        self, lines: list[SaleLineRequest], *, enforce: bool = True
    ) -> SalePricePreview:
        """Price every line and total the document.

        ``enforce`` refuses a line whose discount or override the actor may not give:
        ForbiddenError (403) for a missing permission, ConflictError (409) above the
        Discount cap without users.manage, SaleQuantityRuleError (409) for lines that break
        their SKU's selling rule. A preview passes False and reports ``blocked_by`` per
        line instead.
        """
        priced = [await self._line(line) for line in lines]
        if enforce:
            self._require_authorised(lines, priced)
        classification = classification_of(self.customer)
        including_vat = classification == RETAIL_CLASSIFICATION
        costs = await average_costs_by_sku_id(
            self.db, [line.sku_id for line in priced if line.sku_id is not None]
        )
        for line in priced:
            if line.sku_id is not None:
                line.suspect_price_warning = suspect_line_warning(
                    line.unit_ex_vat,
                    line.discount_percent,
                    costs.get(line.sku_id),
                    reveal_cost=self.authority.sees_cost,
                    inclusive_vat_rate=self.vat_rate if including_vat else None,
                )
        subtotal = sum((line.ex_vat for line in priced), Decimal(0))
        vat = sum((line.vat_amount for line in priced), Decimal(0))
        result = SalePricePreview(
            classification=classification,
            price_list_name=self.price_list_name,
            prices_include_vat=including_vat,
            vat_rate=self.vat_rate,
            before_discount_ex_vat=sum(
                (line.before_discount_ex_vat for line in priced), Decimal(0)
            ),
            before_discount_inc_vat=sum(
                (ex_to_inc(line.before_discount_ex_vat, self.vat_rate) for line in priced),
                Decimal(0),
            ),
            subtotal_ex_vat=subtotal,
            vat_amount=vat,
            total_inc_vat=subtotal + vat,
            lines=priced,
            price_revision="",
        )
        # Identifies the agreed calculation and scope; the till recalculates it on posting.
        # Viewer-specific warnings stay out so they cannot fail a sale.
        scope = f"{self.customer.id}/{self.customer.price_list_id}/"
        fingerprint = scope + result.model_dump_json(
            exclude={
                "price_revision": True,
                "lines": {"__all__": {"suspect_price_warning", "blocked_by", "quantity_rule"}},
            }
        )
        result.price_revision = hashlib.sha256(fingerprint.encode()).hexdigest()
        return result

    def _require_authorised(
        self, requests: list[SaleLineRequest], priced: list[SaleLinePrice]
    ) -> None:
        for request, line in zip(requests, priced, strict=True):
            ref = request.sku.our_ref if request.sku is not None else "this line"
            if line.blocked_by == USERS_MANAGE:
                raise ConflictError(
                    f"Discount exceeds maximum allowed ({self.authority.discount_cap}%)"
                )
            if line.blocked_by == TILL_DISCOUNT:
                raise ForbiddenError(f"Discount permission (till.discount) required for {ref}")
            if line.blocked_by == SALES_PRICE_OVERRIDE:
                raise ForbiddenError(
                    f"Price override permission (sales.price_override) required for {ref}"
                )
        broken = [
            (request.sku, line.qty, line.quantity_rule)
            for request, line in zip(requests, priced, strict=True)
            if line.blocked_by == QUANTITY_RULE
            and request.sku is not None
            and line.quantity_rule is not None
        ]
        if broken:
            raise SaleQuantityRuleError(broken)

    async def _resolve(self, sku: Sku) -> tuple[Decimal, str, Optional[str]]:
        if self.require_listed_price:
            # The exact assigned list entry: a missing entry never falls through to an old
            # catalogue price.
            assert self.customer.price_list_id is not None
            amount = await PriceListCRUD(self.db).get_item_price(
                self.customer.price_list_id, sku.id
            )
            if amount is None:
                raise TillPriceConflictError(
                    f"{sku.our_ref} needs a price in {self.price_list_name} before selling"
                )
            return _cents(amount), "price_list", None
        resolved = await resolve_unit_price(self.db, sku, self.customer)
        warning = resolved.warning
        if self.price_list_name is not None and resolved.source != "price_list":
            missing = price_list_missing_note(self.price_list_name, sku.our_ref)
            warning = f"{missing} {warning}" if warning else missing
        return _cents(resolved.unit_ex_vat), resolved.source, warning

    async def _line(self, request: SaleLineRequest) -> SaleLinePrice:
        """Price one line. A change the actor may not make is reported in ``blocked_by``
        and left out of the amounts: the line is priced at the resolved unit and without
        that discount, so nothing derived from cost can follow an input they may not set.
        """
        authority = self.authority
        saved = request.saved
        # Saved values stay authorised only while the quantity does not grow.
        keep = saved if saved is not None and request.qty <= saved.qty else None
        blocked: Optional[str] = None
        resolved: Optional[Decimal] = None
        warning: Optional[str] = None
        if request.sku is None:
            assert request.unit_ex_vat is not None, "a free-text line needs its unit price"
            unit, source = _cents(request.unit_ex_vat), "manual"
        else:
            resolved, source, warning = await self._resolve(request.sku)
            unit = resolved
            if request.unit_ex_vat is not None:
                asked: Optional[Decimal] = _cents(request.unit_ex_vat)
            else:
                # An omitted unit keeps the saved one only while it may be kept;
                # otherwise the line takes today's resolved price.
                asked = _cents(keep.unit_ex_vat) if keep is not None else None
            if asked is not None and asked != resolved:
                if keep is not None and asked == _cents(keep.unit_ex_vat):
                    unit, source, warning = asked, "saved", keep.price_warning
                elif authority.can_override:
                    unit, source, warning = asked, "override", None
                else:
                    blocked = SALES_PRICE_OVERRIDE

        discount = _cents(Decimal(request.discount_percent))
        kept = keep is not None and discount == _cents(keep.discount_percent)
        if discount > 0 and not kept:
            cap = authority.discount_cap
            if not authority.can_discount:
                blocked = blocked or TILL_DISCOUNT
                discount = Decimal("0.00")
            elif cap is not None and discount > cap and not authority.can_exceed_cap:
                blocked = blocked or USERS_MANAGE
                discount = Decimal("0.00")

        rule: Optional[str] = None
        kept_qty = (
            request.saved_qty
            if request.saved_qty is not None
            else (saved.qty if saved is not None else None)
        )
        # A kit line is checked against the kit SKU only; a free-text line never.
        if request.sku is not None and request.qty != kept_qty:
            rule = quantity_rule_message(request.sku, request.qty)
            # sales.price_override may also break the rule (one replacement chair).
            if rule is not None and not authority.can_override:
                blocked = blocked or QUANTITY_RULE

        ex_vat, vat, inc_vat = line_amounts(unit, request.qty, discount, self.vat_rate)
        return SaleLinePrice(
            sku_id=request.sku.id if request.sku is not None else None,
            qty=request.qty,
            discount_percent=discount,
            unit_ex_vat=unit,
            unit_inc_vat=ex_to_inc(unit, self.vat_rate),
            resolved_unit_ex_vat=resolved,
            before_discount_ex_vat=unit * request.qty,
            ex_vat=ex_vat,
            vat_amount=vat,
            inc_vat=inc_vat,
            source=source,
            price_warning=warning,
            blocked_by=blocked,
            quantity_rule=rule,
        )
