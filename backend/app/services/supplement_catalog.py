from __future__ import annotations

import datetime
import re
from typing import Iterable

from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.supplement_catalog import SupplementCatalogItem

_KEY_RE = re.compile(r"^[a-z0-9_]+$")


def normalize_key(raw: str) -> str:
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    key = re.sub(r"[^a-z0-9_]", "", key)
    return key


def list_items(
    db: Session, include_archived: bool = False
) -> list[SupplementCatalogItem]:
    query = db.query(SupplementCatalogItem)
    if not include_archived:
        query = query.filter(SupplementCatalogItem.archived.is_(False))
    return query.order_by(
        SupplementCatalogItem.sort_order.asc(),
        SupplementCatalogItem.id.asc(),
    ).all()


def create_item(db: Session, key: str, label: str) -> SupplementCatalogItem:
    normalized = normalize_key(key)
    if not normalized or not _KEY_RE.match(normalized):
        raise ValidationError("Invalid key; must contain a-z, 0-9, or underscore.")

    existing = (
        db.query(SupplementCatalogItem)
        .filter(SupplementCatalogItem.key == normalized)
        .one_or_none()
    )
    if existing:
        if existing.archived:
            existing.archived = False
            existing.label = label
            db.commit()
            db.refresh(existing)
            return existing
        raise ConflictError(f"Catalog item '{normalized}' already exists.")

    max_item = (
        db.query(SupplementCatalogItem)
        .order_by(SupplementCatalogItem.sort_order.desc())
        .first()
    )
    next_sort = (max_item.sort_order + 1) if max_item else 0

    item = SupplementCatalogItem(key=normalized, label=label, sort_order=next_sort)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, key: str, data: dict) -> SupplementCatalogItem:
    item = (
        db.query(SupplementCatalogItem)
        .filter(SupplementCatalogItem.key == key)
        .one_or_none()
    )
    if not item:
        raise NotFoundError(f"Catalog item '{key}' not found.")

    for field, value in data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def touch(db: Session, keys: Iterable[str]) -> None:
    """Bulk-update first_used_at/last_used_at. Caller owns the transaction."""
    key_list = list(keys)
    if not key_list:
        return
    now = datetime.datetime.utcnow()
    existing = {
        item.key: item
        for item in db.query(SupplementCatalogItem)
        .filter(SupplementCatalogItem.key.in_(key_list))
        .all()
    }
    for key in key_list:
        item = existing.get(key)
        if item is None:
            continue
        if item.first_used_at is None:
            item.first_used_at = now
        item.last_used_at = now
