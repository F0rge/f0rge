from __future__ import annotations

import uuid
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.account import AccountCRUD
from app.crud.journal import JournalCRUD
from app.models.account import Account
from app.models.journal import JournalStatus
from app.schemas.journal import JournalCreate, JournalLineCreate, JournalResponse
from app.schemas.journal_import import (
    JournalImportPreviewLine,
    JournalImportPreviewResponse,
    JournalImportRowError,
)
from app.services.journal_csv import DEFAULT_NARRATION, JournalCsvParse, parse_journal_csv
from app.services.journals import JournalService
from f0rge_core.exceptions import ConflictError, ValidationError

SIMPLEPAY_SOURCE = "import:simplepay"
DUPLICATE_MONTH_MESSAGE = "SimplePay import already exists for this month"


class JournalImportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = JournalCRUD(db)
        self.account_crud = AccountCRUD(db)
        self.journals = JournalService(db)

    async def preview(self, file: UploadFile) -> JournalImportPreviewResponse:
        parsed, errors, _accounts = await self._parse_and_validate(await file.read())
        return JournalImportPreviewResponse(
            lines=[
                JournalImportPreviewLine(
                    row=line.row,
                    account_code=line.account_code,
                    debit_zar=line.debit_zar,
                    credit_zar=line.credit_zar,
                )
                for line in parsed.lines
            ],
            errors=errors,
            balanced=_is_balanced(parsed),
            debit_total=parsed.debit_total,
            credit_total=parsed.credit_total,
            entry_date=parsed.entry_date,
            narration=parsed.narration,
        )

    async def commit(
        self, file: UploadFile, user_id: Optional[uuid.UUID] = None
    ) -> JournalResponse:
        parsed, errors, accounts = await self._parse_and_validate(await file.read())
        if errors:
            raise ValidationError(errors[0].message)
        if parsed.entry_date is None:
            raise ValidationError("date is required")
        existing = await self.crud.get_posted_for_source_month(SIMPLEPAY_SOURCE, parsed.entry_date)
        if existing is not None:
            raise ConflictError(DUPLICATE_MONTH_MESSAGE)
        lines: list[JournalLineCreate] = []
        for line in parsed.lines:
            account = accounts[line.account_code]
            lines.append(
                JournalLineCreate(
                    account_id=account.id,
                    debit_zar=line.debit_zar,
                    credit_zar=line.credit_zar,
                )
            )
        return await self.journals.create(
            JournalCreate(
                entry_date=parsed.entry_date,
                memo=parsed.narration or DEFAULT_NARRATION,
                source=SIMPLEPAY_SOURCE,
                status=JournalStatus.POSTED,
                lines=lines,
            ),
            user_id,
        )

    async def _parse_and_validate(
        self, content: bytes
    ) -> tuple[JournalCsvParse, list[JournalImportRowError], dict[str, Account]]:
        parsed = parse_journal_csv(content)
        errors = [
            JournalImportRowError(row=item.row, message=item.message) for item in parsed.errors
        ]
        accounts: dict[str, Account] = {}
        for line in parsed.lines:
            if not line.account_code or line.account_code in accounts:
                continue
            account = await self.account_crud.get_by_code(line.account_code)
            if account is None:
                errors.append(
                    JournalImportRowError(
                        row=line.row,
                        message=f"Account {line.account_code} not found",
                    )
                )
                continue
            accounts[line.account_code] = account
        return parsed, errors, accounts


def _is_balanced(parsed: JournalCsvParse) -> bool:
    return len(parsed.lines) >= 2 and parsed.debit_total == parsed.credit_total
