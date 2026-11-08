from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.price_list import PriceListCRUD
from app.models.customer import Customer
from app.models.sku import Sku
from app.services.vat import ex_to_inc
from f0rge_core.exceptions import ValidationError

PRICE_CLASSIFICATIONS = ("Stockist", "Wholesale", "Decorator", "Retail")
RETAIL_CLASSIFICATION = "Retail"
# Names the Cin7 import writes. These lists must not override classification.
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


def classification_from_cin7_tier(tier: Optional[str]) -> str:
    key = (tier or "").strip().lower()
    return {
        "stockist": "Stockist",
        "wholesale": "Wholesale",
        "decorator": "Decorator",
        "retail": "Retail",
    }.get(key, RETAIL_CLASSIFICATION)


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


def format_pdf_unit(unit_ex: Decimal, including_vat: bool) -> str:
    if including_vat:
        return f"{ex_to_inc(unit_ex):.2f} incl. VAT"
    return f"{unit_ex:.2f} excl. VAT"


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

    tier_amount = _positive(getattr(sku, _TIER_ATTR[classification], None))
    if tier_amount is not None:
        return ResolvedUnitPrice(tier_amount, None, classification.lower())

    if classification != RETAIL_CLASSIFICATION:
        retail = _positive(getattr(sku, "retail_ex_vat", None))
        if retail is not None:
            warning = f"{classification} price is missing for {sku.our_ref}; using Retail price"
            return ResolvedUnitPrice(retail, warning, "retail_fallback")

    raise ValidationError(f"SKU {sku.our_ref} has no retail price")


async def resolve_unit_ex_vat(
    db: Optional[AsyncSession],
    sku: Sku,
    customer: Optional[Customer],
) -> Decimal:
    return (await resolve_unit_price(db, sku, customer)).unit_ex_vat
