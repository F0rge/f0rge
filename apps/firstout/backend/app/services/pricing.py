from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.price_list import PriceListCRUD
from app.models.customer import Customer
from app.models.sku import Sku
from f0rge_core.exceptions import ValidationError


async def resolve_unit_ex_vat(
    db: AsyncSession,
    sku: Sku,
    customer: Customer,
) -> Decimal:
    if customer.price_list_id is not None:
        list_price = await PriceListCRUD(db).get_item_price(customer.price_list_id, sku.id)
        if list_price is not None:
            return list_price
    if customer.customer_type == "trade" and sku.wholesale_ex_vat is not None:
        price = sku.wholesale_ex_vat
    else:
        price = sku.retail_ex_vat
    if price is None or price <= 0:
        raise ValidationError(f"SKU {sku.our_ref} has no retail price")
    return price
