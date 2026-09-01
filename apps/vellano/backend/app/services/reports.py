from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.account import AccountCRUD
from app.models.account import AccountType
from app.models.bill import Bill
from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.inventory import LocationStock
from app.models.journal import JournalEntry, JournalLine
from app.models.location import Location
from app.models.sku import Sku
from app.models.supplier import Supplier
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.schemas.bank_import import (
    AgedBucket,
    AgedLine,
    AgedReport,
    BalanceSheetLine,
    BalanceSheetReport,
    ProfitLossLine,
    ProfitLossReport,
    Vat201Draft,
)
from app.schemas.reports_stock import (
    AgedStockBucket,
    AgedStockLine,
    AgedStockReport,
    SalesBySkuLine,
    SalesBySkuReport,
    SalesVatReport,
    StockValuationLine,
    StockValuationReport,
)

AGED_STOCK_BUCKET_SPECS: tuple[tuple[str, str], ...] = (
    ("0-90", "0–90 days"),
    ("91-180", "91–180 days"),
    ("180+", "180+ days"),
)


def _aging_bucket(days: int) -> str:
    if days <= 0:
        return "current"
    if days <= 30:
        return "1-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


def _bucket_label(bucket: str) -> str:
    labels = {
        "current": "Current",
        "1-30": "1–30 days",
        "31-60": "31–60 days",
        "61-90": "61–90 days",
        "90+": "90+ days",
    }
    return labels.get(bucket, bucket)


def _line_stock_value(on_hand: int, unit_cost_zar: Optional[Decimal]) -> Decimal:
    if unit_cost_zar is None or on_hand <= 0:
        return Decimal(0)
    return (Decimal(on_hand) * Decimal(unit_cost_zar)).quantize(Decimal("0.01"))


def _aged_stock_bucket(
    updated_at: datetime.datetime,
    cutoff_90: datetime.datetime,
    cutoff_180: datetime.datetime,
) -> str:
    if updated_at > cutoff_90:
        return "0-90"
    if updated_at > cutoff_180:
        return "91-180"
    return "180+"


class ReportsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.account_crud = AccountCRUD(db)

    async def aged_ar(self, as_of: datetime.date) -> AgedReport:
        result = await self.db.execute(
            select(TaxInvoice, Customer.name)
            .join(Customer, TaxInvoice.customer_id == Customer.id)
            .where(TaxInvoice.total_inc_vat > TaxInvoice.amount_paid)
            .order_by(TaxInvoice.issue_date)
        )
        lines: list[AgedLine] = []
        bucket_totals: dict[str, Decimal] = {
            "current": Decimal(0),
            "1-30": Decimal(0),
            "31-60": Decimal(0),
            "61-90": Decimal(0),
            "90+": Decimal(0),
        }

        for invoice, customer_name in result.all():
            balance = invoice.total_inc_vat - invoice.amount_paid
            if balance <= 0:
                continue
            days = (as_of - invoice.issue_date).days
            bucket = _aging_bucket(days)
            bucket_totals[bucket] += balance
            lines.append(
                AgedLine(
                    document_number=invoice.invoice_number,
                    contact_name=customer_name,
                    issue_date=invoice.issue_date,
                    balance_zar=balance,
                    days_outstanding=days,
                    bucket=bucket,
                )
            )

        total = sum(bucket_totals.values(), Decimal(0))
        buckets = [
            AgedBucket(label=_bucket_label(key), amount_zar=bucket_totals[key])
            for key in ("current", "1-30", "31-60", "61-90", "90+")
        ]
        return AgedReport(as_of=as_of, total_zar=total, buckets=buckets, lines=lines)

    async def aged_ap(self, as_of: datetime.date) -> AgedReport:
        result = await self.db.execute(
            select(Bill, Supplier.name)
            .join(Supplier, Bill.supplier_id == Supplier.id)
            .where(Bill.amount_zar > Bill.amount_paid_zar)
            .order_by(Bill.issue_date)
        )
        lines: list[AgedLine] = []
        bucket_totals: dict[str, Decimal] = {
            "current": Decimal(0),
            "1-30": Decimal(0),
            "31-60": Decimal(0),
            "61-90": Decimal(0),
            "90+": Decimal(0),
        }

        for bill, supplier_name in result.all():
            balance = bill.amount_zar - bill.amount_paid_zar
            if balance <= 0:
                continue
            days = (as_of - bill.issue_date).days
            bucket = _aging_bucket(days)
            bucket_totals[bucket] += balance
            lines.append(
                AgedLine(
                    document_number=bill.bill_number,
                    contact_name=supplier_name,
                    issue_date=bill.issue_date,
                    balance_zar=balance,
                    days_outstanding=days,
                    bucket=bucket,
                )
            )

        total = sum(bucket_totals.values(), Decimal(0))
        buckets = [
            AgedBucket(label=_bucket_label(key), amount_zar=bucket_totals[key])
            for key in ("current", "1-30", "31-60", "61-90", "90+")
        ]
        return AgedReport(as_of=as_of, total_zar=total, buckets=buckets, lines=lines)

    async def profit_loss(
        self, from_date: datetime.date, to_date: datetime.date
    ) -> ProfitLossReport:
        if from_date > to_date:
            raise ValueError("from_date must be on or before to_date")

        accounts = await self.account_crud.list_all()
        income_accounts = [
            a for a in accounts if a.type == AccountType.INCOME and not a.is_archived
        ]
        expense_accounts = [
            a for a in accounts if a.type == AccountType.EXPENSE and not a.is_archived
        ]

        income_lines: list[ProfitLossLine] = []
        expense_lines: list[ProfitLossLine] = []
        total_income = Decimal(0)
        total_expenses = Decimal(0)

        for account in income_accounts:
            amount = await self._period_net(account.id, from_date, to_date, credit_minus_debit=True)
            if amount != 0:
                income_lines.append(
                    ProfitLossLine(code=account.code, name=account.name, amount_zar=amount)
                )
                total_income += amount

        for account in expense_accounts:
            amount = await self._period_net(
                account.id, from_date, to_date, credit_minus_debit=False
            )
            if amount != 0:
                expense_lines.append(
                    ProfitLossLine(code=account.code, name=account.name, amount_zar=amount)
                )
                total_expenses += amount

        return ProfitLossReport(
            from_date=from_date,
            to_date=to_date,
            income=income_lines,
            expenses=expense_lines,
            total_income_zar=total_income,
            total_expenses_zar=total_expenses,
            net_profit_zar=total_income - total_expenses,
        )

    async def balance_sheet(self, as_of: datetime.date) -> BalanceSheetReport:
        accounts = await self.account_crud.list_all()
        assets: list[BalanceSheetLine] = []
        liabilities: list[BalanceSheetLine] = []
        total_assets = Decimal(0)
        total_liabilities = Decimal(0)
        retained_earnings = Decimal(0)

        for account in accounts:
            if account.is_archived:
                continue
            balance = await self._balance_as_of(account.id, as_of)
            if balance == 0:
                continue

            line = BalanceSheetLine(
                code=account.code,
                name=account.name,
                type=account.type.value,
                balance_zar=balance,
            )

            if account.type == AccountType.ASSET:
                assets.append(line)
                total_assets += balance
            elif account.type == AccountType.LIABILITY:
                liabilities.append(line)
                total_liabilities += abs(balance)
            elif account.type in (AccountType.INCOME, AccountType.EXPENSE):
                if account.type == AccountType.INCOME:
                    retained_earnings += balance
                else:
                    retained_earnings -= balance

        equity = total_assets - total_liabilities
        return BalanceSheetReport(
            as_of=as_of,
            assets=assets,
            liabilities=liabilities,
            equity_zar=equity,
            total_assets_zar=total_assets,
            total_liabilities_zar=total_liabilities,
        )

    async def vat201_draft(
        self, period_from: datetime.date, period_to: datetime.date
    ) -> Vat201Draft:
        if period_from > period_to:
            raise ValueError("period_from must be on or before period_to")

        invoice_result = await self.db.execute(
            select(func.coalesce(func.sum(TaxInvoice.subtotal_ex_vat), 0), func.count()).where(
                and_(
                    TaxInvoice.issue_date >= period_from,
                    TaxInvoice.issue_date <= period_to,
                )
            )
        )
        invoice_ex, invoice_count = invoice_result.one()

        cn_result = await self.db.execute(
            select(func.coalesce(func.sum(CreditNote.subtotal_ex_vat), 0), func.count()).where(
                and_(
                    CreditNote.issue_date >= period_from,
                    CreditNote.issue_date <= period_to,
                )
            )
        )
        cn_ex, cn_count = cn_result.one()

        output_tax_result = await self.db.execute(
            select(func.coalesce(func.sum(TaxInvoice.vat_amount), 0)).where(
                and_(
                    TaxInvoice.issue_date >= period_from,
                    TaxInvoice.issue_date <= period_to,
                )
            )
        )
        invoice_vat = output_tax_result.scalar_one()

        cn_vat_result = await self.db.execute(
            select(func.coalesce(func.sum(CreditNote.vat_amount), 0)).where(
                and_(
                    CreditNote.issue_date >= period_from,
                    CreditNote.issue_date <= period_to,
                )
            )
        )
        cn_vat = cn_vat_result.scalar_one()

        standard_rated = Decimal(invoice_ex) - Decimal(cn_ex)
        output_tax = Decimal(invoice_vat) - Decimal(cn_vat)
        input_tax = Decimal(0)

        return Vat201Draft(
            period_from=period_from,
            period_to=period_to,
            standard_rated_supplies_ex_vat=standard_rated,
            output_tax=output_tax,
            input_tax=input_tax,
            net_vat_payable=output_tax - input_tax,
            invoice_count=int(invoice_count),
            credit_note_count=int(cn_count),
        )

    async def stock_valuation(self) -> StockValuationReport:
        result = await self.db.execute(
            select(
                LocationStock,
                Location.name,
                Sku.our_ref,
                Sku.name,
            )
            .join(Location, LocationStock.location_id == Location.id)
            .join(Sku, LocationStock.sku_id == Sku.id)
            .where(LocationStock.on_hand > 0)
            .order_by(Location.name, Sku.our_ref)
        )

        lines: list[StockValuationLine] = []
        total_on_hand = 0
        total_value = Decimal(0)

        for stock, location_name, our_ref, sku_name in result.all():
            value = _line_stock_value(stock.on_hand, stock.unit_cost_zar)
            total_on_hand += stock.on_hand
            total_value += value
            lines.append(
                StockValuationLine(
                    location_id=stock.location_id,
                    location_name=location_name,
                    sku_id=stock.sku_id,
                    our_ref=our_ref,
                    name=sku_name,
                    on_hand=stock.on_hand,
                    unit_cost_zar=stock.unit_cost_zar,
                    value_zar=value,
                )
            )

        return StockValuationReport(
            lines=lines,
            total_on_hand=total_on_hand,
            total_value_zar=total_value.quantize(Decimal("0.01")),
        )

    async def aged_stock(self) -> AgedStockReport:
        now = datetime.datetime.utcnow()
        cutoff_90 = now - datetime.timedelta(days=90)
        cutoff_180 = now - datetime.timedelta(days=180)

        result = await self.db.execute(
            select(
                LocationStock,
                Location.name,
                Sku.our_ref,
                Sku.name,
            )
            .join(Location, LocationStock.location_id == Location.id)
            .join(Sku, LocationStock.sku_id == Sku.id)
            .where(LocationStock.on_hand > 0)
            .order_by(LocationStock.updated_at, Sku.our_ref)
        )

        bucket_lines: dict[str, list[AgedStockLine]] = {
            key: [] for key, _ in AGED_STOCK_BUCKET_SPECS
        }
        bucket_qty: dict[str, int] = {key: 0 for key, _ in AGED_STOCK_BUCKET_SPECS}
        bucket_value: dict[str, Decimal] = {key: Decimal(0) for key, _ in AGED_STOCK_BUCKET_SPECS}

        for stock, location_name, our_ref, sku_name in result.all():
            updated_at = stock.updated_at
            bucket = _aged_stock_bucket(updated_at, cutoff_90, cutoff_180)
            days = max(0, (now - updated_at).days)
            value = _line_stock_value(stock.on_hand, stock.unit_cost_zar)
            line = AgedStockLine(
                sku_id=stock.sku_id,
                our_ref=our_ref,
                name=sku_name,
                location_id=stock.location_id,
                location_name=location_name,
                on_hand=stock.on_hand,
                value_zar=value,
                days=days,
                bucket=bucket,
            )
            bucket_lines[bucket].append(line)
            bucket_qty[bucket] += stock.on_hand
            bucket_value[bucket] += value

        buckets = [
            AgedStockBucket(
                bucket=key,
                label=label,
                qty=bucket_qty[key],
                value_zar=bucket_value[key].quantize(Decimal("0.01")),
                lines=bucket_lines[key],
            )
            for key, label in AGED_STOCK_BUCKET_SPECS
        ]
        total_qty = sum(bucket_qty.values())
        total_value = sum(bucket_value.values(), Decimal(0))

        return AgedStockReport(
            buckets=buckets,
            total_qty=total_qty,
            total_value_zar=total_value.quantize(Decimal("0.01")),
        )

    async def sales_by_sku(
        self, from_date: datetime.date, to_date: datetime.date
    ) -> SalesBySkuReport:
        if from_date > to_date:
            raise ValueError("from_date must be on or before to_date")

        result = await self.db.execute(
            select(
                InvoiceLine.sku_id,
                Sku.our_ref,
                Sku.name,
                func.coalesce(func.sum(InvoiceLine.qty), 0),
                func.coalesce(func.sum(InvoiceLine.ex_vat), 0),
                func.coalesce(func.sum(InvoiceLine.inc_vat), 0),
            )
            .join(TaxInvoice, InvoiceLine.invoice_id == TaxInvoice.id)
            .join(Sku, InvoiceLine.sku_id == Sku.id)
            .where(
                and_(
                    InvoiceLine.sku_id.isnot(None),
                    TaxInvoice.issue_date >= from_date,
                    TaxInvoice.issue_date <= to_date,
                )
            )
            .group_by(InvoiceLine.sku_id, Sku.our_ref, Sku.name)
            .order_by(Sku.our_ref)
        )

        lines: list[SalesBySkuLine] = []
        total_qty = 0
        total_ex = Decimal(0)
        total_inc = Decimal(0)

        for sku_id, our_ref, name, qty, ex_vat, inc_vat in result.all():
            qty_int = int(qty)
            ex = Decimal(ex_vat)
            inc = Decimal(inc_vat)
            total_qty += qty_int
            total_ex += ex
            total_inc += inc
            lines.append(
                SalesBySkuLine(
                    sku_id=sku_id,
                    our_ref=our_ref,
                    name=name,
                    qty=qty_int,
                    ex_vat_zar=ex,
                    inc_vat_zar=inc,
                )
            )

        return SalesBySkuReport(
            from_date=from_date,
            to_date=to_date,
            lines=lines,
            total_qty=total_qty,
            total_ex_vat_zar=total_ex,
            total_inc_vat_zar=total_inc,
        )

    async def sales_vat(self, from_date: datetime.date, to_date: datetime.date) -> SalesVatReport:
        if from_date > to_date:
            raise ValueError("from_date must be on or before to_date")

        result = await self.db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(TaxInvoice.subtotal_ex_vat), 0),
                func.coalesce(func.sum(TaxInvoice.vat_amount), 0),
                func.coalesce(func.sum(TaxInvoice.total_inc_vat), 0),
                func.coalesce(func.sum(TaxInvoice.amount_paid), 0),
            ).where(
                and_(
                    TaxInvoice.issue_date >= from_date,
                    TaxInvoice.issue_date <= to_date,
                )
            )
        )
        invoice_count, subtotal, vat_amount, total_inc, amount_paid = result.one()

        return SalesVatReport(
            from_date=from_date,
            to_date=to_date,
            invoice_count=int(invoice_count),
            subtotal_ex_vat=Decimal(subtotal),
            vat_amount=Decimal(vat_amount),
            total_inc_vat=Decimal(total_inc),
            amount_paid=Decimal(amount_paid),
        )

    async def _period_net(
        self,
        account_id: uuid.UUID,
        from_date: datetime.date,
        to_date: datetime.date,
        *,
        credit_minus_debit: bool,
    ) -> Decimal:
        start_dt = datetime.datetime.combine(from_date, datetime.time.min)
        end_dt = datetime.datetime.combine(to_date, datetime.time.max)

        result = await self.db.execute(
            select(
                func.coalesce(func.sum(JournalLine.debit_zar), 0),
                func.coalesce(func.sum(JournalLine.credit_zar), 0),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .where(
                and_(
                    JournalLine.account_id == account_id,
                    JournalEntry.created_at >= start_dt,
                    JournalEntry.created_at <= end_dt,
                )
            )
        )
        debits, credits = result.one()
        debits = Decimal(debits)
        credits = Decimal(credits)
        if credit_minus_debit:
            return credits - debits
        return debits - credits

    async def _balance_as_of(self, account_id: uuid.UUID, as_of: datetime.date) -> Decimal:
        end_dt = datetime.datetime.combine(as_of, datetime.time.max)
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(JournalLine.debit_zar), 0)
                - func.coalesce(func.sum(JournalLine.credit_zar), 0),
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .where(
                and_(
                    JournalLine.account_id == account_id,
                    JournalEntry.created_at <= end_dt,
                )
            )
        )
        return Decimal(result.scalar_one())
