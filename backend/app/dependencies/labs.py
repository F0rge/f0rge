from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.lab_attachment_storage import LabAttachmentStorage
from app.services.lab_catalog import LabMarkerCatalogService
from app.services.lab_extraction import LabExtractionService
from app.services.lab_extraction_orchestrator import LabExtractionOrchestrator
from app.services.lab_import import LabImportService
from app.services.labs import LabsService


def get_labs_service(db: Session = Depends(get_db)) -> LabsService:
    return LabsService(db)


def get_lab_catalog_service(db: Session = Depends(get_db)) -> LabMarkerCatalogService:
    return LabMarkerCatalogService(db)


def get_lab_extraction_service() -> LabExtractionService:
    return LabExtractionService()


def get_lab_attachment_storage() -> LabAttachmentStorage:
    return LabAttachmentStorage()


def get_lab_extraction_orchestrator(
    extraction_service: LabExtractionService = Depends(get_lab_extraction_service),
    catalog_service: LabMarkerCatalogService = Depends(get_lab_catalog_service),
) -> LabExtractionOrchestrator:
    return LabExtractionOrchestrator(extraction_service, catalog_service)


def get_lab_import_service(
    db: Session = Depends(get_db),
    labs_service: LabsService = Depends(get_labs_service),
    catalog_service: LabMarkerCatalogService = Depends(get_lab_catalog_service),
    extraction_service: LabExtractionService = Depends(get_lab_extraction_service),
    attachment_storage: LabAttachmentStorage = Depends(get_lab_attachment_storage),
) -> LabImportService:
    return LabImportService(
        db=db,
        labs_service=labs_service,
        catalog_service=catalog_service,
        extraction_service=extraction_service,
        attachment_storage=attachment_storage,
    )
