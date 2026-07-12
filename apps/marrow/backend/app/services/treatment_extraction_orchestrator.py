from __future__ import annotations

from fastapi import UploadFile

from app.schemas.treatment import TreatmentExtractionResult
from app.services.treatment_extraction import TreatmentExtractionService


class TreatmentExtractionOrchestrator:
    def __init__(self, extraction_service: TreatmentExtractionService) -> None:
        self.extraction_service = extraction_service

    async def preview_upload(self, file: UploadFile) -> TreatmentExtractionResult:
        file_bytes = await file.read()
        return await self.extraction_service.preview_upload(
            file_bytes,
            file.content_type or "",
            file.filename or "upload",
        )
