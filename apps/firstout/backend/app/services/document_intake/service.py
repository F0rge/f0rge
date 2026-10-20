"""Proforma review, purchase-order confirm, and guided SKU creation."""

from __future__ import annotations

import asyncio
import re
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.proforma import ProformaCRUD
from app.crud.purchase_order import PurchaseOrderCRUD
from app.crud.sku import SkuCRUD
from app.crud.supplier import SupplierCRUD
from app.models.proforma import Proforma
from app.models.sku_supplier_price import SkuSupplierPrice
from app.schemas.document_intake import (
    ChargeOut,
    ConfirmLineIn,
    ExtractedDocument,
    IntakeSkuCreate,
    IntakeSkuResponse,
    ModelUsage,
    ProformaConfirmIn,
    ProformaConfirmResponse,
    ProformaReview,
    ReviewedLine,
    SkuSuggestIn,
    SkuSuggestion,
)
from app.schemas.purchase_order import PoLineCreate, PurchaseOrderCreate
from app.schemas.sku import SkuCreate, SkuUpdate
from app.services.document_intake import extract as extract_mod
from app.services.document_intake.matching import (
    PriceRecord,
    SkuRecord,
    SupplierRecord,
    document_flags,
    line_flags,
    match_sku_line,
    match_supplier,
)
from app.services.document_intake.pricing import (
    CENT,
    dec_str,
    extended,
    money,
    net_unit_price,
    whole_qty,
)
from app.services.object_storage import save_bytes
from app.services.proformas import ProformaService
from app.services.purchase_orders import PurchaseOrderService
from app.services.skus import SkuService
from app.schemas.supplier import SupplierCreate
from app.services.suppliers import SupplierService, normalize_vat_number
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()
    return cleaned[:40] or "SKU"


class DocumentIntakeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.supplier_crud = SupplierCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.proforma_crud = ProformaCRUD(db)
        self.po_crud = PurchaseOrderCRUD(db)
        self.suppliers = SupplierService(db)
        self.skus = SkuService(db)
        self.proformas = ProformaService(db)
        self.purchase_orders = PurchaseOrderService(db)

    async def extract_proforma(self, file: UploadFile) -> ProformaReview:
        raw = await file.read()
        extracted, usage = await extract_mod.extract_supplier_document(
            raw,
            file.filename or "proforma",
            file.content_type,
            kind="proforma",
        )
        return await self.build_proforma_review(extracted, usage)

    async def build_proforma_review(
        self,
        extracted: ExtractedDocument,
        usage: ModelUsage,
    ) -> ProformaReview:
        suppliers = await self._supplier_records()
        skus = await self._sku_records()
        prices = await self._price_records()
        chosen, candidates = match_supplier(
            extracted.supplier.name,
            extracted.supplier.vat_number,
            extracted.supplier.address,
            suppliers,
        )
        duplicate = False
        if chosen.supplier_id is not None and extracted.document_number.strip():
            duplicate = await self._proforma_exists(chosen.supplier_id, extracted.document_number)

        reviewed: list[ReviewedLine] = []
        computed_ex = Decimal("0")
        for index, line in enumerate(extracted.lines, start=1):
            qty = line.qty if line.qty is not None else Decimal("0")
            net = net_unit_price(
                line.unit_price, qty or Decimal("1"), line.discount_percent, line.discount_amount
            )
            if qty > 0 and net > 0:
                computed_ex += extended(net, qty)
            match, alternatives = match_sku_line(line, skus, prices, chosen.supplier_id)
            reviewed.append(
                ReviewedLine(
                    supplier_code=(line.supplier_code or "").strip() or None,
                    description=line.description.strip() or "Untitled line",
                    qty=str(qty),
                    qty_whole=whole_qty(qty),
                    unit_price=str(money(line.unit_price, Decimal("0.0001"))),
                    discount_percent=dec_str(line.discount_percent),
                    discount_amount=dec_str(line.discount_amount),
                    net_unit_price=str(net),
                    vat_rate=dec_str(line.vat_rate, Decimal("0.0001")),
                    vat_amount=dec_str(line.vat_amount),
                    line_total=dec_str(line.line_total),
                    match=match,
                    alternatives=alternatives,
                    flags=line_flags(index, line, match),
                )
            )

        charges = [
            ChargeOut(
                description=row.description.strip() or "Charge", amount=str(money(row.amount, CENT))
            )
            for row in extracted.charges
            if row.amount is not None
        ]
        currency = SupplierService.normalize_currency(extracted.currency)
        return ProformaReview(
            supplier=chosen,
            supplier_candidates=candidates,
            document_number=extracted.document_number.strip(),
            document_date=extracted.document_date,
            currency=currency,
            payment_terms=(extracted.payment_terms or "").strip() or None,
            deposit=(extracted.deposit or "").strip() or None,
            lines=reviewed,
            charges=charges,
            subtotal=dec_str(extracted.subtotal),
            vat_total=dec_str(extracted.vat_total),
            total=dec_str(extracted.total),
            computed_total=str(
                money(
                    computed_ex
                    + sum((Decimal(row.amount) for row in charges), Decimal("0"))
                    + (extracted.vat_total or Decimal("0")),
                    CENT,
                )
            ),
            flags=document_flags(extracted, computed_ex, duplicate),
            usage=usage,
        )

    async def confirm_proforma(
        self,
        file: UploadFile,
        data: ProformaConfirmIn,
        user_id: uuid.UUID,
    ) -> ProformaConfirmResponse:
        raw = await file.read()
        if not raw:
            raise ValidationError("Choose a PDF, JPG, or PNG.")
        content_type = extract_mod.sniff_content_type(raw, file.filename or "", file.content_type)
        kept = [line for line in data.lines if not line.skip]
        if not kept:
            raise ValidationError("Keep at least one line on the purchase order.")
        sku_ids = [line.sku_id for line in kept]
        if any(sku_id is None for sku_id in sku_ids):
            raise ValidationError(
                "Every kept line needs a SKU. Create one, link one, or skip the line."
            )
        if len(set(sku_ids)) != len(sku_ids):
            raise ValidationError("Two lines point at the same SKU. Combine them or skip one.")
        for line in kept:
            assert line.sku_id is not None
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")

        supplier_id = await self._resolve_supplier(data)
        if await self._proforma_exists(supplier_id, data.document_number):
            raise ConflictError(
                "A proforma with this invoice number already exists for this supplier"
            )

        proforma_id = uuid.uuid4()
        extension = extract_mod.stored_extension(content_type)
        relative_path = f"proformas/{proforma_id}.{extension}"
        try:
            storage_key = await asyncio.to_thread(save_bytes, relative_path, raw)
        except FileExistsError as exc:
            raise ConflictError("Proforma file already exists") from exc

        proforma = Proforma(
            id=proforma_id,
            supplier_id=supplier_id,
            invoice_number=data.document_number.strip(),
            invoice_date=data.document_date,
            currency=SupplierService.normalize_currency(data.currency),
            pdf_storage_key=storage_key,
        )
        try:
            async with unit_of_work(self.db):
                await self.proforma_crud.add_and_flush(proforma)
        except IntegrityError as exc:
            raise ConflictError(
                "A proforma with this invoice number already exists for this supplier"
            ) from exc

        created = await self.purchase_orders.create(
            PurchaseOrderCreate(
                supplier_id=supplier_id,
                proforma_id=proforma_id,
                lines=[
                    PoLineCreate(
                        sku_id=line.sku_id,  # type: ignore[arg-type]
                        qty=line.qty,
                        factory_unit_amount=line.unit_price,
                    )
                    for line in kept
                    if line.sku_id is not None
                ],
            ),
            user_id,
        )
        await self._write_snapshot_and_prices(created.id, supplier_id, data, kept)
        proforma_response = await self.proformas.get(proforma_id)
        po_response = await self.purchase_orders.get(created.id)
        return ProformaConfirmResponse(proforma=proforma_response, purchase_order=po_response)

    async def suggest_sku(self, data: SkuSuggestIn) -> SkuSuggestion:
        description = data.description.strip()
        hint = (data.hint or "").strip()
        name = description[:255]
        design = description[:255]
        fabric = "Unspecified"
        category: Optional[str] = None
        source = "document"
        if hint:
            hinted = await extract_mod.suggest_sku_fields(description, data.supplier_code, hint)
            name = str(hinted.get("name") or name).strip()[:255] or name
            design = str(hinted.get("design") or design).strip()[:255] or design
            fabric = str(hinted.get("fabric") or fabric).strip()[:255] or fabric
            raw_category = hinted.get("category")
            if isinstance(raw_category, str) and raw_category.strip():
                category = raw_category.strip()[:64]
            source = "model"
        base = _slug(data.supplier_code or description)
        our_ref = await self._unique_our_ref(base)
        our_barcode = await self._unique_barcode(f"BC-{our_ref}"[:64])
        cost = dec_str(data.unit_price, Decimal("0.0001")) if data.unit_price is not None else None
        return SkuSuggestion(
            our_ref=our_ref,
            our_barcode=our_barcode,
            name=name,
            design=design,
            fabric=fabric,
            supplier_ref=(data.supplier_code or "").strip()[:64] or None,
            category=category,
            cost_price=cost,
            vat_rate=dec_str(data.vat_rate, Decimal("0.0001")),
            source=source,
        )

    async def create_sku(self, data: IntakeSkuCreate, user_id: uuid.UUID) -> IntakeSkuResponse:
        supplier = await self.supplier_crud.get_by_id(data.supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier not found")
        created = await self.skus.create(
            SkuCreate(
                our_ref=data.our_ref,
                our_barcode=data.our_barcode,
                name=data.name,
                design=data.design,
                fabric=data.fabric,
                supplier_ref=data.supplier_ref,
                category=data.category,
                carton_count=data.carton_count,
            ),
            user_id,
        )
        await self.skus.update(
            created.id,
            SkuUpdate(preferred_supplier_id=data.supplier_id),
            user_id,
        )
        price_id = await self._upsert_supplier_price(
            sku_id=created.id,
            supplier_id=data.supplier_id,
            supplier_sku=data.supplier_sku or data.supplier_ref,
            latest_price=data.latest_price,
        )
        sku = await self.skus.get(created.id, user_id)
        return IntakeSkuResponse(sku=sku, supplier_price_id=price_id)

    async def _resolve_supplier(self, data: ProformaConfirmIn) -> uuid.UUID:
        if data.supplier_id is not None:
            supplier = await self.supplier_crud.get_by_id(data.supplier_id)
            if supplier is None:
                raise NotFoundError("Supplier not found")
            return data.supplier_id
        if data.create_supplier is None:
            raise ValidationError("Choose a supplier or create a new one.")
        created = await self.suppliers.create(_supplier_create(data.create_supplier, data.currency))
        return created.id

    async def _write_snapshot_and_prices(
        self,
        po_id: uuid.UUID,
        supplier_id: uuid.UUID,
        data: ProformaConfirmIn,
        kept: list[ConfirmLineIn],
    ) -> None:
        po = await self.po_crud.get_by_id(po_id)
        if po is None:
            raise NotFoundError("Purchase order not found")
        kept_lines = []
        for line in kept:
            if line.sku_id is None:
                continue
            await self._upsert_supplier_price(
                sku_id=line.sku_id,
                supplier_id=supplier_id,
                supplier_sku=line.supplier_code,
                latest_price=line.unit_price,
            )
            kept_lines.append(
                {
                    "sku_id": str(line.sku_id),
                    "supplier_code": line.supplier_code,
                    "description": line.description,
                    "qty": line.qty,
                    "unit_price": str(line.unit_price),
                    "discount_percent": str(line.discount_percent)
                    if line.discount_percent is not None
                    else None,
                    "vat_rate": str(line.vat_rate) if line.vat_rate is not None else None,
                }
            )
        po.intake_snapshot = {
            "source": "proforma",
            "document_number": data.document_number,
            "currency": SupplierService.normalize_currency(data.currency),
            "payment_terms": data.payment_terms,
            "deposit": data.deposit,
            "vat_total": str(data.vat_total) if data.vat_total is not None else None,
            "total": str(data.total) if data.total is not None else None,
            "charges": [
                {"description": row.description, "amount": str(row.amount)} for row in data.charges
            ],
            "lines": kept_lines,
        }
        async with unit_of_work(self.db):
            await self.db.flush()

    async def _upsert_supplier_price(
        self,
        *,
        sku_id: uuid.UUID,
        supplier_id: uuid.UUID,
        supplier_sku: Optional[str],
        latest_price: Optional[Decimal],
    ) -> uuid.UUID:
        existing = (
            await self.db.execute(
                select(SkuSupplierPrice).where(
                    SkuSupplierPrice.sku_id == sku_id,
                    SkuSupplierPrice.supplier_id == supplier_id,
                )
            )
        ).scalar_one_or_none()
        code = (supplier_sku or "").strip() or None
        if existing is None:
            existing = SkuSupplierPrice(
                sku_id=sku_id,
                supplier_id=supplier_id,
                supplier_sku=code,
                latest_price=latest_price,
            )
            self.db.add(existing)
        else:
            if code:
                existing.supplier_sku = code
            if latest_price is not None:
                existing.latest_price = latest_price
        async with unit_of_work(self.db):
            await self.db.flush()
        return existing.id

    async def _unique_our_ref(self, base: str) -> str:
        candidate = base[:64]
        suffix = 2
        while await self.sku_crud.get_by_our_ref(candidate) is not None:
            extra = f"-{suffix}"
            candidate = f"{base[: 64 - len(extra)]}{extra}"
            suffix += 1
        return candidate

    async def _unique_barcode(self, base: str) -> str:
        candidate = base[:64]
        suffix = 2
        while await self.sku_crud.get_by_our_barcode(candidate) is not None:
            extra = f"-{suffix}"
            candidate = f"{base[: 64 - len(extra)]}{extra}"
            suffix += 1
        return candidate

    async def _supplier_records(self) -> list[SupplierRecord]:
        rows = await self.supplier_crud.list_all()
        return [
            SupplierRecord(
                id=row.id,
                name=row.name,
                vat_number=row.vat_number,
                address=row.address,
            )
            for row in rows
        ]

    async def _sku_records(self) -> list[SkuRecord]:
        rows = await self.sku_crud.list_all()
        return [
            SkuRecord(
                id=row.id,
                our_ref=row.our_ref,
                our_barcode=row.our_barcode,
                name=row.name,
                design=row.design,
                fabric=row.fabric,
                supplier_ref=row.supplier_ref,
            )
            for row in rows
        ]

    async def _price_records(self) -> list[PriceRecord]:
        rows = (await self.db.execute(select(SkuSupplierPrice))).scalars().all()
        return [
            PriceRecord(
                sku_id=row.sku_id, supplier_id=row.supplier_id, supplier_sku=row.supplier_sku
            )
            for row in rows
        ]

    async def _proforma_exists(self, supplier_id: uuid.UUID, invoice_number: str) -> bool:
        stmt = select(Proforma.id).where(
            Proforma.supplier_id == supplier_id,
            func.lower(Proforma.invoice_number) == invoice_number.strip().lower(),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None


def _supplier_create(data, currency: str) -> SupplierCreate:
    return SupplierCreate(
        name=data.name,
        default_currency=data.default_currency or currency,
        vat_number=normalize_vat_number(data.vat_number),
        address=data.address,
    )
