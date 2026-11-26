from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.price_list import PriceListCRUD
from app.models.customer import Customer
from app.models.sku import Sku
from app.services.vat import CENT, ex_to_inc
from f0rge_core.exceptions import ValidationError

PRICE_CLASSIFICATIONS = ("Stockist", "Wholesale", "Decorator", "Retail")
RETAIL_CLASSIFICATION = "Retail"
# Historical Cin7 price lists must not override the customer classification.
CIN7_NAMED_PRICE_LISTS = frozenset(
    {
        "Cin7 Stockist",
        "Cin7 Wholesale",
        "Cin7 Decorator",
        "Cin7 Retail",
    }
)
_CIN7_TIER_LIST = re.compile(r"^Cin7 Tier [1-9]\d*$")

_TIER_ATTR = {
    "Stockist": "stockist_ex_vat",
    "Wholesale": "wholesale_ex_vat",
    "Decorator": "decorator_ex_vat",
    "Retail": "retail_ex_vat",
}


def classification_for_legacy_customer_type(customer_type: Optional[str]) -> str:
    """Map the old retail/trade flag. Trade becomes Wholesale; everything else is Retail."""
    if customer_type == "trade":
        return "Wholesale"
    return RETAIL_CLASSIFICATION


def customer_type_for_classification(classification: str) -> str:
    """Keep customer_type in step with classification. Only Retail stays retail."""
    if classification == RETAIL_CLASSIFICATION:
        return "retail"
    return "trade"


def classification_of(customer: Optional[Customer]) -> str:
    if customer is None:
        return RETAIL_CLASSIFICATION
    value = getattr(customer, "price_classification", None)
    if value in PRICE_CLASSIFICATIONS:
        return value
    return classification_for_legacy_customer_type(getattr(customer, "customer_type", None))


def is_cin7_generated_price_list(name: Optional[str]) -> bool:
    """True for `Cin7 Tier N` and the four named Cin7 classification lists.

    Matching is by those names. A list with any other name still overrides.
    """
    if name is None:
        return False
    text = name.strip()
    return text in CIN7_NAMED_PRICE_LISTS or _CIN7_TIER_LIST.fullmatch(text) is not None


def shows_prices_including_vat(customer: Optional[Customer]) -> bool:
    """Retail, including a walk-in with no customer, is the only inclusive display."""
    return classification_of(customer) == RETAIL_CLASSIFICATION


def format_pdf_unit(unit_ex: Decimal, including_vat: bool, vat_rate: Decimal) -> str:
    # The basis lives in the column header (pdf_unit_header), as on the invoice screen.
    # ``vat_rate`` is the document's stored rate.
    return f"{ex_to_inc(unit_ex, vat_rate) if including_vat else unit_ex:.2f}"


def format_pdf_discount(discount_percent: Optional[Decimal]) -> Optional[str]:
    # None is a line stored before line discounts were kept: its unit is already net.
    return f"{discount_percent:.2f}%" if discount_percent else None


def price_list_missing_note(list_name: str, our_ref: str) -> str:
    """Staff-only: the customer's price list has no entry for this SKU."""
    return f"No price in {list_name} for {our_ref}."


_PRICE_LIST_MISSING_NOTE = re.compile(r"^No price in .+? for \S+\.\s*")


def customer_price_warning(warning: Optional[str]) -> Optional[str]:
    """A line's price warning as a customer may see it (PDF, portal): without the
    staff-only price-list note, which names an internal list."""
    if warning is None:
        return None
    return _PRICE_LIST_MISSING_NOTE.sub("", warning, count=1).strip() or None


def pdf_unit_header(including_vat: bool) -> str:
    return "Unit incl. VAT" if including_vat else "Unit excl. VAT"


def pdf_unit_basis_note(including_vat: bool) -> str:
    if including_vat:
        return "Unit prices incl. VAT"
    return "Unit prices excl. VAT. VAT is added to the total."


def _positive(amount: Optional[Decimal]) -> Optional[Decimal]:
    if amount is None or amount <= 0:
        return None
    return amount


@dataclass(frozen=True)
class ResolvedUnitPrice:
    unit_ex_vat: Decimal
    warning: Optional[str]
    source: str


async def resolve_unit_price(
    db: Optional[AsyncSession],
    sku: Sku,
    customer: Optional[Customer],
) -> ResolvedUnitPrice:
    """Hand-made price list, then the customer's classification tier, then Retail.

    Cin7-generated lists are not overrides: `Cin7 Tier 4` stored inc-VAT figures
    as ex VAT, and the named Cin7 lists would replace the classification.
    A missing Stockist, Wholesale, or Decorator price falls back to Retail and
    sets a warning. Retail with no positive price is still an error.
    """
    classification = classification_of(customer)
    price_list_id = getattr(customer, "price_list_id", None) if customer is not None else None
    if price_list_id is not None and db is not None:
        list_name = await PriceListCRUD(db).get_name(price_list_id)
        if list_name is not None and not is_cin7_generated_price_list(list_name):
            list_price = await PriceListCRUD(db).get_item_price(price_list_id, sku.id)
            positive_list = _positive(list_price)
            if positive_list is not None:
                return ResolvedUnitPrice(positive_list, None, "price_list")

    return resolve_classification_price(sku, classification)


def resolve_classification_price(
    sku: Sku,
    classification: str,
    *,
    price_updates: Optional[Mapping[str, Optional[Decimal]]] = None,
) -> ResolvedUnitPrice:
    """Resolve catalogue tiers, with optional ex-VAT changes for a SKU preview."""
    updates = price_updates or {}
    tier_field = _TIER_ATTR[classification]
    tier_amount = _positive(updates.get(tier_field, getattr(sku, tier_field, None)))
    if tier_amount is not None:
        return ResolvedUnitPrice(tier_amount, None, classification.lower())

    if classification != RETAIL_CLASSIFICATION:
        retail = _positive(updates.get("retail_ex_vat", getattr(sku, "retail_ex_vat", None)))
        if retail is not None:
            warning = f"{classification} price is missing for {sku.our_ref}; using Retail price"
            return ResolvedUnitPrice(retail, warning, "retail_fallback")

    raise ValidationError(f"SKU {sku.our_ref} has no retail price")


async def resolve_unit_ex_vat(
    db: Optional[AsyncSession],
    sku: Sku,
    customer: Optional[Customer],
) -> Decimal:
    # The portal displays the same unit cents that its sales orders use.
    price = await resolve_unit_price(db, sku, customer)
    return price.unit_ex_vat.quantize(CENT, rounding=ROUND_HALF_UP)
