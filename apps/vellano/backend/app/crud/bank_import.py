from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bank_import import BankImport, BankImportLine
from f0rge_db.crud import BaseCRUD


class BankImportCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, import_id: uuid.UUID) -> Optional[BankImport]:
        return (
            await self.db.execute(
                select(BankImport)
                .options(
                    selectinload(BankImport.account),
                    selectinload(BankImport.lines).selectinload(BankImportLine.matched_payment),
                )
                .where(BankImport.id == import_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[BankImport]:
        result = await self.db.execute(
            select(BankImport)
            .options(
                selectinload(BankImport.account),
                selectinload(BankImport.lines),
            )
            .order_by(BankImport.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_line_by_id(self, line_id: uuid.UUID) -> Optional[BankImportLine]:
        return (
            await self.db.execute(
                select(BankImportLine)
                .options(selectinload(BankImportLine.matched_payment))
                .where(BankImportLine.id == line_id)
            )
        ).scalar_one_or_none()


class BankImportLineCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, line_id: uuid.UUID) -> Optional[BankImportLine]:
        return (
            await self.db.execute(
                select(BankImportLine)
                .options(selectinload(BankImportLine.matched_payment))
                .where(BankImportLine.id == line_id)
            )
        ).scalar_one_or_none()

    async def list_unmatched(self, account_id: Optional[uuid.UUID] = None) -> list[BankImportLine]:
        stmt = (
            select(BankImportLine)
            .join(BankImport, BankImportLine.import_id == BankImport.id)
            .where(
                BankImportLine.matched_payment_id.is_(None),
                BankImportLine.matched_journal_id.is_(None),
            )
            .order_by(BankImportLine.transaction_date.desc())
        )
        if account_id is not None:
            stmt = stmt.where(BankImport.account_id == account_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def unmatched_counts_by_account(self) -> dict[uuid.UUID, int]:
        result = await self.db.execute(
            select(BankImport.account_id, func.count())
            .select_from(BankImportLine)
            .join(BankImport, BankImportLine.import_id == BankImport.id)
            .where(
                BankImportLine.matched_payment_id.is_(None),
                BankImportLine.matched_journal_id.is_(None),
            )
            .group_by(BankImport.account_id)
        )
        return {row[0]: int(row[1]) for row in result.all()}
