from __future__ import annotations

import io

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from app.services import object_storage

register_heif_opener()

AVATAR_MAX_DIM = 256
AVATAR_JPEG_QUALITY = 85


def avatar_relative_path(user_id: str) -> str:
    return f"avatars/{user_id}.jpg"


def resize_avatar(file_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    if img.width > AVATAR_MAX_DIM or img.height > AVATAR_MAX_DIM:
        img.thumbnail((AVATAR_MAX_DIM, AVATAR_MAX_DIM), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=AVATAR_JPEG_QUALITY)
    return buf.getvalue()


def avatar_exists(*, user_id: str) -> bool:
    return object_storage.exists_relative(avatar_relative_path(user_id), user_id=user_id)


def read_avatar(*, user_id: str) -> bytes:
    return object_storage.read_relative(avatar_relative_path(user_id), user_id=user_id)


def save_avatar(file_bytes: bytes, *, user_id: str) -> str:
    relative_path = avatar_relative_path(user_id)
    if avatar_exists(user_id=user_id):
        delete_avatar(user_id=user_id)
    object_storage.save_bytes(relative_path, file_bytes, user_id=user_id)
    return relative_path


def delete_avatar(*, user_id: str) -> None:
    if not avatar_exists(user_id=user_id):
        return
    object_storage.delete_relative(avatar_relative_path(user_id), user_id=user_id)
