from __future__ import annotations

import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.payment import PaymentCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.journal import JournalDocumentType
from app.models.location import LocationType
from app.models.payment import Payment, PaymentDirection
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.schemas.invoice import InvoiceLineResponse
from app.schemas.till import TillSaleCreate, TillSaleLocationStock, TillSaleResponse
from app.services.chart_of_accounts import (
    CODE_AR,
    CODE_BANK,
    CODE_COGS,
    CODE_INVENTORY,
    CODE_SALES,
    CODE_VAT,
    LedgerPostingService,
)
from app.services.stocktakes import StocktakeService
from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from app.services.vat import CENT, ex_to_inc
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class TillOrchestrator:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.location_stock_crud = LocationStockCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.payment_crud = PaymentCRUD(db)
        self.customer_crud = CustomerCRUD(db)
        self.posting = LedgerPostingService(db)

    async def create_sale(self, data: TillSaleCreate) -> TillSaleResponse:
        await StocktakeService(self.db).assert_location_unlocked(data.location_id)
        from app.crud.location import LocationCRUD

        location = await LocationCRUD(self.db).get_by_id(data.location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot sell from archived location")
        if location.type != LocationType.SHOWROOM:
            raise ConflictError("Till sales are only allowed at showroom locations")

        customer = await self._get_walk_in_customer()
        sale_date = datetime.date.today()

        line_inputs: list[tuple] = []
        total_cogs = Decimal(0)

        for line in data.lines:
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            if sku.retail_ex_vat is None or sku.retail_ex_vat <= 0:
                raise ValidationError(f"SKU {sku.our_ref} has no retail price")

            location_stock = await self.location_stock_crud.get_by_sku_and_location(
                line.sku_id,
                data.location_id,
            )
            if location_stock is None or location_stock.on_hand < line.qty:
                raise ConflictError(
                    f"Insufficient on-hand quantity for {sku.our_ref} at this location"
                )
            if location_stock.unit_cost_zar is None:
                raise ConflictError(f"No unit cost for {sku.our_ref} at this location")

            line_cogs = (location_stock.unit_cost_zar * line.qty).quantize(
                CENT,
                rounding=ROUND_HALF_UP,
            )
            total_cogs += line_cogs
            line_inputs.append((sku, line.qty, location_stock, line.discount_percent))

        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        invoice_line_models: list[InvoiceLine] = []

        for index, (sku, qty, _stock, discount_percent) in enumerate(line_inputs):
            discounted_unit = (
                sku.retail_ex_vat * (Decimal(100) - discount_percent) / Decimal(100)
            ).quantize(CENT, rounding=ROUND_HALF_UP)
            ex_vat = (Decimal(qty) * discounted_unit).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            subtotal += ex_vat
            vat_total += line_vat
            total_inc += inc_vat
            invoice_line_models.append(
                InvoiceLine(
                    description=sku.name,
                    qty=qty,
                    unit_ex_vat=discounted_unit,
                    ex_vat=ex_vat,
                    inc_vat=inc_vat,
                    vat_amount=line_vat,
                    sort_order=index,
                    sku_id=sku.id,
                )
            )

        if subtotal <= 0:
            raise ValidationError("Sale total must be positive")

        invoice_number = await self.invoice_crud.get_next_invoice_number()
        payment_number = await self.payment_crud.get_next_payment_number()

        invoice = TaxInvoice(
            invoice_number=invoice_number,
            customer_id=customer.id,
            issue_date=sale_date,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_total,
            total_inc_vat=total_inc,
            amount_paid=Decimal(0),
            lines=invoice_line_models,
        )

        payment = Payment(
            payment_number=payment_number,
            direction=PaymentDirection.IN,
            invoice_id=None,
            amount=total_inc,
            currency="ZAR",
            fx_to_zar=Decimal("1"),
            amount_zar=total_inc,
            fx_gain_loss_zar=Decimal(0),
            paid_on=sale_date,
            tender=data.tender,
        )

        async with unit_of_work(self.db):
            await self.invoice_crud.add_and_flush(invoice)
            payment.invoice_id = invoice.id

            await self.posting.post(
                JournalDocumentType.INVOICE,
                invoice.id,
                f"Till tax invoice {invoice_number}",
                [
                    (CODE_AR, total_inc, Decimal(0)),
                    (CODE_SALES, Decimal(0), subtotal),
                    (CODE_VAT, Decimal(0), vat_total),
                ],
            )

            await self.payment_crud.add_and_flush(payment)
            await self.posting.post(
                JournalDocumentType.PAYMENT,
                payment.id,
                f"Till payment {payment_number} ({data.tender})",
                [
                    (CODE_BANK, total_inc, Decimal(0)),
                    (CODE_AR, Decimal(0), total_inc),
                ],
            )

            if total_cogs > 0:
                await self.posting.post(
                    JournalDocumentType.INVOICE,
                    invoice.id,
                    f"COGS for till sale {invoice_number}",
                    [
                        (CODE_COGS, total_cogs, Decimal(0)),
                        (CODE_INVENTORY, Decimal(0), total_cogs),
                    ],
                )

            for sku, qty, location_stock, _discount in line_inputs:
                location_stock.on_hand -= qty

            invoice.amount_paid = total_inc
            await self.invoice_crud.commit_refresh(invoice)

        reloaded = await self.invoice_crud.get_by_id(invoice.id)
        assert reloaded is not None

        remaining_stock = await self.location_stock_crud.get_by_sku_and_location(
            line_inputs[0][0].id,
            data.location_id,
        )
        on_hand = remaining_stock.on_hand if remaining_stock is not None else 0

        return TillSaleResponse(
            invoice_id=reloaded.id,
            invoice_number=reloaded.invoice_number,
            payment_id=payment.id,
            payment_number=payment.payment_number,
            tender=data.tender,
            issue_date=reloaded.issue_date,
            subtotal_ex_vat=reloaded.subtotal_ex_vat,
            vat_amount=reloaded.vat_amount,
            total_inc_vat=reloaded.total_inc_vat,
            lines=[
                InvoiceLineResponse(
                    id=line.id,
                    description=line.description,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    ex_vat=line.ex_vat,
                    inc_vat=line.inc_vat,
                    vat_amount=line.vat_amount,
                    sort_order=line.sort_order,
                    sku_id=line.sku_id,
                )
                for line in reloaded.lines
            ],
            location=TillSaleLocationStock(
                location_id=location.id,
                location_name=location.name,
                on_hand=on_hand,
            ),
        )

    async def _get_walk_in_customer(self):
        from app.models.customer import Customer

        walk_in = (
            await self.db.execute(
                select(Customer).where(Customer.name == WALK_IN_CUSTOMER_NAME).limit(1)
            )
        ).scalar_one_or_none()
        if walk_in is None:
            raise NotFoundError("Walk-in customer not seeded")
        return walk_in
