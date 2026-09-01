from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.account import AccountCRUD
from app.crud.journal import JournalCRUD
from app.models.journal import (
    JournalDocumentType,
    JournalEntry,
    JournalLine,
    JournalStatus,
)
from app.schemas.journal import (
    JournalCreate,
    JournalLineCreate,
    JournalLineResponse,
    JournalResponse,
)
from app.services.vat import CENT
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class JournalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = JournalCRUD(db)
        self.account_crud = AccountCRUD(db)

    async def list(self) -> list[JournalResponse]:
        return [self._to_response(entry) for entry in await self.crud.list_all()]

    async def get(self, journal_id: uuid.UUID) -> JournalResponse:
        return self._to_response(await self._get_or_404(journal_id))

    async def create(self, data: JournalCreate) -> JournalResponse:
        if data.status == JournalStatus.VOIDED:
            raise ValidationError("Cannot create a voided journal")
        amounts = self._validated_line_amounts(data.lines)
        entry_id = uuid.uuid4()
        journal_number = await self.crud.get_next_journal_number()
        entry = JournalEntry(
            id=entry_id,
            document_type=JournalDocumentType.MANUAL,
            document_id=entry_id,
            memo=data.memo,
            status=data.status,
            entry_date=data.entry_date,
            source=data.source,
            journal_number=journal_number,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(entry)
            for line, debit, credit in amounts:
                account = await self.account_crud.get_by_id(line.account_id)
                if account is None:
                    raise NotFoundError("Account not found")
                await self.crud.add_line(
                    JournalLine(
                        entry_id=entry.id,
                        account_id=account.id,
                        debit_zar=debit,
                        credit_zar=credit,
                    )
                )

        return self._to_response(await self._get_or_404(entry.id))

    async def post(self, journal_id: uuid.UUID) -> JournalResponse:
        entry = await self._get_or_404(journal_id)
        if entry.status != JournalStatus.DRAFT:
            raise ValidationError("Journal is not a draft")
        async with unit_of_work(self.db):
            entry.status = JournalStatus.POSTED
        return self._to_response(await self._get_or_404(entry.id))

    async def void(self, journal_id: uuid.UUID) -> JournalResponse:
        entry = await self._get_or_404(journal_id)
        if entry.document_type != JournalDocumentType.MANUAL:
            raise ValidationError("Only manual journals can be voided")
        if entry.status != JournalStatus.POSTED:
            raise ValidationError("Only posted journals can be voided")

        reversing_id = uuid.uuid4()
        reversing_number = await self.crud.get_next_journal_number()
        reversing = JournalEntry(
            id=reversing_id,
            document_type=JournalDocumentType.MANUAL,
            document_id=reversing_id,
            memo=f"Void of {entry.journal_number}",
            status=JournalStatus.POSTED,
            entry_date=entry.entry_date,
            source="void",
            journal_number=reversing_number,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(reversing)
            for line in entry.lines:
                await self.crud.add_line(
                    JournalLine(
                        entry_id=reversing.id,
                        account_id=line.account_id,
                        debit_zar=line.credit_zar,
                        credit_zar=line.debit_zar,
                    )
                )
            entry.status = JournalStatus.VOIDED
            entry.voided_by_id = reversing.id

        return self._to_response(await self._get_or_404(entry.id))

    async def _get_or_404(self, journal_id: uuid.UUID) -> JournalEntry:
        entry = await self.crud.get_entry_by_id(journal_id)
        if entry is None:
            raise NotFoundError("Journal not found")
        return entry

    @staticmethod
    def _validated_line_amounts(
        lines: list[JournalLineCreate],
    ) -> list[tuple[JournalLineCreate, Decimal, Decimal]]:
        if len(lines) < 2:
            raise ValidationError("Journal must have at least two lines")
        amounts: list[tuple[JournalLineCreate, Decimal, Decimal]] = []
        total_debit = Decimal(0)
        total_credit = Decimal(0)
        for line in lines:
            debit = line.debit_zar.quantize(CENT, rounding=ROUND_HALF_UP)
            credit = line.credit_zar.quantize(CENT, rounding=ROUND_HALF_UP)
            if (debit > 0 and credit == 0) or (credit > 0 and debit == 0):
                amounts.append((line, debit, credit))
                total_debit += debit
                total_credit += credit
                continue
            raise ValidationError("Each line must be debit or credit, not both")
        if total_debit != total_credit:
            raise ValidationError("Journal entry must balance")
        return amounts

    @staticmethod
    def _to_response(entry: JournalEntry) -> JournalResponse:
        line_responses = [
            JournalLineResponse(
                id=line.id,
                account_id=line.account_id,
                account_code=line.account.code,
                account_name=line.account.name,
                debit_zar=line.debit_zar,
                credit_zar=line.credit_zar,
            )
            for line in entry.lines
        ]
        debit_total = sum((line.debit_zar for line in entry.lines), Decimal(0))
        credit_total = sum((line.credit_zar for line in entry.lines), Decimal(0))
        return JournalResponse(
            id=entry.id,
            document_type=entry.document_type,
            document_id=entry.document_id,
            memo=entry.memo,
            status=entry.status,
            source=entry.source,
            journal_number=entry.journal_number,
            entry_date=entry.entry_date,
            voided_by_id=entry.voided_by_id,
            debit_total_zar=debit_total,
            credit_total_zar=credit_total,
            lines=line_responses,
            created_at=entry.created_at,
        )
