from __future__ import annotations

import hashlib
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.price_list import PriceListCRUD
from app.exceptions import TillPriceConflictError
from app.models.customer import Customer
from app.models.sku import Sku
from app.schemas.till import TillPriceLine, TillPricePreview, TillSaleLineCreate
from app.services.pricing import classification_of, is_cin7_generated_price_list, resolve_unit_price
from app.services.vat import CENT, ex_to_inc


class TillPricing:
    """Resolve the selected customer's prices and round checkout money per line."""

    def __init__(
        self,
        db: AsyncSession,
        customer: Customer,
        price_list_name: str | None,
        require_listed_price: bool,
    ) -> None:
        self.db = db
        self.customer = customer
        self.price_list_name = price_list_name
        self.require_listed_price = require_listed_price

    @classmethod
    async def for_customer(cls, db: AsyncSession, customer: Customer) -> TillPricing:
        if customer.price_list_id is not None:
            policy = await PriceListCRUD(db).get_till_policy(customer.price_list_id)
            if policy is not None:
                name, archived, required = policy
                if not is_cin7_generated_price_list(name):
                    if archived and required:
                        raise TillPriceConflictError(
                            f"Assign an active price list instead of {name} before selling"
                        )
                    return cls(db, customer, name, required)
        return cls(db, customer, None, False)

    async def line(self, sku: Sku, item: TillSaleLineCreate) -> TillPriceLine:
        if self.require_listed_price:
            # Require the exact assigned list entry. A missing entry cannot fall
            # through to an old catalogue price even if that price is valid.
            assert self.customer.price_list_id is not None
            amount = await PriceListCRUD(self.db).get_item_price(
                self.customer.price_list_id, sku.id
            )
            if amount is None:
                raise TillPriceConflictError(
                    f"{sku.our_ref} needs a price in {self.price_list_name} before selling"
                )
            source, warning = "price_list", None
        else:
            resolved = await resolve_unit_price(self.db, sku, self.customer)
            amount, source, warning = resolved.unit_ex_vat, resolved.source, resolved.warning
            if self.price_list_name is not None and source != "price_list":
                missing = f"No price in {self.price_list_name} for {sku.our_ref}."
                warning = f"{missing} {warning}" if warning else missing

        # Calculate the discount on the extended line before rounding. Rounding
        # the discounted unit first can shift a multi-quantity line by a cent.
        before_discount = amount * item.qty
        net = (before_discount * (100 - item.discount_percent) / 100).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        gross = ex_to_inc(net)
        return TillPriceLine(
            sku_id=sku.id,
            qty=item.qty,
            discount_percent=item.discount_percent,
            unit_ex_vat=amount,
            before_discount_ex_vat=before_discount,
            ex_vat=net,
            vat_amount=gross - net,
            inc_vat=gross,
            source=source,
            price_warning=warning,
        )

    def preview(self, lines: list[TillPriceLine]) -> TillPricePreview:
        classification = classification_of(self.customer)
        subtotal_before_discount = sum((line.before_discount_ex_vat for line in lines), Decimal(0))
        subtotal = sum((line.ex_vat for line in lines), Decimal(0))
        vat = sum((line.vat_amount for line in lines), Decimal(0))
        gross_before_discount = sum(
            (ex_to_inc(line.before_discount_ex_vat) for line in lines), Decimal(0)
        )
        result = TillPricePreview(
            classification=classification,
            price_list_name=self.price_list_name,
            prices_include_vat=classification == "Retail",
            before_discount_ex_vat=subtotal_before_discount,
            before_discount_inc_vat=gross_before_discount,
            subtotal_ex_vat=subtotal,
            vat_amount=vat,
            total_inc_vat=subtotal + vat,
            lines=lines,
            price_revision="",
        )
        # This identifies the exact agreed calculation and scope. The server
        # calculates it again from its own data when the sale is posted.
        scope = f"{self.customer.id}/{self.customer.price_list_id}/"
        fingerprint = scope + result.model_dump_json(exclude={"price_revision"})
        return result.model_copy(
            update={"price_revision": hashlib.sha256(fingerprint.encode()).hexdigest()}
        )
