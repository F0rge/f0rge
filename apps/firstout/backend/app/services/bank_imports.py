from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.account import AccountCRUD
from app.crud.bank_import import BankImportCRUD, BankImportLineCRUD
from app.crud.bank_rule import BankRuleCRUD
from app.crud.journal import JournalCRUD
from app.crud.payment import PaymentCRUD
from app.models.account import Account
from app.models.bank_import import BankImport, BankImportLine, BankImportLineAllocation
from app.models.bank_rule import BankRule
from app.models.bill import Bill
from app.models.tax_invoice import TaxInvoice
from app.models.journal import JournalDocumentType, JournalStatus
from app.schemas.bank_import import (
    AutoMatchConfirmRequest,
    AutoMatchConfirmResult,
    AutoMatchPreview,
    AutoMatchPreviewItem,
    BankApplyRuleRequest,
    BankDocumentSuggestion,
    BankImportLineResponse,
    BankImportMatchRequest,
    BankImportResponse,
    BankImportSummary,
    BankLineAllocationResponse,
    BankMatchDocumentRequest,
    BankRecodeRequest,
    BankSplitRequest,
    BankUnmatchedCount,
)
from app.schemas.journal import JournalCreate, JournalLineCreate
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.bank_match_rank import OpenDocument, rank_documents, unique_auto_match
from app.services.payment_terms import invoice_collectible_balance, invoice_open_balance_expr
from app.services.settlement import cents
from app.services.bank_csv import parse_bank_csv
from app.services.chart_of_accounts import CODE_BANK
from app.services.journals import JournalService
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
        self.rule_crud = BankRuleCRUD(db)
        self.journals = JournalService(db)

    async def list(self) -> list[BankImportSummary]:
        imports = await self.crud.list_all()
        return [self._to_summary(bank_import) for bank_import in imports]

    async def get(self, import_id: uuid.UUID) -> BankImportResponse:
        return await self._to_response(await self._require_import(import_id))

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
        bank_import = await self._require_import(import_id)
        line = self._require_unmatched_line(bank_import, line_id)

        if data.payment_id is not None:
            await self._match_payment(line, data.payment_id)
        else:
            assert data.journal_id is not None
            await self._match_journal(bank_import, line, data.journal_id)

        reloaded = await self.line_crud.get_by_id(line_id)
        assert reloaded is not None
        return await self._line_to_response(reloaded)

    async def apply_rule(
        self,
        import_id: uuid.UUID,
        line_id: uuid.UUID,
        data: BankApplyRuleRequest,
    ) -> BankImportLineResponse:
        bank_import = await self._require_import(import_id)
        line = self._require_unmatched_line(bank_import, line_id)
        rule = await self.rule_crud.get_by_id(data.rule_id)
        if rule is None:
            raise NotFoundError("Bank rule not found")
        if not rule.is_active:
            raise ValidationError("Bank rule is not active")
        if rule.bank_account_id != bank_import.account_id:
            raise ValidationError("Bank rule does not belong to this bank account")
        if line.amount_zar == 0:
            raise ValidationError("Bank line amount cannot be zero")

        amount = abs(line.amount_zar)
        zero = Decimal("0")
        if line.amount_zar > 0:
            journal_lines = [
                JournalLineCreate(
                    account_id=bank_import.account_id, debit_zar=amount, credit_zar=zero
                ),
                JournalLineCreate(
                    account_id=rule.target_account_id, debit_zar=zero, credit_zar=amount
                ),
            ]
        else:
            journal_lines = [
                JournalLineCreate(
                    account_id=rule.target_account_id, debit_zar=amount, credit_zar=zero
                ),
                JournalLineCreate(
                    account_id=bank_import.account_id, debit_zar=zero, credit_zar=amount
                ),
            ]

        journal = await self.journals.create(
            JournalCreate(
                entry_date=line.transaction_date,
                memo=line.description,
                source="bank-rule",
                status=JournalStatus.POSTED,
                lines=journal_lines,
            )
        )
        await self._match_journal(bank_import, line, journal.id)
        reloaded = await self.line_crud.get_by_id(line_id)
        assert reloaded is not None
        return await self._line_to_response(reloaded)

    async def recode(
        self,
        import_id: uuid.UUID,
        line_id: uuid.UUID,
        data: BankRecodeRequest,
    ) -> BankImportLineResponse:
        bank_import = await self._require_import(import_id)
        line = self._require_line(bank_import, line_id)
        if line.matched_payment_id is not None:
            raise ValidationError("Cannot recode a payment match")
        if line.matched_journal_id is None:
            raise ValidationError("Line is not matched to a journal")

        journal = await self.journal_crud.get_entry_by_id(line.matched_journal_id)
        if journal is None:
            raise NotFoundError("Journal not found")
        if journal.document_type != JournalDocumentType.MANUAL:
            raise ValidationError("Line is not matched to a manual journal")
        if journal.status == JournalStatus.VOIDED:
            raise ValidationError("Journal is voided")
        if journal.status != JournalStatus.POSTED:
            raise ValidationError("Journal is not posted")

        counterparties = [
            journal_line
            for journal_line in journal.lines
            if journal_line.account_id != bank_import.account_id
        ]
        if len(counterparties) != 1:
            raise ValidationError("Journal must have exactly one non-bank line")

        target = await self.account_crud.get_by_id(data.account_id)
        if target is None:
            raise NotFoundError("Account not found")
        if target.id == bank_import.account_id:
            raise ValidationError("Target account cannot be the bank account")

        async with unit_of_work(self.db):
            counterparties[0].account_id = target.id

        reloaded = await self.line_crud.get_by_id(line_id)
        assert reloaded is not None
        return await self._line_to_response(reloaded)

    async def list_unmatched_lines(
        self, account_id: Optional[uuid.UUID] = None
    ) -> list[BankImportLineResponse]:
        lines = await self.line_crud.list_unmatched(account_id)
        rules_cache: dict[uuid.UUID, list[BankRule]] = {}
        responses: list[BankImportLineResponse] = []
        for line in lines:
            aid = line.bank_import.account_id
            if aid not in rules_cache:
                rules_cache[aid] = await self.rule_crud.list_active_for_account(aid)
            responses.append(await self._line_to_response(line, rules=rules_cache[aid]))
        return responses

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

    async def _require_import(self, import_id: uuid.UUID) -> BankImport:
        bank_import = await self.crud.get_by_id(import_id)
        if bank_import is None:
            raise NotFoundError("Bank import not found")
        return bank_import

    def _require_line(self, bank_import: BankImport, line_id: uuid.UUID) -> BankImportLine:
        line = next((entry for entry in bank_import.lines if entry.id == line_id), None)
        if line is None:
            raise NotFoundError("Bank import line not found")
        return line

    def _require_unmatched_line(
        self, bank_import: BankImport, line_id: uuid.UUID
    ) -> BankImportLine:
        line = self._require_line(bank_import, line_id)
        if self._is_matched(line):
            raise ValidationError("Line is already matched")
        return line

    async def _to_response(self, bank_import: BankImport) -> BankImportResponse:
        rules = await self.rule_crud.list_active_for_account(bank_import.account_id)
        line_responses = [
            await self._line_to_response(line, rules=rules) for line in bank_import.lines
        ]
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

    async def _line_to_response(
        self,
        line: BankImportLine,
        *,
        rules: Optional[list[BankRule]] = None,
    ) -> BankImportLineResponse:
        matched_payment_number = None
        if line.matched_payment is not None:
            matched_payment_number = line.matched_payment.payment_number

        suggested = await self._suggest_payment(line)
        rule = await self._suggest_rule(line, rules)
        suggestions = await self._document_suggestions(line)
        return BankImportLineResponse(
            id=line.id,
            import_id=line.import_id,
            transaction_date=line.transaction_date,
            description=line.description,
            reference=line.reference,
            amount_zar=line.amount_zar,
            matched_payment_id=line.matched_payment_id,
            matched_journal_id=line.matched_journal_id,
            matched_payment_number=matched_payment_number,
            suggested_payment_id=suggested.id if suggested else None,
            suggested_payment_number=suggested.payment_number if suggested else None,
            suggested_rule_id=rule.id if rule else None,
            suggested_rule_pattern=rule.pattern if rule else None,
            suggested_account_code=rule.target_account.code if rule else None,
            suggested_account_name=rule.target_account.name if rule else None,
            document_suggestions=suggestions,
            allocations=[
                BankLineAllocationResponse(
                    payment_id=allocation.payment_id,
                    amount_zar=allocation.amount_zar,
                    document_number=allocation.document_number,
                )
                for allocation in getattr(line, "allocations", []) or []
            ],
        )

    async def _suggest_rule(
        self,
        line: BankImportLine,
        rules: Optional[list[BankRule]],
    ) -> Optional[BankRule]:
        if self._is_matched(line):
            return None
        if rules is None:
            account_id = line.bank_import.account_id if line.bank_import is not None else None
            if account_id is None:
                return None
            rules = await self.rule_crud.list_active_for_account(account_id)
        return self._first_matching_rule(line.description, rules)

    @staticmethod
    def _first_matching_rule(description: str, rules: list[BankRule]) -> Optional[BankRule]:
        haystack = description.lower()
        for rule in rules:
            if rule.pattern.lower() in haystack:
                return rule
        return None

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

    async def match_document(
        self,
        import_id: uuid.UUID,
        line_id: uuid.UUID,
        data: BankMatchDocumentRequest,
        user_id: uuid.UUID,
    ) -> BankImportLineResponse:
        bank_import = await self._require_import(import_id)
        line = self._require_unmatched_line(bank_import, line_id)
        payment, number = await self._create_document_payment(
            line,
            invoice_id=data.invoice_id,
            bill_id=data.bill_id,
            amount=cents(abs(line.amount_zar)),
            user_id=user_id,
        )
        await self._reconcile_payments(line, [(payment.id, payment.amount_zar, number)])
        reloaded = await self.line_crud.get_by_id(line_id)
        assert reloaded is not None
        return await self._line_to_response(reloaded)

    async def split_line(
        self,
        import_id: uuid.UUID,
        line_id: uuid.UUID,
        data: BankSplitRequest,
        user_id: uuid.UUID,
    ) -> BankImportLineResponse:
        bank_import = await self._require_import(import_id)
        line = self._require_unmatched_line(bank_import, line_id)
        bank_abs = cents(abs(line.amount_zar))
        total = cents(sum((cents(item.amount) for item in data.allocations), Decimal(0)))
        if total != bank_abs:
            raise ValidationError(f"Split amounts must add up to the bank line of {bank_abs}.")
        money_in = line.amount_zar > 0
        await self._assert_split_fits(data, money_in=money_in)
        created: list[tuple[uuid.UUID, Decimal, str]] = []
        for item in data.allocations:
            if money_in and item.invoice_id is None:
                raise ValidationError("Money in can only be split across customer invoices.")
            if not money_in and item.bill_id is None:
                raise ValidationError("Money out can only be split across supplier bills.")
            payment, number = await self._create_document_payment(
                line,
                invoice_id=item.invoice_id,
                bill_id=item.bill_id,
                amount=cents(item.amount),
                user_id=user_id,
            )
            created.append((payment.id, payment.amount_zar, number))
        await self._reconcile_payments(line, created)
        reloaded = await self.line_crud.get_by_id(line_id)
        assert reloaded is not None
        return await self._line_to_response(reloaded)

    async def auto_match_preview(self, account_id: Optional[uuid.UUID] = None) -> AutoMatchPreview:
        lines = await self.line_crud.list_unmatched(account_id)
        documents = await self._open_documents()
        matches: list[AutoMatchPreviewItem] = []
        for line in lines:
            ranked = rank_documents(
                amount_zar=line.amount_zar,
                transaction_date=line.transaction_date,
                description=line.description,
                reference=line.reference,
                documents=documents,
            )
            chosen = unique_auto_match(ranked)
            if chosen is None:
                continue
            matches.append(self._preview_item(line, chosen))
        return AutoMatchPreview(matches=matches)

    async def auto_match_confirm(
        self,
        data: AutoMatchConfirmRequest,
        user_id: uuid.UUID,
    ) -> AutoMatchConfirmResult:
        applied: list[AutoMatchPreviewItem] = []
        skipped: list[str] = []
        documents = await self._open_documents()
        for line_id in data.line_ids:
            line = await self.line_crud.get_by_id(line_id)
            if line is None or self._is_matched(line):
                skipped.append(f"{line_id} is no longer unmatched")
                continue
            ranked = rank_documents(
                amount_zar=line.amount_zar,
                transaction_date=line.transaction_date,
                description=line.description,
                reference=line.reference,
                documents=documents,
            )
            chosen = unique_auto_match(ranked)
            if chosen is None:
                skipped.append(f"{line_id} is not an exact reference match")
                continue
            invoice_id = chosen.document.document_id if chosen.document.kind == "invoice" else None
            bill_id = chosen.document.document_id if chosen.document.kind == "bill" else None
            payment, number = await self._create_document_payment(
                line,
                invoice_id=invoice_id,
                bill_id=bill_id,
                amount=cents(abs(line.amount_zar)),
                user_id=user_id,
            )
            await self._reconcile_payments(line, [(payment.id, payment.amount_zar, number)])
            applied.append(self._preview_item(line, chosen))
            documents = [doc for doc in documents if doc.document_id != chosen.document.document_id]
        return AutoMatchConfirmResult(applied=applied, skipped=skipped)

    async def _create_document_payment(
        self,
        line: BankImportLine,
        *,
        invoice_id: Optional[uuid.UUID],
        bill_id: Optional[uuid.UUID],
        amount: Decimal,
        user_id: uuid.UUID,
    ):
        payments = PaymentService(self.db)
        if invoice_id is not None:
            if line.amount_zar <= 0:
                raise ValidationError("A customer invoice can only match money in.")
            payment = await payments.create(
                PaymentCreate(
                    direction="in",
                    invoice_id=invoice_id,
                    amount=amount,
                    currency="ZAR",
                    paid_on=line.transaction_date,
                ),
                user_id,
            )
            invoice = await self.db.get(TaxInvoice, invoice_id)
            number = invoice.invoice_number if invoice is not None else payment.payment_number
            return payment, number
        if bill_id is None:
            raise ValidationError("Choose an invoice or a bill.")
        if line.amount_zar >= 0:
            raise ValidationError("A supplier bill can only match money out.")
        bill = await self.db.get(Bill, bill_id)
        if bill is None:
            raise NotFoundError("Bill not found")
        pay_amount = amount
        if bill.currency.upper() != "ZAR":
            remaining_zar = cents(bill.amount_zar - bill.amount_paid_zar)
            if amount != remaining_zar:
                raise ValidationError(
                    "A foreign bill can only be matched when the bank line equals the rand still owing."
                )
            pay_amount = cents(bill.amount_foreign - bill.amount_paid_foreign)
        payment = await payments.create(
            PaymentCreate(
                direction="out",
                bill_id=bill.id,
                amount=pay_amount,
                currency=bill.currency,
                fx_to_zar=bill.fx_to_zar,
                paid_on=line.transaction_date,
            ),
            user_id,
        )
        return payment, bill.bill_number

    async def _reconcile_payments(
        self,
        line: BankImportLine,
        created: list[tuple[uuid.UUID, Decimal, str]],
    ) -> None:
        now = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            line.matched_payment_id = created[0][0]
            for payment_id, amount_zar, number in created:
                payment = await self.payment_crud.get_by_id(payment_id)
                if payment is None:
                    raise NotFoundError("Payment not found")
                payment.is_reconciled = True
                payment.reconciled_at = now
                self.db.add(
                    BankImportLineAllocation(
                        line_id=line.id,
                        payment_id=payment_id,
                        amount_zar=amount_zar,
                        document_number=number,
                    )
                )
            await self.crud.commit_refresh(line)

    async def _assert_split_fits(self, data: BankSplitRequest, *, money_in: bool) -> None:
        totals: dict[uuid.UUID, Decimal] = {}
        for item in data.allocations:
            document_id = item.invoice_id if money_in else item.bill_id
            if document_id is None:
                continue
            totals[document_id] = cents(totals.get(document_id, Decimal(0)) + cents(item.amount))
        for document_id, amount in totals.items():
            if money_in:
                invoice = (
                    await self.db.execute(
                        select(TaxInvoice)
                        .options(selectinload(TaxInvoice.credit_note))
                        .where(TaxInvoice.id == document_id)
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one_or_none()
                if invoice is None:
                    raise NotFoundError("Invoice not found")
                remaining = cents(invoice_collectible_balance(invoice))
            else:
                bill = await self.db.get(Bill, document_id)
                if bill is None:
                    raise NotFoundError("Bill not found")
                if bill.currency.upper() != "ZAR":
                    raise ValidationError(
                        "Split a foreign bill from the single match, not a split."
                    )
                remaining = cents(bill.amount_foreign - bill.amount_paid_foreign)
            if amount > remaining:
                label = invoice.invoice_number if money_in else bill.bill_number
                raise ValidationError(f"Split is more than the {remaining} still owing on {label}.")

    async def _document_suggestions(self, line: BankImportLine) -> list[BankDocumentSuggestion]:
        if self._is_matched(line):
            return []
        ranked = rank_documents(
            amount_zar=line.amount_zar,
            transaction_date=line.transaction_date,
            description=line.description,
            reference=line.reference,
            documents=await self._open_documents(),
        )
        auto = unique_auto_match(ranked)
        return [
            BankDocumentSuggestion(
                kind=item.document.kind,  # type: ignore[arg-type]
                document_id=item.document.document_id,
                document_number=item.document.number,
                contact_name=item.document.contact_name,
                outstanding_zar=item.document.outstanding_zar,
                confidence=item.confidence,
                reason=item.reason,
                auto_match=auto is not None
                and auto.document.document_id == item.document.document_id,
            )
            for item in ranked
        ]

    async def _open_documents(self) -> list[OpenDocument]:
        cached = getattr(self, "_open_document_cache", None)
        if cached is not None:
            return cached
        open_balance = invoice_open_balance_expr()
        invoices = (
            (
                await self.db.execute(
                    select(TaxInvoice)
                    .options(
                        selectinload(TaxInvoice.customer),
                        selectinload(TaxInvoice.credit_note),
                    )
                    .where(TaxInvoice.is_archive.is_(False))
                    .where(open_balance > 0)
                )
            )
            .scalars()
            .all()
        )
        bills = (
            (
                await self.db.execute(
                    select(Bill)
                    .options(selectinload(Bill.supplier))
                    .where(Bill.is_archive.is_(False))
                    .where(Bill.amount_zar > Bill.amount_paid_zar)
                )
            )
            .scalars()
            .all()
        )
        documents = [
            OpenDocument(
                kind="invoice",
                document_id=invoice.id,
                number=invoice.invoice_number,
                contact_name=invoice.customer.name,
                outstanding_zar=cents(invoice_collectible_balance(invoice)),
                issue_date=invoice.issue_date,
                currency="ZAR",
                outstanding_foreign=cents(invoice_collectible_balance(invoice)),
                fx_to_zar=Decimal("1"),
            )
            for invoice in invoices
        ]
        documents.extend(
            OpenDocument(
                kind="bill",
                document_id=bill.id,
                number=bill.bill_number,
                contact_name=bill.supplier.name,
                outstanding_zar=cents(bill.amount_zar - bill.amount_paid_zar),
                issue_date=bill.issue_date,
                currency=bill.currency,
                outstanding_foreign=cents(bill.amount_foreign - bill.amount_paid_foreign),
                fx_to_zar=bill.fx_to_zar,
            )
            for bill in bills
        )
        self._open_document_cache = documents
        return documents

    @staticmethod
    def _preview_item(line: BankImportLine, chosen) -> AutoMatchPreviewItem:
        return AutoMatchPreviewItem(
            import_id=line.import_id,
            line_id=line.id,
            transaction_date=line.transaction_date,
            description=line.description,
            amount_zar=line.amount_zar,
            kind=chosen.document.kind,  # type: ignore[arg-type]
            document_id=chosen.document.document_id,
            document_number=chosen.document.number,
            contact_name=chosen.document.contact_name,
            confidence=chosen.confidence,
            reason=chosen.reason,
        )
