from __future__ import annotations

from f0rge_storage.images import resize_image

from app.services import object_storage

AVATAR_MAX_DIM = 256
AVATAR_JPEG_QUALITY = 85


def avatar_relative_path(user_id: str) -> str:
    return f"avatars/{user_id}.jpg"


def resize_avatar(file_bytes: bytes) -> bytes:
    return resize_image(file_bytes, max_dim=AVATAR_MAX_DIM, quality=AVATAR_JPEG_QUALITY)


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
