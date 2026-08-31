from __future__ import annotations

import asyncio
import datetime
import uuid
from typing import Optional

from fastapi import UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.proforma import ProformaCRUD
from app.crud.supplier import SupplierCRUD
from app.models.proforma import Proforma
from app.schemas.proforma import ProformaResponse
from app.services.object_storage import (
    is_remote_storage_ref,
    presigned_get_url,
    read_bytes,
    save_bytes,
)
from app.services.suppliers import SupplierService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError


class ProformaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = ProformaCRUD(db)
        self.supplier_crud = SupplierCRUD(db)

    async def list(self) -> list[ProformaResponse]:
        proformas = await self.crud.list_all()
        return [self._to_response(p) for p in proformas]

    async def get(self, proforma_id: uuid.UUID) -> ProformaResponse:
        proforma = await self.crud.get_by_id(proforma_id)
        if proforma is None:
            raise NotFoundError("Proforma not found")
        return self._to_response(proforma)

    async def create(
        self,
        supplier_id: uuid.UUID,
        invoice_number: str,
        invoice_date: datetime.date,
        currency: Optional[str],
        file: UploadFile,
    ) -> ProformaResponse:
        supplier = await self.supplier_crud.get_by_id(supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier not found")

        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise ValidationError("PDF file is required")

        proforma_id = uuid.uuid4()
        relative_path = f"proformas/{proforma_id}.pdf"
        try:
            storage_key = await asyncio.to_thread(save_bytes, relative_path, pdf_bytes)
        except FileExistsError as exc:
            raise ConflictError("Proforma file already exists") from exc

        proforma = Proforma(
            id=proforma_id,
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            currency=SupplierService.normalize_currency(currency),
            pdf_storage_key=storage_key,
        )
        await self.crud.add_and_flush(proforma)
        try:
            await self.crud.commit_refresh(proforma)
        except IntegrityError as exc:
            raise ConflictError(
                "A proforma with this invoice number already exists for this supplier"
            ) from exc

        reloaded = await self.crud.get_by_id(proforma.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def serve_file(self, proforma_id: uuid.UUID) -> Response:
        proforma = await self.crud.get_by_id(proforma_id)
        if proforma is None:
            raise NotFoundError("Proforma not found")

        storage_key = proforma.pdf_storage_key
        if is_remote_storage_ref(storage_key):
            url = presigned_get_url(storage_key)
            if url:
                return RedirectResponse(url)

        try:
            data = await asyncio.to_thread(read_bytes, storage_key)
        except FileNotFoundError as exc:
            raise NotFoundError("Proforma file not found") from exc
        return Response(content=data, media_type="application/pdf")

    @staticmethod
    def _to_response(proforma: Proforma) -> ProformaResponse:
        return ProformaResponse(
            id=proforma.id,
            supplier_id=proforma.supplier_id,
            supplier_name=proforma.supplier.name,
            invoice_number=proforma.invoice_number,
            invoice_date=proforma.invoice_date,
            currency=proforma.currency,
            pdf_storage_key=proforma.pdf_storage_key,
            created_at=proforma.created_at,
            updated_at=proforma.updated_at,
        )
