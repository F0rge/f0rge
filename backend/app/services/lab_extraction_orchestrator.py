from __future__ import annotations

from fastapi import UploadFile

from app.schemas.lab_marker import CatalogHint, ExtractionResult
from app.services.lab_catalog import LabMarkerCatalogService
from app.services.lab_extraction import LabExtractionService


class LabExtractionOrchestrator:
    def __init__(
        self,
        extraction_service: LabExtractionService,
        catalog_service: LabMarkerCatalogService,
    ) -> None:
        self.extraction_service = extraction_service
        self.catalog_service = catalog_service

    def _hints(self) -> list[CatalogHint]:
        return [
            CatalogHint(
                canonical=item.canonical_name,
                display=item.display_name,
                aliases=[a.alias for a in item.aliases],
                common_units=item.common_units or [],
            )
            for item in self.catalog_service.search(None, limit=10000)
        ]

    async def preview_text(self, document_text: str) -> ExtractionResult:
        return await self.extraction_service.extract_text(document_text, self._hints())

    async def preview_upload(self, file: UploadFile) -> ExtractionResult:
        file_bytes = await file.read()
        return await self.extraction_service.preview_upload(
            file_bytes,
            file.content_type or "",
            file.filename or "upload",
            self._hints(),
        )
