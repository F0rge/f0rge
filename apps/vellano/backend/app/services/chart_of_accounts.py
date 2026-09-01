from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.account import AccountCRUD
from app.crud.category_account_map import CategoryAccountMapCRUD
from app.models.account import Account, AccountType, default_tax_treatment
from app.models.category_account_map import CategoryAccountMap
from app.models.journal import JournalDocumentType, JournalEntry, JournalLine, JournalStatus
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

# Seeded chart-of-accounts codes (S6).
CODE_BANK = "1100"
CODE_AR = "1200"
CODE_INVENTORY = "1300"
CODE_AP = "2100"
CODE_VAT = "2200"
CODE_DEPOSITS = "2300"
CODE_OPENING = "3000"
CODE_SALES = "4000"
CODE_COGS = "5000"
CODE_FX = "6100"

CHART_OF_ACCOUNTS: tuple[tuple[str, str, AccountType], ...] = (
    (CODE_BANK, "Bank", AccountType.ASSET),
    (CODE_AR, "Accounts receivable", AccountType.ASSET),
    (CODE_INVENTORY, "Inventory", AccountType.ASSET),
    (CODE_AP, "Accounts payable", AccountType.LIABILITY),
    (CODE_VAT, "VAT control", AccountType.LIABILITY),
    (CODE_DEPOSITS, "Customer deposits", AccountType.LIABILITY),
    (CODE_OPENING, "Opening balances", AccountType.EQUITY),
    (CODE_SALES, "Sales", AccountType.INCOME),
    (CODE_COGS, "Cost of goods sold", AccountType.EXPENSE),
    (CODE_FX, "Foreign exchange gain/loss", AccountType.EXPENSE),
)

# Furniture retail category P&L accounts (B1). 4000/5000 stay as unmapped fallbacks.
CATEGORY_ACCOUNTS: tuple[tuple[str, str, AccountType], ...] = (
    ("4010", "Sales – Seating", AccountType.INCOME),
    ("4020", "Sales – Tables", AccountType.INCOME),
    ("4030", "Sales – Storage", AccountType.INCOME),
    ("4040", "Sales – Decor", AccountType.INCOME),
    ("4050", "Sales – Bedroom", AccountType.INCOME),
    ("4060", "Sales – Dining", AccountType.INCOME),
    ("4070", "Sales – Outdoor", AccountType.INCOME),
    ("5010", "COGS – Seating", AccountType.EXPENSE),
    ("5020", "COGS – Tables", AccountType.EXPENSE),
    ("5030", "COGS – Storage", AccountType.EXPENSE),
    ("5040", "COGS – Decor", AccountType.EXPENSE),
    ("5050", "COGS – Bedroom", AccountType.EXPENSE),
    ("5060", "COGS – Dining", AccountType.EXPENSE),
    ("5070", "COGS – Outdoor", AccountType.EXPENSE),
    ("5110", "Stock adj – Seating", AccountType.EXPENSE),
    ("5120", "Stock adj – Tables", AccountType.EXPENSE),
    ("5130", "Stock adj – Storage", AccountType.EXPENSE),
    ("5140", "Stock adj – Decor", AccountType.EXPENSE),
    ("5150", "Stock adj – Bedroom", AccountType.EXPENSE),
    ("5160", "Stock adj – Dining", AccountType.EXPENSE),
    ("5170", "Stock adj – Outdoor", AccountType.EXPENSE),
    ("5210", "Count var – Seating", AccountType.EXPENSE),
    ("5220", "Count var – Tables", AccountType.EXPENSE),
    ("5230", "Count var – Storage", AccountType.EXPENSE),
    ("5240", "Count var – Decor", AccountType.EXPENSE),
    ("5250", "Count var – Bedroom", AccountType.EXPENSE),
    ("5260", "Count var – Dining", AccountType.EXPENSE),
    ("5270", "Count var – Outdoor", AccountType.EXPENSE),
)

