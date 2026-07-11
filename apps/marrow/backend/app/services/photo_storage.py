from __future__ import annotations

from f0rge_storage.images import resize_image

from app.services import object_storage

__all__ = ["resize_image", "save_photo", "delete_photo", "read_photo", "photo_exists"]


def save_photo(file_bytes: bytes, filename: str, *, user_id: str | None = None) -> str:
    return object_storage.save_bytes(filename, file_bytes, user_id=user_id)


def delete_photo(filename: str, *, user_id: str | None = None) -> None:
    object_storage.delete_relative(filename, user_id=user_id)


def read_photo(filename: str, *, user_id: str | None = None) -> bytes:
    return object_storage.read_relative(filename, user_id=user_id)


def photo_exists(filename: str, *, user_id: str | None = None) -> bool:
    return object_storage.exists_relative(filename, user_id=user_id)
