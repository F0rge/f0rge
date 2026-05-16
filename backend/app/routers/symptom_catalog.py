from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.symptom_catalog import (
    SymptomCatalogItemCreate,
    SymptomCatalogItemResponse,
    SymptomCatalogItemUpdate,
)
from app.services import symptom_catalog as symptom_catalog_service

router = APIRouter(
    prefix="/api/v1/symptoms/catalog",
    tags=["symptoms"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[SymptomCatalogItemResponse])
def list_catalog(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
):
    return symptom_catalog_service.list_items(db, include_archived=include_archived)


@router.post(
    "",
    response_model=SymptomCatalogItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_catalog_item(
    body: SymptomCatalogItemCreate,
    db: Session = Depends(get_db),
):
    return symptom_catalog_service.create_item(db, body.key, body.label)


@router.patch("/{key}", response_model=SymptomCatalogItemResponse)
def update_catalog_item(
    key: str,
    body: SymptomCatalogItemUpdate,
    db: Session = Depends(get_db),
):
    return symptom_catalog_service.update_item(
        db, key, body.model_dump(exclude_unset=True)
    )
