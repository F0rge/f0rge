from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.account import AccountCRUD
from app.crud.bank_import import BankImportCRUD, BankImportLineCRUD
from app.crud.journal import JournalCRUD
from app.crud.payment import PaymentCRUD
from app.models.account import Account
from app.models.bank_import import BankImport, BankImportLine
from app.models.journal import JournalStatus
from app.schemas.bank_import import (
    BankImportLineResponse,
    BankImportMatchRequest,
    BankImportResponse,
    BankImportSummary,
    BankUnmatchedCount,
)
from app.schemas.payment import PaymentResponse
from app.services.bank_csv import parse_bank_csv
from app.services.chart_of_accounts import CODE_BANK
from app.services.payments import PaymentService
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class BankImportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = BankImportCRUD(db)
        self.line_crud = BankImportLineCRUD(db)
        self.payment_crud = PaymentCRUD(db)
        self.account_crud = AccountCRUD(db)
        self.journal_crud = JournalCRUD(db)

    async def list(self) -> list[BankImportSummary]:
        imports = await self.crud.list_all()
        return [self._to_summary(bank_import) for bank_import in imports]

    async def get(self, import_id: uuid.UUID) -> BankImportResponse:
        bank_import = await self.crud.get_by_id(import_id)
        if bank_import is None:
            raise NotFoundError("Bank import not found")
        return await self._to_response(bank_import)

    async def create_from_csv(
        self,
        filename: str,
        content: bytes,
        account_id: Optional[uuid.UUID] = None,
    ) -> BankImportResponse:
        parsed_lines = parse_bank_csv(content)
        account = await self._resolve_bank_account(account_id)
        bank_import = BankImport(
            filename=filename,
            line_count=len(parsed_lines),
            account_id=account.id,
        )

        async with unit_of_work(self.db):
            await self.crud.add_and_flush(bank_import)
            for line_data in parsed_lines:
                line = BankImportLine(
                    import_id=bank_import.id,
                    transaction_date=line_data["transaction_date"],  # type: ignore[arg-type]
                    description=line_data["description"],  # type: ignore[arg-type]
                    reference=line_data["reference"],  # type: ignore[arg-type]
                    amount_zar=line_data["amount_zar"],  # type: ignore[arg-type]
                )
                self.db.add(line)
            await self.crud.commit_refresh(bank_import)

        reloaded = await self.crud.get_by_id(bank_import.id)
        assert reloaded is not None
        return await self._to_response(reloaded)

    async def match_line(
        self,
        import_id: uuid.UUID,
        line_id: uuid.UUID,
        data: BankImportMatchRequest,
    ) -> BankImportLineResponse:
        bank_import = await self.crud.get_by_id(import_id)
        if bank_import is None:
            raise NotFoundError("Bank import not found")

        line = next((entry for entry in bank_import.lines if entry.id == line_id), None)
        if line is None:
            raise NotFoundError("Bank import line not found")
        if self._is_matched(line):
            raise ValidationError("Line is already matched")

        if data.payment_id is not None:
            await self._match_payment(line, data.payment_id)
        else:
            assert data.journal_id is not None
            await self._match_journal(bank_import, line, data.journal_id)

        reloaded = await self.line_crud.get_by_id(line_id)
        assert reloaded is not None
        return await self._line_to_response(reloaded)

    async def list_unmatched_lines(
        self, account_id: Optional[uuid.UUID] = None
    ) -> list[BankImportLineResponse]:
        lines = await self.line_crud.list_unmatched(account_id)
        return [await self._line_to_response(line) for line in lines]

    async def unmatched_counts(self) -> list[BankUnmatchedCount]:
        accounts = [account for account in await self.account_crud.list_all() if account.is_bank]
        counts = await self.line_crud.unmatched_counts_by_account()
        return [
            BankUnmatchedCount(
                account_id=account.id,
                account_code=account.code,
                account_name=account.name,
                unmatched_count=counts.get(account.id, 0),
            )
            for account in accounts
        ]

    async def _match_payment(self, line: BankImportLine, payment_id: uuid.UUID) -> None:
        payment = await self.payment_crud.get_by_id(payment_id)
        if payment is None:
            raise NotFoundError("Payment not found")
        if payment.is_reconciled:
            raise ValidationError("Payment is already reconciled")

        expected_amount = (
            payment.amount_zar if payment.direction.value == "in" else -payment.amount_zar
        )
        if line.amount_zar != expected_amount:
            raise ValidationError(
                f"Amount mismatch: bank line {line.amount_zar} vs payment {expected_amount}"
            )

        now = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            line.matched_payment_id = payment.id
            payment.is_reconciled = True
            payment.reconciled_at = now
            await self.crud.commit_refresh(line)

    async def _match_journal(
        self,
        bank_import: BankImport,
        line: BankImportLine,
        journal_id: uuid.UUID,
    ) -> None:
        journal = await self.journal_crud.get_entry_by_id(journal_id)
        if journal is None:
            raise NotFoundError("Journal not found")
        if journal.status != JournalStatus.POSTED:
            raise ValidationError("Journal is not posted")
        if not any(jl.account_id == bank_import.account_id for jl in journal.lines):
            raise ValidationError("Journal has no line on this bank account")

        async with unit_of_work(self.db):
            line.matched_journal_id = journal.id
            await self.crud.commit_refresh(line)

    async def _resolve_bank_account(self, account_id: Optional[uuid.UUID]) -> Account:
        if account_id is None:
            account = await self.account_crud.get_by_code(CODE_BANK)
            if account is None:
                raise NotFoundError("Account 1100 not found")
        else:
            account = await self.account_crud.get_by_id(account_id)
            if account is None:
                raise NotFoundError("Account not found")
        if not account.is_bank:
            raise ValidationError("Account is not a bank reconciliation target")
        return account

    async def _to_response(self, bank_import: BankImport) -> BankImportResponse:
        line_responses = [await self._line_to_response(line) for line in bank_import.lines]
        return BankImportResponse(
            id=bank_import.id,
            filename=bank_import.filename,
            line_count=bank_import.line_count,
            account_id=bank_import.account_id,
            account_code=bank_import.account.code,
            account_name=bank_import.account.name,
            lines=line_responses,
            created_at=bank_import.created_at,
            updated_at=bank_import.updated_at,
        )

    def _to_summary(self, bank_import: BankImport) -> BankImportSummary:
        unmatched_count = sum(1 for line in bank_import.lines if not self._is_matched(line))
        return BankImportSummary(
            id=bank_import.id,
            filename=bank_import.filename,
            line_count=bank_import.line_count,
            matched_count=bank_import.line_count - unmatched_count,
            unmatched_count=unmatched_count,
            account_id=bank_import.account_id,
            account_code=bank_import.account.code,
            account_name=bank_import.account.name,
            created_at=bank_import.created_at,
        )

    async def _line_to_response(self, line: BankImportLine) -> BankImportLineResponse:
        matched_payment_number = None
        if line.matched_payment is not None:
            matched_payment_number = line.matched_payment.payment_number

        suggested = await self._suggest_payment(line)
        return BankImportLineResponse(
            id=line.id,
            transaction_date=line.transaction_date,
            description=line.description,
            reference=line.reference,
            amount_zar=line.amount_zar,
            matched_payment_id=line.matched_payment_id,
            matched_journal_id=line.matched_journal_id,
            matched_payment_number=matched_payment_number,
            suggested_payment_id=suggested.id if suggested else None,
            suggested_payment_number=suggested.payment_number if suggested else None,
        )

    async def _suggest_payment(self, line: BankImportLine) -> Optional[PaymentResponse]:
        if self._is_matched(line):
            return None

        payments = await self.payment_crud.list_all()
        for payment in payments:
            if payment.is_reconciled:
                continue
            expected = (
                payment.amount_zar if payment.direction.value == "in" else -payment.amount_zar
            )
            if expected != line.amount_zar:
                continue
            if abs((payment.paid_on - line.transaction_date).days) <= 3:
                return PaymentService._to_response(payment)
        return None

    @staticmethod
    def _is_matched(line: BankImportLine) -> bool:
        return line.matched_payment_id is not None or line.matched_journal_id is not None
