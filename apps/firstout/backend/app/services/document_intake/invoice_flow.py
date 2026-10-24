"""Match a supplier invoice to a purchase order and post the supplier bill."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bill import Bill
from app.models.proforma import Proforma
from app.models.purchase_order import PoLine, PurchaseOrder, PurchaseOrderStatus
from app.models.team_settings import TeamSettings
from app.schemas.bill import BillCreate, BillLineCreate
from app.schemas.document_intake import (
    ChargeIn,
    ConfirmLineIn,
    ExtractedDocument,
    InvoiceProcessIn,
    InvoiceReview,
    ProcessedBillOut,
    ProformaReview,
    PurchaseOrderMatchOut,
    ReviewFlag,
)
from app.services.bills import BillService
from app.services.document_intake import extract as extract_mod
from app.services.document_intake.compare import compare_invoice, discount_differences
from app.services.document_intake.pricing import CENT, as_decimal, money
from app.schemas.supplier import SupplierCreate
from app.services.document_intake.service import DocumentIntakeService
from app.services.object_storage import save_bytes
from app.services.suppliers import SupplierService, normalize_vat_number
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

_PROCESSABLE = (
    PurchaseOrderStatus.OPEN,
    PurchaseOrderStatus.ON_WATER,
    PurchaseOrderStatus.LANDED,
    PurchaseOrderStatus.RECEIVED,
)
_PO_LOAD = (
    selectinload(PurchaseOrder.supplier),
    selectinload(PurchaseOrder.lines).selectinload(PoLine.sku),
    selectinload(PurchaseOrder.proforma),
)


class InvoiceIntakeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.intake = DocumentIntakeService(db)
        self.bills = BillService(db)

    async def extract_invoice(self, file: UploadFile, user_id: uuid.UUID) -> InvoiceReview:
        raw = await file.read()
        extracted, usage = await extract_mod.extract_supplier_document(
            raw,
            file.filename or "invoice",
            file.content_type,
            kind="invoice",
        )
        review = await self.intake.build_proforma_review(
            extracted,
            usage,
            record_proforma_duplicate=False,
            number_noun="invoice",
        )
        return await self._review_against_orders(extracted, review, raw, file, user_id)

    async def process_invoice(
        self,
        file: UploadFile,
        data: InvoiceProcessIn,
        user_id: uuid.UUID,
    ) -> ProcessedBillOut:
        raw = await file.read()
        if not raw:
            raise ValidationError("Choose a PDF, JPG, or PNG.")
        po = await self._purchase_order(data.purchase_order_id)
        self._require_processable(po)
        _refuse_incomplete(po)
        supplier_id = await self._resolve_supplier(data)
        if supplier_id != po.supplier_id:
            raise ValidationError("This invoice supplier does not match the purchase order.")
        exact, differences = self._compare_confirmed(po, data)
        if not exact and not data.accept_differences:
            raise ValidationError(" ".join(differences))
        content_type = extract_mod.sniff_content_type(raw, file.filename or "", file.content_type)
        note = f"Processed from supplier invoice {data.document_number.strip()} against {po.po_number}."
        return await self._post_bill(
            raw=raw,
            content_type=content_type,
            supplier_id=supplier_id,
            po=po,
            document_number=data.document_number.strip(),
            document_date=data.document_date,
            currency=data.currency,
            fx_to_zar=data.fx_to_zar,
            lines=self._bill_lines(data.lines, data.vat_total, data.charges),
            note=note,
            user_id=user_id,
            auto=False,
        )

    async def _review_against_orders(
        self,
        extracted: ExtractedDocument,
        review: ProformaReview,
        raw: bytes,
        file: UploadFile,
        user_id: uuid.UUID,
    ) -> InvoiceReview:
        supplier_id = review.supplier.supplier_id
        matches, blocked_note, candidates = await self._find_orders(
            extracted,
            supplier_id,
        )
        chosen = matches[0] if len(matches) == 1 else None
        differences: list[str] = []
        exact = False
        if blocked_note:
            differences.append(blocked_note)
        if len(matches) > 1:
            numbers = ", ".join(po.po_number for po in matches)
            differences.append(
                f"More than one purchase order matches this invoice ({numbers}). Pick the right one."
            )
        elif chosen is None and not blocked_note:
            differences.append(
                "No purchase order was linked. Pick the order this invoice belongs to."
            )
        elif chosen is not None:
            exact, differences = self._compare_review(chosen, review)
            if blocked_note:
                differences = [blocked_note, *differences]
                exact = False

        duplicate = False
        if supplier_id is not None and review.document_number.strip():
            duplicate = await self._invoice_exists(supplier_id, review.document_number)
        flags = list(review.flags)
        if duplicate:
            flags.append(
                ReviewFlag(
                    code="duplicate_invoice",
                    message="This supplier invoice number is already on a bill.",
                )
            )
            differences.append("This supplier invoice number is already on a bill.")
            exact = False

        currency = review.currency.upper()
        needs_fx = currency != "ZAR"
        auto_on = await self._auto_enabled()
        processed: Optional[ProcessedBillOut] = None
        if (
            auto_on
            and exact
            and chosen is not None
            and supplier_id is not None
            and not needs_fx
            and not duplicate
            and review.document_date is not None
            and review.document_number.strip()
        ):
            content_type = extract_mod.sniff_content_type(
                raw, file.filename or "", file.content_type
            )
            confirmed = _lines_from_review(review)
            processed = await self._post_bill(
                raw=raw,
                content_type=content_type,
                supplier_id=supplier_id,
                po=chosen,
                document_number=review.document_number.strip(),
                document_date=review.document_date,
                currency=currency,
                fx_to_zar=None,
                lines=self._bill_lines(
                    confirmed,
                    as_decimal(review.vat_total),
                    [
                        ChargeIn(description=row.description, amount=Decimal(row.amount))
                        for row in review.charges
                    ],
                ),
                note=(
                    f"Auto-processed from supplier invoice {review.document_number.strip()} "
                    f"against {chosen.po_number}."
                ),
                user_id=user_id,
                auto=True,
            )

        payload = review.model_dump()
        payload["flags"] = flags
        listed = candidates or matches
        return InvoiceReview(
            **payload,
            po_reference=(extracted.po_reference or "").strip() or None,
            proforma_number=(extracted.proforma_number or "").strip() or None,
            purchase_order=_po_out(chosen) if chosen is not None else None,
            purchase_order_candidates=[_po_out(po) for po in listed],
            exact=exact,
            differences=differences,
            auto_process_enabled=auto_on,
            needs_fx=needs_fx,
            processed=processed,
        )

    async def _find_orders(
        self,
        extracted: ExtractedDocument,
        supplier_id: Optional[uuid.UUID],
    ) -> tuple[list[PurchaseOrder], Optional[str], list[PurchaseOrder]]:
        blocked: Optional[str] = None
        reference = (extracted.po_reference or "").strip()
        if reference:
            referenced = await self._po_by_number(reference)
            if referenced is None:
                blocked = f"Invoice mentions purchase order {reference}, which was not found."
            elif supplier_id is not None and referenced.supplier_id != supplier_id:
                blocked = (
                    f"Invoice mentions {referenced.po_number}, which belongs to another supplier."
                )
            elif referenced.status not in _PROCESSABLE:
                blocked = (
                    f"Invoice mentions {referenced.po_number}, "
                    f"which is {referenced.status.value.replace('_', ' ')}."
                )
            elif referenced.is_archive:
                blocked = f"Invoice mentions {referenced.po_number}, which is an archive order."
            else:
                return [referenced], None, await self._candidates(referenced.supplier_id)

        proforma_number = (extracted.proforma_number or "").strip()
        if supplier_id is not None and proforma_number:
            found = await self._pos_for_proforma(supplier_id, proforma_number)
            usable = [po for po in found if po.status in _PROCESSABLE and not po.is_archive]
            if usable:
                return usable, None, await self._candidates(supplier_id)
            if found and blocked is None:
                blocked = (
                    f"{found[0].po_number} is {found[0].status.value.replace('_', ' ')} "
                    "and cannot be invoiced yet."
                )

        return [], blocked, await self._candidates(supplier_id)

    def _compare_review(self, po: PurchaseOrder, review: ProformaReview) -> tuple[bool, list[str]]:
        invoice_lines: list[tuple[int, Optional[uuid.UUID], str, int, Decimal]] = []
        discounts: list[tuple[int, Optional[Decimal], Optional[Decimal]]] = []
        snapshot_discounts = _snapshot_discounts(po)
        for index, line in enumerate(review.lines, start=1):
            sku_id = line.match.sku_id if line.match is not None else None
            qty = line.qty_whole or 0
            invoice_lines.append(
                (index, sku_id, line.description, qty, Decimal(line.net_unit_price))
            )
            discounts.append(
                (index, as_decimal(line.discount_percent), snapshot_discounts.get(sku_id))
            )
        return self._compare(po, review.currency, invoice_lines, review, discounts)

    def _compare_confirmed(
        self,
        po: PurchaseOrder,
        data: InvoiceProcessIn,
    ) -> tuple[bool, list[str]]:
        invoice_lines: list[tuple[int, Optional[uuid.UUID], str, int, Decimal]] = []
        discounts: list[tuple[int, Optional[Decimal], Optional[Decimal]]] = []
        snapshot_discounts = _snapshot_discounts(po)
        number = 0
        for line in data.lines:
            if line.skip:
                continue
            number += 1
            invoice_lines.append((number, line.sku_id, line.description, line.qty, line.unit_price))
            discounts.append((number, line.discount_percent, snapshot_discounts.get(line.sku_id)))
        exact, differences = compare_invoice(
            currency=data.currency,
            po_currency=_po_currency(po),
            po_lines=_po_lines(po),
            invoice_lines=invoice_lines,
            po_charges=_po_charges(po),
            invoice_charges=[(row.description, row.amount) for row in data.charges],
            po_vat=_po_money(po, "vat_total"),
            invoice_vat=data.vat_total,
            po_total=_po_money(po, "total"),
            invoice_total=data.total,
        )
        return _with_incomplete(po, *_merge(exact, differences, discounts))

    def _compare(
        self,
        po: PurchaseOrder,
        currency: str,
        invoice_lines: list[tuple[int, Optional[uuid.UUID], str, int, Decimal]],
        review: ProformaReview,
        discounts: list[tuple[int, Optional[Decimal], Optional[Decimal]]],
    ) -> tuple[bool, list[str]]:
        exact, differences = compare_invoice(
            currency=currency,
            po_currency=_po_currency(po),
            po_lines=_po_lines(po),
            invoice_lines=invoice_lines,
            po_charges=_po_charges(po),
            invoice_charges=[(row.description, Decimal(row.amount)) for row in review.charges],
            po_vat=_po_money(po, "vat_total"),
            invoice_vat=as_decimal(review.vat_total),
            po_total=_po_money(po, "total"),
            invoice_total=as_decimal(review.total),
        )
        return _with_incomplete(po, *_merge(exact, differences, discounts))

    def _bill_lines(
        self,
        lines: list[ConfirmLineIn],
        vat_total: Optional[Decimal],
        charges: list[ChargeIn],
    ) -> list[BillLineCreate]:
        built: list[BillLineCreate] = []
        for line in lines:
            if line.skip or line.sku_id is None:
                continue
            code = (line.supplier_code or "").strip()
            description = f"{code} — {line.description}" if code else line.description
            built.append(
                BillLineCreate(
                    description=description[:500],
                    qty=line.qty,
                    unit_amount=money(line.unit_price, CENT),
                )
            )
        if vat_total is not None and vat_total > CENT:
            built.append(
                BillLineCreate(description="VAT", qty=1, unit_amount=money(vat_total, CENT))
            )
        for charge in charges:
            if charge.amount > CENT:
                built.append(
                    BillLineCreate(
                        description=charge.description[:500],
                        qty=1,
                        unit_amount=money(charge.amount, CENT),
                    )
                )
        if not built:
            raise ValidationError("The invoice needs at least one line with a SKU.")
        return built

    async def _post_bill(
        self,
        *,
        raw: bytes,
        content_type: str,
        supplier_id: uuid.UUID,
        po: PurchaseOrder,
        document_number: str,
        document_date,
        currency: str,
        fx_to_zar: Optional[Decimal],
        lines: list[BillLineCreate],
        note: str,
        user_id: uuid.UUID,
        auto: bool,
    ) -> ProcessedBillOut:
        created = await self.bills.create(
            BillCreate(
                supplier_id=supplier_id,
                supplier_ref=document_number,
                issue_date=document_date,
                currency=currency,
                fx_to_zar=fx_to_zar,
                lines=lines,
            ),
            user_id=user_id,
            note=note[:512],
        )
        extension = extract_mod.stored_extension(content_type)
        relative_path = f"bills/{created.id}.{extension}"
        try:
            storage_key = await asyncio.to_thread(save_bytes, relative_path, raw)
        except FileExistsError as exc:
            raise ConflictError("Bill attachment already exists") from exc
        bill = await self.bills.crud.get_by_id(created.id)
        if bill is None:
            raise NotFoundError("Bill not found")
        bill.purchase_order_id = po.id
        bill.pdf_storage_key = storage_key
        async with unit_of_work(self.db):
            await self.db.flush()
        return ProcessedBillOut(
            bill_id=created.id,
            bill_number=created.bill_number,
            auto=auto,
            purchase_order_id=po.id,
            po_number=po.po_number,
        )

    async def _purchase_order(self, po_id: uuid.UUID) -> PurchaseOrder:
        po = (
            await self.db.execute(
                select(PurchaseOrder).options(*_PO_LOAD).where(PurchaseOrder.id == po_id)
            )
        ).scalar_one_or_none()
        if po is None:
            raise NotFoundError("Purchase order not found")
        return po

    async def _po_by_number(self, number: str) -> Optional[PurchaseOrder]:
        return (
            await self.db.execute(
                select(PurchaseOrder)
                .options(*_PO_LOAD)
                .where(func.lower(PurchaseOrder.po_number) == number.strip().lower())
            )
        ).scalar_one_or_none()

    async def _pos_for_proforma(
        self,
        supplier_id: uuid.UUID,
        proforma_number: str,
    ) -> list[PurchaseOrder]:
        number = proforma_number.strip().lower()
        proforma_ids = select(Proforma.id).where(
            Proforma.supplier_id == supplier_id,
            func.lower(Proforma.invoice_number) == number,
        )
        stmt = (
            select(PurchaseOrder)
            .options(*_PO_LOAD)
            .where(
                PurchaseOrder.supplier_id == supplier_id,
                PurchaseOrder.is_archive.is_(False),
                or_(
                    PurchaseOrder.proforma_id.in_(proforma_ids),
                    func.lower(PurchaseOrder.intake_snapshot["document_number"].astext) == number,
                ),
            )
            .order_by(PurchaseOrder.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().unique().all())

    async def _candidates(self, supplier_id: Optional[uuid.UUID]) -> list[PurchaseOrder]:
        stmt = (
            select(PurchaseOrder)
            .options(*_PO_LOAD)
            .where(
                PurchaseOrder.is_archive.is_(False),
                PurchaseOrder.status.in_(_PROCESSABLE),
            )
            .order_by(PurchaseOrder.created_at.desc())
            .limit(20)
        )
        if supplier_id is not None:
            stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
        return list((await self.db.execute(stmt)).scalars().unique().all())

    async def _invoice_exists(self, supplier_id: uuid.UUID, supplier_ref: str) -> bool:
        existing = (
            await self.db.execute(
                select(Bill.id).where(
                    Bill.supplier_id == supplier_id,
                    func.lower(Bill.supplier_ref) == supplier_ref.strip().lower(),
                )
            )
        ).scalar_one_or_none()
        return existing is not None

    async def _auto_enabled(self) -> bool:
        value = (
            await self.db.execute(
                select(TeamSettings.auto_process_exact_supplier_invoices).limit(1)
            )
        ).scalar_one_or_none()
        return bool(value)

    async def _resolve_supplier(self, data: InvoiceProcessIn) -> uuid.UUID:
        if data.supplier_id is not None:
            supplier = await self.intake.supplier_crud.get_by_id(data.supplier_id)
            if supplier is None:
                raise NotFoundError("Supplier not found")
            return data.supplier_id
        if data.create_supplier is None:
            raise ValidationError("Choose a supplier or create a new one.")
        created = await self.intake.suppliers.create(
            SupplierCreate(
                name=data.create_supplier.name,
                default_currency=data.create_supplier.default_currency or data.currency,
                vat_number=normalize_vat_number(data.create_supplier.vat_number),
                address=data.create_supplier.address,
            )
        )
        return created.id

    @staticmethod
    def _require_processable(po: PurchaseOrder) -> None:
        if po.is_archive or po.status not in _PROCESSABLE:
            raise ValidationError("This purchase order is not ready to receive a supplier invoice.")


def _merge(
    exact: bool,
    differences: list[str],
    discounts: list[tuple[int, Optional[Decimal], Optional[Decimal]]],
) -> tuple[bool, list[str]]:
    extra = discount_differences(discounts)
    if extra:
        return False, [*differences, *extra]
    return exact, differences


def _lines_from_review(review: ProformaReview) -> list[ConfirmLineIn]:
    lines: list[ConfirmLineIn] = []
    for line in review.lines:
        if line.match is None or line.qty_whole is None:
            continue
        lines.append(
            ConfirmLineIn(
                supplier_code=line.supplier_code,
                description=line.description,
                qty=line.qty_whole,
                unit_price=Decimal(line.net_unit_price),
                discount_percent=as_decimal(line.discount_percent),
                vat_rate=as_decimal(line.vat_rate),
                sku_id=line.match.sku_id,
                skip=False,
            )
        )
    return lines


def _po_out(po: PurchaseOrder) -> PurchaseOrderMatchOut:
    return PurchaseOrderMatchOut(
        purchase_order_id=po.id,
        po_number=po.po_number,
        status=po.status.value,
        supplier_id=po.supplier_id,
        supplier_name=po.supplier.name,
    )


def _po_lines(po: PurchaseOrder) -> list[tuple[uuid.UUID, str, int, Decimal]]:
    rows: list[tuple[uuid.UUID, str, int, Decimal]] = []
    for line in po.lines:
        if line.sku_id is None or line.sku is None:
            continue
        rows.append((line.sku_id, line.sku.our_ref, line.qty, Decimal(line.factory_unit_amount)))
    return rows


def _incomplete_note(po: PurchaseOrder) -> list[str]:
    missing = sum(1 for line in po.lines if line.sku_id is None)
    if missing == 0:
        return []
    noun = "line" if missing == 1 else "lines"
    return [f"The purchase order still has {missing} {noun} without a SKU."]


def _with_incomplete(
    po: PurchaseOrder,
    exact: bool,
    differences: list[str],
) -> tuple[bool, list[str]]:
    extra = _incomplete_note(po)
    if extra:
        return False, [*differences, *extra]
    return exact, differences


def _refuse_incomplete(po: PurchaseOrder) -> None:
    extra = _incomplete_note(po)
    if extra:
        raise ValidationError(extra[0])


def _po_currency(po: PurchaseOrder) -> str:
    snapshot = po.intake_snapshot or {}
    raw = snapshot.get("currency") or "ZAR"
    return SupplierService.normalize_currency(str(raw))


def _po_charges(po: PurchaseOrder) -> list[tuple[str, Decimal]]:
    snapshot = po.intake_snapshot or {}
    charges = snapshot.get("charges") or []
    rows: list[tuple[str, Decimal]] = []
    for row in charges:
        if not isinstance(row, dict):
            continue
        amount = as_decimal(row.get("amount")) or Decimal("0")
        rows.append((str(row.get("description") or "Charge"), amount))
    return rows


def _po_money(po: PurchaseOrder, key: str) -> Optional[Decimal]:
    snapshot = po.intake_snapshot or {}
    return as_decimal(snapshot.get(key))


def _snapshot_discounts(po: PurchaseOrder) -> dict[Optional[uuid.UUID], Optional[Decimal]]:
    snapshot = po.intake_snapshot or {}
    found: dict[Optional[uuid.UUID], Optional[Decimal]] = {}
    for row in snapshot.get("lines") or []:
        if not isinstance(row, dict) or not row.get("sku_id"):
            continue
        found[uuid.UUID(str(row["sku_id"]))] = as_decimal(row.get("discount_percent"))
    return found
