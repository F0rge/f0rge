from __future__ import annotations

import asyncio
import hashlib
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ValidationError
from app.models.lab import Lab
from app.schemas.lab import LabCreate, LabMarkerCreate
from app.schemas.lab_marker import CatalogHint
from app.services.lab_attachment_storage import LabAttachmentStorage
from app.services.lab_catalog import LabMarkerCatalogService
from app.services.lab_extraction import LabExtractionService
from app.services.labs import LabsService


def _sha256_source_path(file_bytes: bytes) -> str:
    return "upload:" + hashlib.sha256(file_bytes).hexdigest()


async def _build_catalog_hints(
    catalog_service: LabMarkerCatalogService,
) -> list[CatalogHint]:
    items = await catalog_service.search(None, limit=10000)
    return [
        CatalogHint(
            canonical=item.canonical_name,
            display=item.display_name,
            aliases=[a.alias for a in item.aliases],
            common_units=item.common_units or [],
        )
        for item in items
    ]


class LabImportService:
    def __init__(
        self,
        db: AsyncSession,
        labs_service: LabsService,
        catalog_service: LabMarkerCatalogService,
        extraction_service: LabExtractionService,
        attachment_storage: LabAttachmentStorage,
    ) -> None:
        self.db = db
        self.labs_service = labs_service
        self.catalog_service = catalog_service
        self.extraction_service = extraction_service
        self.attachment_storage = attachment_storage

    async def _existing_or_none(self, source_path: Optional[str], force: bool) -> Optional[Lab]:
        if force or source_path is None:
            return None
        return (
            await self.db.execute(select(Lab).where(Lab.source_path == source_path))
        ).scalar_one_or_none()

    async def import_from_text(
        self,
        document_text: str,
        source_path: Optional[str] = None,
        force: bool = False,
        filename: Optional[str] = None,
    ) -> Lab:
        existing = await self._existing_or_none(source_path, force)
        if existing is not None:
            return existing
        hints = await _build_catalog_hints(self.catalog_service)
        hint_name = filename or (source_path.rsplit("/", 1)[-1] if source_path else None)
        result = await self.extraction_service.extract_text(
            document_text, hints, filename=hint_name
        )
        return await self._persist(
            result=result,
            source_kind="text",
            source_path=source_path,
            raw_text=document_text,
            attachment_path=None,
            force=force,
        )

    async def import_from_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        source_path: Optional[str] = None,
        force: bool = False,
    ) -> Lab:
        computed_source_path = source_path or _sha256_source_path(pdf_bytes)
        existing = await self._existing_or_none(computed_source_path, force)
        if existing is not None:
            return existing
        hints = await _build_catalog_hints(self.catalog_service)
        result = await self.extraction_service.extract_pdf(pdf_bytes, hints, filename=filename)
        attachment_path = await asyncio.to_thread(
            self.attachment_storage.save, pdf_bytes, filename, "application/pdf"
        )
        return await self._persist(
            result=result,
            source_kind="pdf",
            source_path=computed_source_path,
            raw_text=None,
            attachment_path=attachment_path,
            force=force,
        )

    async def import_from_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        filename: str,
        source_path: Optional[str] = None,
        force: bool = False,
    ) -> Lab:
        computed_source_path = source_path or _sha256_source_path(image_bytes)
        existing = await self._existing_or_none(computed_source_path, force)
        if existing is not None:
            return existing
        hints = await _build_catalog_hints(self.catalog_service)
        result = await self.extraction_service.extract_image(
            image_bytes, mime_type, hints, filename=filename
        )
        attachment_path = await asyncio.to_thread(
            self.attachment_storage.save, image_bytes, filename, mime_type
        )
        return await self._persist(
            result=result,
            source_kind="image",
            source_path=computed_source_path,
            raw_text=None,
            attachment_path=attachment_path,
            force=force,
        )

    async def import_from_upload(
        self,
        upload_file: UploadFile,
        force: bool = False,
    ) -> Lab:
        """Sniff MIME type and dispatch to the correct import method."""
        content_type = upload_file.content_type or ""
        filename = upload_file.filename or "upload"
        file_bytes = await upload_file.read()

        if content_type == "application/pdf":
            return await self.import_from_pdf(file_bytes, filename, force=force)
        if content_type.startswith("image/"):
            return await self.import_from_image(file_bytes, content_type, filename, force=force)
        raise ValidationError(
            f"Unsupported upload MIME type: {content_type!r}. "
            "Supported: application/pdf, image/jpeg, image/png, image/webp."
        )

    async def _persist(
        self,
        *,
        result: object,
        source_kind: str,
        source_path: Optional[str],
        raw_text: Optional[str],
        attachment_path: Optional[str],
        force: bool,
    ) -> Lab:
        """Resolve catalog entries, handle idempotency, and call LabsService.create_lab."""
        from app.schemas.lab_marker import ExtractionResult

        assert isinstance(result, ExtractionResult)
        payload = result.payload
        lab_data = payload.lab

        if source_path is not None:
            existing = (
                await self.db.execute(select(Lab).where(Lab.source_path == source_path))
            ).scalar_one_or_none()
            if existing is not None:
                if not force:
                    return existing
                await self.db.delete(existing)
                await self.db.flush()

        review_status = (
            "needs_review" if payload.confidence < 0.7 or result.attempts > 1 else "confirmed"
        )

        marker_creates: list[LabMarkerCreate] = []
        for em in payload.markers:
            canonical_name = em.canonical_match or em.proposed_canonical
            assert canonical_name is not None
            catalog_item = await self.catalog_service.resolve_or_create(
                name=canonical_name,
                display_name=em.display_name,
                units=[em.unit] if em.unit else None,
            )
            marker_creates.append(
                LabMarkerCreate(
                    catalog_id=catalog_item.id,
                    canonical_name=catalog_item.canonical_name,
                    display_name=em.display_name,
                    value=em.value,
                    value_text=em.value_text,
                    unit=em.unit,
                    ref_low=em.ref_low,
                    ref_high=em.ref_high,
                    ref_text=em.ref_text,
                )
            )

        create_data = LabCreate(
            lab_date=lab_data.lab_date,
            name=lab_data.name,
            type=lab_data.type,
            lab_location=lab_data.lab_location,
            source_kind=source_kind,
            source_path=source_path,
            attachment_path=attachment_path,
            raw_text=raw_text,
            notes=lab_data.notes,
            markers=marker_creates,
        )

        return await self.labs_service.create_lab(
            create_data,
            extraction_meta={
                "extraction_model": result.model,
                "extraction_confidence": payload.confidence,
                "review_status": review_status,
                "source_kind": source_kind,
                "attachment_path": attachment_path,
                "raw_text": raw_text,
            },
        )
