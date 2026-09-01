from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.account import AccountCRUD
from app.models.account import Account, AccountType
from app.models.journal import JournalDocumentType, JournalEntry, JournalLine
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

# Seeded chart-of-accounts codes (S6).
CODE_BANK = "1100"
CODE_AR = "1200"
CODE_INVENTORY = "1300"
CODE_AP = "2100"
CODE_VAT = "2200"
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
    (CODE_OPENING, "Opening balances", AccountType.EQUITY),
    (CODE_SALES, "Sales", AccountType.INCOME),
    (CODE_COGS, "Cost of goods sold", AccountType.EXPENSE),
    (CODE_FX, "Foreign exchange gain/loss", AccountType.EXPENSE),
)


class ChartOfAccountsSeedService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = AccountCRUD(db)

    async def seed_if_empty(self) -> None:
        if await self.crud.count() > 0:
            return

        async with unit_of_work(self.db):
            for code, name, account_type in CHART_OF_ACCOUNTS:
                account = Account(
                    code=code,
                    name=name,
                    type=account_type,
                    is_system=True,
                )
                await self.crud.add_and_flush(account)

    async def ensure_opening_equity(self) -> None:
        if await self.crud.get_by_code(CODE_OPENING) is not None:
            return
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(
                Account(
                    code=CODE_OPENING,
                    name="Opening balances",
                    type=AccountType.EQUITY,
                    is_system=True,
                )
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
