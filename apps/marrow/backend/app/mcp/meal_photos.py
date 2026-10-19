"""Meal-photo bytes for MCP: decode, hash, store, dedupe, copy.

Filenames stay per placement. ``original_filename`` holds ``sha256:<hex>`` of the
bytes the caller supplied (the upload, or the copied file). No new column.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import io
import re
import uuid
from typing import Optional

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.meal import Meal
from app.models.photo import Photo
from app.services.photo_storage import (
    THUMB_MAX_DIM,
    THUMB_QUALITY,
    delete_photo,
    read_photo,
    resize_image,
    save_photo,
    thumb_filename,
)
from app.services.photos import entry_photo_upload_lock, next_photo_filename
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.tenant import owned_by_user

MAX_PHOTO_BYTES = 25 * 1024 * 1024
_HASH_PREFIX = "sha256:"
_DATA_URL = re.compile(r"^data:image/[^;,]+;base64,", re.IGNORECASE)


def photo_hash_tag(raw: bytes) -> str:
    """``sha256:<hex>`` of the original bytes, stored in ``original_filename``."""
    return _HASH_PREFIX + hashlib.sha256(raw).hexdigest()


def photo_sha256_value(original_filename: Optional[str]) -> Optional[str]:
    """Return the stored hash tag when ``original_filename`` is one."""
    if original_filename and original_filename.startswith(_HASH_PREFIX):
        return original_filename
    return None


def decode_photo_b64(value: str) -> bytes:
    """Strict base64, after a ``data:image/...;base64,`` prefix and whitespace.

    ``ValidationError`` if the payload is empty, larger than ``MAX_PHOTO_BYTES``,
    or not an image Pillow can open (message ``unsupported image``).
    """
    text = _DATA_URL.sub("", value.strip(), count=1)
    compact = "".join(text.split())
    if not compact:
        raise ValidationError("empty photo")
    try:
        raw = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError("invalid base64 photo") from exc
    if not raw:
        raise ValidationError("empty photo")
    if len(raw) > MAX_PHOTO_BYTES:
        raise ValidationError("photo exceeds 25 MB")
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img.load()
    except Exception as exc:
        raise ValidationError("unsupported image") from exc
    return raw


async def delete_photo_files(names: list[str], user_id: uuid.UUID) -> None:
    """Best-effort delete of full and thumb objects after a failed commit."""
    uid = str(user_id)
    for name in names:
        await asyncio.to_thread(delete_photo, name, user_id=uid)


async def store_photo_for(
    db: AsyncSession,
    entry: Entry,
    photo: Photo,
    meal: Meal,
    raw: bytes,
    user_id: uuid.UUID,
    *,
    bind_meal: bool = True,
) -> list[str]:
    """Resize outside the day lock, save full + thumb, stamp hash and filename.

    Returns the object names written so the caller can delete them if the
    surrounding commit fails. ``bind_meal`` is false when the meal has other
    placements and only this photo should point at the new file.
    """
    processed = await asyncio.to_thread(resize_image, raw)
    thumb = await asyncio.to_thread(
        resize_image, processed, max_dim=THUMB_MAX_DIM, quality=THUMB_QUALITY
    )
    tag = photo_hash_tag(raw)
    saved: list[str] = []
    filename = ""
    try:
        async with entry_photo_upload_lock(db, entry.id):
            filename = await next_photo_filename(db, entry)
            uid = str(user_id)
            await asyncio.to_thread(save_photo, processed, filename, user_id=uid)
            saved.append(filename)
            thumb_name = thumb_filename(filename)
            await asyncio.to_thread(save_photo, thumb, thumb_name, user_id=uid)
            saved.append(thumb_name)
    except Exception:
        await delete_photo_files(saved, user_id)
        raise

    photo.filename = filename
    photo.original_filename = tag
    if bind_meal:
        meal.filename = filename
        meal.original_filename = tag
    return list(saved)


async def find_duplicate(db: AsyncSession, entry_id: int, hash_tag: str) -> Optional[Photo]:
    """Same user, same day, same original-bytes hash. Oldest row wins."""
    stmt = (
        select(Photo)
        .where(
            owned_by_user(Photo.user_id),
            Photo.entry_id == entry_id,
            Photo.original_filename == hash_tag,
        )
        .order_by(Photo.id.asc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def copy_photo_bytes(src_photo: Photo, user_id: uuid.UUID) -> bytes:
    """Read another placement's file. Never share the filename — callers re-save."""
    if not src_photo.filename:
        raise NotFoundError("Photo file not found")
    try:
        return await asyncio.to_thread(read_photo, src_photo.filename, user_id=str(user_id))
    except FileNotFoundError as exc:
        raise NotFoundError("Photo file not found") from exc


async def placement_count(db: AsyncSession, meal_id: int) -> int:
    count = await db.scalar(select(func.count()).select_from(Photo).where(Photo.meal_id == meal_id))
    return int(count or 0)


async def filename_in_use(db: AsyncSession, filename: str) -> bool:
    """True when any photo or meal row still points at ``filename``."""
    photo_id = await db.scalar(select(Photo.id).where(Photo.filename == filename).limit(1))
    if photo_id is not None:
        return True
    meal_id = await db.scalar(select(Meal.id).where(Meal.filename == filename).limit(1))
    return meal_id is not None
