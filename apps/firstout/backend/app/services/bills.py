from __future__ import annotations

import asyncio
import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.bill import BillCRUD
from app.crud.supplier import SupplierCRUD
from app.services.party_archive import require_active_supplier
from app.services.archive_documents import assert_operational_document, bill_display_number
from app.models.bill import Bill, BillApprovalStatus, BillAttachment, BillLine
from app.models.books_event import BooksDocumentType, BooksEventAction
from app.models.journal import JournalDocumentType
from app.schemas.bill import (
    BillAttachmentResponse,
    BillCreate,
    BillLineResponse,
    BillListItem,
    BillResponse,
    BillSummary,
    BillUpdate,
)
from app.schemas.page import Page, PageParams
from app.services.books_events import BooksEventService
from app.services.chart_of_accounts import CODE_AP, CODE_INVENTORY, LedgerPostingService
from app.services.document_intake.extract import (
    MAX_UPLOAD_BYTES,
    magic_content_type,
    stored_extension,
)
from app.services.object_storage import delete_object, save_bytes
from app.services.packing_sheet import convert_bill_to_zar
from app.services.settlement import SettlementStatus, cents
from app.services.stored_pdf import media_type_for_storage_key, serve_stored_pdf
from app.services.suppliers import SupplierService
from app.services.vat import CENT
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

DEFAULT_DUE_DAYS = 30
DUE_SOON_DAYS = 7


def bill_status(bill: Bill, today: datetime.date) -> str:
    if bill.is_archive:
        return "unknown"
    if bill.approval_status != BillApprovalStatus.APPROVED:
        return bill.approval_status.value
    if bill.payment_status == SettlementStatus.PAID:
        return "paid"
    if bill.due_date is not None and bill.due_date < today:
        return "overdue"
    return bill.payment_status.value


