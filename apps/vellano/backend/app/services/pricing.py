from __future__ import annotations

from decimal import Decimal

from app.models.customer import Customer
from app.models.sku import Sku
from f0rge_core.exceptions import ValidationError


def resolve_unit_ex_vat(sku: Sku, customer: Customer) -> Decimal:
    if customer.customer_type == "trade" and sku.wholesale_ex_vat is not None:
        price = sku.wholesale_ex_vat
    else:
        price = sku.retail_ex_vat
    if price is None or price <= 0:
        raise ValidationError(f"SKU {sku.our_ref} has no retail price")
    return price
