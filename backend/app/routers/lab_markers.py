from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.labs import get_lab_catalog_service
from app.middleware.auth import get_current_session
from app.schemas.lab_marker import (
    LabMarkerAliasCreate,
    LabMarkerAliasResponse,
    LabMarkerCatalogCreate,
    LabMarkerCatalogResponse,
    MarkerHistoryPoint,
)
from app.services.lab_catalog import LabMarkerCatalogService

router = APIRouter(
    prefix="/api/v1/lab-markers",
    tags=["lab-markers"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/catalog", response_model=List[LabMarkerCatalogResponse])
def search_catalog(
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    service: LabMarkerCatalogService = Depends(get_lab_catalog_service),
):
    return service.search(q, limit)


@router.post(
    "/catalog",
    response_model=LabMarkerCatalogResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_catalog_item(
    body: LabMarkerCatalogCreate,
    service: LabMarkerCatalogService = Depends(get_lab_catalog_service),
):
    return service.create_catalog_item(body)


@router.post(
    "/catalog/{catalog_id}/aliases",
    response_model=LabMarkerAliasResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_alias(
    catalog_id: int,
    body: LabMarkerAliasCreate,
    service: LabMarkerCatalogService = Depends(get_lab_catalog_service),
):
    return service.add_alias(catalog_id, body.alias, body.language)


@router.get("/{canonical_name}/history", response_model=List[MarkerHistoryPoint])
def get_marker_history(
    canonical_name: str,
    service: LabMarkerCatalogService = Depends(get_lab_catalog_service),
):
    return service.get_marker_history(canonical_name)