class BillService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = BillCRUD(db)
        self.supplier_crud = SupplierCRUD(db)
        self.posting = LedgerPostingService(db)
        self.events = BooksEventService(db)

    async def list(self, params: PageParams) -> Page[BillListItem]:
        bills, total = await self.crud.list_page(
            limit=params.limit,
            offset=params.offset,
            q=params.q,
        )
        return Page(
            items=[self._to_list_item(bill) for bill in bills],
            total=total,
        )

    async def list_all(self) -> list[BillListItem]:
        """Live bills for the workspace; Cin7 imports stay in Searchable history."""
        return [
            self._to_list_item(bill) for bill in await self.crud.list_all(include_imported=False)
        ]

    async def get(self, bill_id: uuid.UUID) -> BillResponse:
        return self._to_response(await self._load(bill_id))

    async def get_list_item(self, bill_id: uuid.UUID) -> BillListItem:
        return self._to_list_item(await self._load(bill_id))

    async def summary(self) -> BillSummary:
        today = datetime.date.today()
        soon = today + datetime.timedelta(days=DUE_SOON_DAYS)
        rows = [row for row in await self.list_all() if not row.is_archived]
        owing = [row for row in rows if row.status in {"unpaid", "partially_paid", "overdue"}]
        overdue = [row for row in owing if row.status == "overdue"]
        due_soon = [
            row
            for row in owing
            if row.status != "overdue" and row.due_date and row.due_date <= soon
        ]
        # Awaiting approval is owed too; only drafts are not yet a liability.
        awaiting = [row for row in rows if row.status == "awaiting_approval"]
        return BillSummary(
            owing_zar=cents(sum((row.balance_zar for row in owing + awaiting), Decimal(0))),
            owing_count=len(owing) + len(awaiting),
            overdue_zar=cents(sum((row.balance_zar for row in overdue), Decimal(0))),
            overdue_count=len(overdue),
            due_soon_zar=cents(sum((row.balance_zar for row in due_soon), Decimal(0))),
            due_soon_count=len(due_soon),
            awaiting_approval_count=len(awaiting),
            draft_count=sum(1 for row in rows if row.status == "draft"),
        )

    async def create(
        self,
        data: BillCreate,
        user_id: Optional[uuid.UUID] = None,
        note: Optional[str] = None,
    ) -> BillResponse:
        await require_active_supplier(self.db, data.supplier_id)
        approved = data.approval_status == BillApprovalStatus.APPROVED.value

        currency = SupplierService.normalize_currency(data.currency)
        fx_to_zar = self._resolve_fx(currency, data.fx_to_zar)
        await self._reject_duplicate_supplier_ref(data.supplier_id, data.supplier_ref)

        amount_foreign = Decimal(0)
        line_models: list[BillLine] = []
        for index, line in enumerate(data.lines):
            line_amount = (Decimal(line.qty) * line.unit_amount).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            amount_foreign += line_amount
            line_models.append(
                BillLine(
                    description=line.description,
                    qty=line.qty,
                    unit_amount=line.unit_amount,
                    amount_foreign=line_amount,
                    sort_order=index,
                )
            )

        if amount_foreign <= 0:
            raise ValidationError("Bill total must be positive")

        amount_zar = convert_bill_to_zar(amount_foreign, currency, fx_to_zar)
        bill = Bill(
            bill_number="",
            supplier_id=data.supplier_id,
            supplier_ref=data.supplier_ref,
            issue_date=data.issue_date,
            due_date=data.due_date or data.issue_date + datetime.timedelta(days=DEFAULT_DUE_DAYS),
            currency=currency,
            fx_to_zar=fx_to_zar,
            amount_foreign=amount_foreign,
            amount_zar=amount_zar,
            amount_paid_zar=Decimal(0),
            approval_status=BillApprovalStatus(data.approval_status),
            notes=(data.notes or "").strip() or None,
            lines=line_models,
            attachments=[],
        )

        async with unit_of_work(self.db):
            bill.bill_number = await self.crud.get_next_bill_number()
            await self.crud.add_and_flush(bill)
            if approved:
                await self._post(bill)
            await self.events.record(
                BooksDocumentType.BILL,
                bill.id,
                BooksEventAction.CREATED,
                actor_user_id=user_id,
                note=note
                or {
                    "draft": "Saved as a draft",
                    "awaiting_approval": "Saved for approval",
                }.get(data.approval_status),
            )
            await self.crud.commit_refresh(bill)

        return await self.get(bill.id)

    async def update(self, bill_id: uuid.UUID, data: BillUpdate) -> BillResponse:
        bill = await self._load(bill_id, operational=True)
        fields = data.model_fields_set
        if "due_date" in fields:
            if data.due_date is None:
                raise ValidationError("A bill needs a due date")
            if data.due_date < bill.issue_date:
                raise ValidationError("The due date can't be before the issue date")
            bill.due_date = data.due_date
        if "notes" in fields:
            bill.notes = (data.notes or "").strip() or None
        await self.crud.commit_refresh(bill)
        return await self.get(bill.id)

    async def submit(self, bill_id: uuid.UUID) -> BillResponse:
        bill = await self._load(bill_id, operational=True, for_update=True)
        if bill.approval_status != BillApprovalStatus.DRAFT:
            raise ValidationError("Only a draft can be submitted for approval")
        bill.approval_status = BillApprovalStatus.AWAITING_APPROVAL
        await self.crud.commit_refresh(bill)
        return await self.get(bill.id)

    async def approve(self, bill_id: uuid.UUID, user_id: uuid.UUID) -> BillResponse:
        """Approve a draft or submitted bill and post it, as creating an approved bill does."""
        bill = await self._load(bill_id, operational=True, for_update=True)
        if bill.approval_status == BillApprovalStatus.APPROVED:
            raise ValidationError("This bill is already approved")
        async with unit_of_work(self.db):
            bill.approval_status = BillApprovalStatus.APPROVED
            await self._post(bill)
            await self.events.record(
                BooksDocumentType.BILL,
                bill.id,
                BooksEventAction.POSTED,
                actor_user_id=user_id,
                note="Approved for payment",
            )
        return await self.get(bill.id)

    async def set_archived(
        self, bill_id: uuid.UUID, archived: bool, user_id: Optional[uuid.UUID] = None
    ) -> BillResponse:
        """Hide a bill from the active list. Its ledger entries and payments stay."""
        bill = await self._load(bill_id, for_update=True)
        assert_operational_document(bill)
        if (bill.archived_at is not None) == archived:
            raise ValidationError(
                "This bill is already archived" if archived else "This bill is not archived"
            )
        bill.archived_at = datetime.datetime.now(datetime.timezone.utc) if archived else None
        bill.archived_by_id = user_id if archived else None
        await self.crud.commit_refresh(bill)
        return await self.get(bill.id)

    async def add_attachment(
        self, bill_id: uuid.UUID, file: UploadFile, user_id: uuid.UUID
    ) -> BillResponse:
        bill = await self._load(bill_id, operational=True)
        data = await file.read()
        if not data:
            raise ValidationError("Choose a PDF, JPG, or PNG.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValidationError("That file is larger than 8 MB.")
        filename = (file.filename or "attachment").strip()[-255:] or "attachment"
        # The bytes decide: a browser-declared type or extension can lie.
        content_type = magic_content_type(data)
        if content_type is None:
            raise ValidationError("Choose a PDF, JPG, or PNG.")
        attachment_id = uuid.uuid4()
        relative_path = f"bills/{bill.id}/{attachment_id}.{stored_extension(content_type)}"
        try:
            storage_key = await asyncio.to_thread(save_bytes, relative_path, data)
        except FileExistsError as exc:
            raise ConflictError("Bill attachment already exists") from exc
        bill.attachments.append(
            BillAttachment(
                id=attachment_id,
                storage_key=storage_key,
                filename=filename,
                content_type=content_type,
                uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                uploaded_by_id=user_id,
            )
        )
        await self.crud.save()
        return await self.get(bill.id)

    async def serve_attachment(self, bill_id: uuid.UUID, attachment_id: uuid.UUID) -> Response:
        bill = await self._load(bill_id)
        legacy = self._legacy_attachment(bill)
        if legacy is not None and legacy.id == attachment_id:
            return await serve_stored_pdf(
                bill.pdf_storage_key, legacy.filename, "Bill attachment not found"
            )
        attachment = self._attachment(bill, attachment_id)
        return await serve_stored_pdf(
            attachment.storage_key, attachment.filename, "Bill attachment not found"
        )

    async def remove_attachment(self, bill_id: uuid.UUID, attachment_id: uuid.UUID) -> BillResponse:
        bill = await self._load(bill_id, operational=True)
        attachment = self._attachment(bill, attachment_id)
        storage_key = attachment.storage_key
        if bill.pdf_storage_key == storage_key:
            # Keep a rolled-back release from offering a file that is gone.
            bill.pdf_storage_key = None
        bill.attachments.remove(attachment)
        await self.crud.save()
        try:
            await asyncio.to_thread(delete_object, storage_key)
        except FileNotFoundError:
            pass
        return await self.get(bill.id)

    async def _post(self, bill: Bill) -> None:
        await self.posting.post(
            JournalDocumentType.BILL,
            bill.id,
            f"Supplier bill {bill.bill_number}",
            [
                (CODE_INVENTORY, bill.amount_zar, Decimal(0)),
                (CODE_AP, Decimal(0), bill.amount_zar),
            ],
            entry_date=bill.issue_date,
        )

    async def _load(
        self, bill_id: uuid.UUID, *, operational: bool = False, for_update: bool = False
    ) -> Bill:
        bill = await self.crud.get_by_id(bill_id, for_update=for_update)
        if bill is None:
            raise NotFoundError("Bill not found")
        if operational:
            assert_operational_document(bill)
            if bill.archived_at is not None:
                raise ValidationError("Restore this bill before changing it")
        return bill

    @staticmethod
    def _legacy_attachment(bill: Bill) -> Optional[BillAttachmentResponse]:
        """A file the previous release stored only in ``pdf_storage_key``; read-only.

        107 copied existing keys into ``bill_attachments``; this covers uploads made by
        the previous release while this one rolls out.
        """
        key = (bill.pdf_storage_key or "").strip()
        if not key or any(item.storage_key == key for item in bill.attachments):
            return None
        content_type = media_type_for_storage_key(key)
        return BillAttachmentResponse(
            id=uuid.uuid5(bill.id, "legacy-pdf-storage-key"),
            filename=f"{bill.bill_number}.{stored_extension(content_type)}",
            content_type=content_type,
            uploaded_at=bill.created_at,
            uploaded_by_id=None,
            read_only=True,
        )

    @classmethod
    def _attachment_views(cls, bill: Bill) -> list[BillAttachmentResponse]:
        views = [BillAttachmentResponse.model_validate(item) for item in bill.attachments]
        legacy = cls._legacy_attachment(bill)
        return [legacy, *views] if legacy is not None else views

    @staticmethod
    def _attachment(bill: Bill, attachment_id: uuid.UUID) -> BillAttachment:
        for attachment in bill.attachments:
            if attachment.id == attachment_id:
                return attachment
        raise NotFoundError("Bill attachment not found")

    async def _reject_duplicate_supplier_ref(
        self, supplier_id: uuid.UUID, supplier_ref: str
    ) -> None:
        ref = supplier_ref.strip()
        if not ref:
            return
        existing = (
            await self.db.execute(
                select(Bill.id).where(
                    Bill.is_archive.is_(False),
                    Bill.supplier_id == supplier_id,
                    func.lower(Bill.supplier_ref) == ref.lower(),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("This supplier invoice number is already on a bill.")

    @staticmethod
    def _resolve_fx(currency: str, fx_to_zar: Optional[Decimal]) -> Decimal:
        if currency == "ZAR":
            return Decimal("1")
        if fx_to_zar is None or fx_to_zar <= 0:
            raise ValidationError("fx_to_zar is required and must be positive for foreign currency")
        return fx_to_zar

    @classmethod
    def _to_list_item(cls, bill: Bill) -> BillListItem:
        return BillListItem(
            is_archive=bill.is_archive,
            fx_rate_known=bill.fx_rate_known,
            id=bill.id,
            bill_number=bill_display_number(bill),
            supplier_id=bill.supplier_id,
            supplier_name=bill.supplier.name,
            supplier_ref=bill.supplier_ref,
            issue_date=bill.issue_date,
            due_date=bill.due_date,
            currency=bill.currency,
            fx_to_zar=bill.fx_to_zar,
            amount_foreign=bill.amount_foreign,
            amount_zar=bill.amount_zar,
            amount_paid_zar=bill.amount_paid_zar,
            amount_paid_foreign=bill.amount_paid_foreign,
            balance_zar=bill.amount_zar - bill.amount_paid_zar,
            balance_foreign=bill.amount_foreign - bill.amount_paid_foreign,
            payment_status="unknown" if bill.is_archive else bill.payment_status.value,
            approval_status=bill.approval_status.value,
            status=bill_status(bill, datetime.date.today()),
            is_archived=bill.archived_at is not None,
            archived_at=bill.archived_at,
            notes=bill.notes,
            attachment_count=len(cls._attachment_views(bill)),
            purchase_order_id=bill.purchase_order_id,
            created_at=bill.created_at,
            updated_at=bill.updated_at,
        )

    @classmethod
    def _to_response(cls, bill: Bill) -> BillResponse:
        return BillResponse(
            **cls._to_list_item(bill).model_dump(),
            lines=[BillLineResponse.model_validate(line) for line in bill.lines],
            attachments=cls._attachment_views(bill),
        )