# (category, sales_code, cogs_code, stock_adj_code, count_var_code)
CATEGORY_MAPS: tuple[tuple[str, str, str, str, str], ...] = (
    ("Seating", "4010", "5010", "5110", "5210"),
    ("Tables", "4020", "5020", "5120", "5220"),
    ("Storage", "4030", "5030", "5130", "5230"),
    ("Decor", "4040", "5040", "5140", "5240"),
    ("Bedroom", "4050", "5050", "5150", "5250"),
    ("Dining", "4060", "5060", "5160", "5260"),
    ("Outdoor", "4070", "5070", "5170", "5270"),
)


class ChartOfAccountsSeedService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = AccountCRUD(db)
        self.map_crud = CategoryAccountMapCRUD(db)

    async def seed_if_empty(self) -> None:
        if await self.crud.count() > 0:
            return

        async with unit_of_work(self.db):
            for code, name, account_type in CHART_OF_ACCOUNTS:
                await self.crud.add_and_flush(self._system_account(code, name, account_type))

    async def ensure_opening_equity(self) -> None:
        if await self.crud.get_by_code(CODE_OPENING) is not None:
            return
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(
                self._system_account(CODE_OPENING, "Opening balances", AccountType.EQUITY)
            )

    async def ensure_customer_deposits(self) -> None:
        if await self.crud.get_by_code(CODE_DEPOSITS) is not None:
            return
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(
                self._system_account(CODE_DEPOSITS, "Customer deposits", AccountType.LIABILITY)
            )

    async def ensure_category_chart(self) -> None:
        async with unit_of_work(self.db):
            for code, name, account_type in CATEGORY_ACCOUNTS:
                if await self.crud.get_by_code(code) is None:
                    await self.crud.add_and_flush(self._system_account(code, name, account_type))
            for category, sales_code, cogs_code, stock_adj_code, count_var_code in CATEGORY_MAPS:
                if await self.map_crud.get_by_category_insensitive(category) is None:
                    await self.map_crud.add_and_flush(
                        CategoryAccountMap(
                            category=category,
                            sales_code=sales_code,
                            cogs_code=cogs_code,
                            stock_adj_code=stock_adj_code,
                            count_var_code=count_var_code,
                        )
                    )

    @staticmethod
    def _system_account(code: str, name: str, account_type: AccountType) -> Account:
        return Account(
            code=code,
            name=name,
            type=account_type,
            is_system=True,
            tax_treatment=default_tax_treatment(account_type),
        )


class LedgerPostingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.account_crud = AccountCRUD(db)

    async def post(
        self,
        document_type: JournalDocumentType,
        document_id: uuid.UUID,
        memo: Optional[str],
        lines: list[tuple[str, Decimal, Decimal]],
        *,
        entry_date: Optional[datetime.date] = None,
        source: Optional[str] = None,
    ) -> JournalEntry:
        """Post a balanced journal. Each line: (account_code, debit_zar, credit_zar)."""
        total_debit = Decimal(0)
        total_credit = Decimal(0)
        for _, debit, credit in lines:
            total_debit += debit
            total_credit += credit

        if total_debit != total_credit:
            raise ValidationError("Journal entry must balance")

        entry = JournalEntry(
            document_type=document_type,
            document_id=document_id,
            memo=memo,
            status=JournalStatus.POSTED,
            entry_date=entry_date or datetime.date.today(),
            source=source,
        )
        await self.account_crud.add_and_flush(entry)

        for account_code, debit, credit in lines:
            account = await self.account_crud.get_by_code(account_code)
            if account is None:
                raise NotFoundError(f"Account {account_code} not found")
            journal_line = JournalLine(
                entry_id=entry.id,
                account_id=account.id,
                debit_zar=debit,
                credit_zar=credit,
            )
            await self.account_crud.add_and_flush(journal_line)

        return entry
