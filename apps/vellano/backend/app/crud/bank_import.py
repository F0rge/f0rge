from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
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
                    selectinload(BankImport.lines).selectinload(BankImportLine.matched_payment)
                )
                .where(BankImport.id == import_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[BankImport]:
        result = await self.db.execute(
            select(BankImport)
            .options(selectinload(BankImport.lines))
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

    async def list_unmatched(self) -> list[BankImportLine]:
        result = await self.db.execute(
            select(BankImportLine)
            .where(BankImportLine.matched_payment_id.is_(None))
            .order_by(BankImportLine.transaction_date.desc())
        )
        return list(result.scalars().all())
