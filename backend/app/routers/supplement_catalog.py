from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_session
from app.models.supplement_catalog import SupplementCatalogItem
from app.schemas.supplement_catalog import (
    SupplementCatalogItemCreate,
    SupplementCatalogItemResponse,
    SupplementCatalogItemUpdate,
)

router = APIRouter(
    prefix="/api/v1/supplements/catalog",
    tags=["supplements"],
    dependencies=[Depends(get_current_session)],
)

_KEY_RE = re.compile(r"^[a-z0-9_]+$")


def _normalize_key(raw: str) -> str:
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    key = re.sub(r"[^a-z0-9_]", "", key)
    return key


@router.get("", response_model=list[SupplementCatalogItemResponse])
def list_catalog(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
):
    query = db.query(SupplementCatalogItem)
    if not include_archived:
        query = query.filter(SupplementCatalogItem.archived.is_(False))
    return query.order_by(
        SupplementCatalogItem.sort_order.asc(),
        SupplementCatalogItem.id.asc(),
    ).all()


@router.post(
    "",
    response_model=SupplementCatalogItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_catalog_item(
    body: SupplementCatalogItemCreate,
    db: Session = Depends(get_db),
):
    key = _normalize_key(body.key)
    if not key or not _KEY_RE.match(key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key; must contain a-z, 0-9, or underscore.",
        )

    existing = (
        db.query(SupplementCatalogItem)
        .filter(SupplementCatalogItem.key == key)
        .one_or_none()
    )
    if existing:
        if existing.archived:
            existing.archived = False
            existing.label = body.label
            db.commit()
            db.refresh(existing)
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Catalog item '{key}' already exists.",
        )

    max_sort = (
        db.query(SupplementCatalogItem)
        .order_by(SupplementCatalogItem.sort_order.desc())
        .first()
    )
    next_sort = (max_sort.sort_order + 1) if max_sort else 0

    item = SupplementCatalogItem(key=key, label=body.label, sort_order=next_sort)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{key}", response_model=SupplementCatalogItemResponse)
def update_catalog_item(
    key: str,
    body: SupplementCatalogItemUpdate,
    db: Session = Depends(get_db),
):
    item = (
        db.query(SupplementCatalogItem)
        .filter(SupplementCatalogItem.key == key)
        .one_or_none()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Catalog item '{key}' not found.",
        )

    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
