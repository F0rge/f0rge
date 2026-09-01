from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.account import AccountCRUD
from app.models.account import AccountType
from app.models.bill import Bill
from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.journal import JournalEntry, JournalLine
from app.models.supplier import Supplier
from app.models.tax_invoice import TaxInvoice
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
