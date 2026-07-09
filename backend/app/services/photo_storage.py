from __future__ import annotations

import io

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from app.services import object_storage

register_heif_opener()


def resize_image(file_bytes: bytes, max_dim: int = 2048, quality: int = 85) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    if img.width > max_dim or img.height > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def save_photo(file_bytes: bytes, filename: str, *, user_id: str | None = None) -> str:
    return object_storage.save_bytes(filename, file_bytes, user_id=user_id)


def delete_photo(filename: str, *, user_id: str | None = None) -> None:
    object_storage.delete_relative(filename, user_id=user_id)


def read_photo(filename: str, *, user_id: str | None = None) -> bytes:
    return object_storage.read_relative(filename, user_id=user_id)


def photo_exists(filename: str, *, user_id: str | None = None) -> bool:
    return object_storage.exists_relative(filename, user_id=user_id)
