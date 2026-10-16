"""Cin7 customer/supplier addresses and contacts, one row per export line.

Each row is keyed by a hash of its content, so a re-import of the same export
creates nothing. Rows that disappear from a later export are left in place.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cin7_import.parse import as_bool, clip
from app.services.cin7_import.report import EntityResult


def natural_key(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _email(value: Optional[str]) -> Optional[str]:
    email = clip(value, 255)
    if email is None or "@" not in email:
        return None
    return email


def address_payload(row: dict[str, str]) -> dict[str, object]:
    return {
        "address_type": clip(row.get("AddressType"), 32),
        "is_default": as_bool(row.get("AddressDefaultForType", "")),
        "line1": clip(row.get("AddressLine1"), 4000),
        "line2": clip(row.get("AddressLine2"), 4000),
        "city": clip(row.get("City"), 128),
        "state": clip(row.get("State"), 128),
        "postcode": clip(row.get("Postcode"), 32),
        "country": clip(row.get("Country"), 128),
    }


def contact_payload(row: dict[str, str], with_marketing: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": clip(row.get("Contact"), 255),
        "job_title": clip(row.get("JobTitle"), 255),
        "phone": clip(row.get("Phone"), 64),
        "mobile": clip(row.get("MobilePhone"), 64),
        "fax": clip(row.get("Fax"), 64),
        "email": _email(row.get("Email")),
        "website": clip(row.get("Website"), 255),
        "comment": clip(row.get("Comment"), 4000),
        "is_default": as_bool(row.get("Default", "")),
        "include_in_emails": as_bool(row.get("IncludeInEmails", "")),
    }
    if with_marketing:
        payload["marketing_consent"] = clip(row.get("MarketingConsent"), 64)
    return payload


def _is_empty(payload: dict[str, object]) -> bool:
    return not any(value for key, value in payload.items() if not isinstance(value, bool))


async def upsert_children(
    session: AsyncSession,
    *,
    model: type,
    owner_field: str,
    owners: dict[str, object],
    owner_key: Callable[[str], str],
    rows: list[dict[str, str]],
    owner_column: str,
    build: Callable[[dict[str, str]], dict[str, object]],
    result: EntityResult,
) -> None:
    existing: set[tuple[uuid.UUID, str]] = {
        (getattr(row, owner_field), row.natural_key)
        for row in (await session.scalars(select(model))).all()
    }
    seen: set[tuple[uuid.UUID, str]] = set()
    for row in rows:
        key = owner_key(row.get(owner_column, ""))
        if not key:
            result.skip(f"row has no {owner_column}")
            continue
        owner = owners.get(key)
        if owner is None:
            result.skip(f"{owner_column} is not in the export")
            continue
        payload = build(row)
        if _is_empty(payload):
            result.skip("row is blank")
            continue
        digest = natural_key(payload)
        owner_id = owner.id  # type: ignore[attr-defined]
        if (owner_id, digest) in seen:
            result.note("identical row for the same owner merged")
            continue
        seen.add((owner_id, digest))
        if (owner_id, digest) in existing:
            result.unchanged += 1
            continue
        session.add(model(**{owner_field: owner_id, "natural_key": digest, **payload}))
        existing.add((owner_id, digest))
        result.created += 1
    await session.flush()
