"""Composition module: f0rge_storage ObjectStorage wired to Firstout settings."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import Optional

from f0rge_db.organisation import tenant_id_ctx
from functools import lru_cache

import boto3
from botocore.client import BaseClient
from f0rge_storage.object_storage import ObjectStorage, ObjectStorageConfig

from app.config import settings


def _config() -> ObjectStorageConfig:
    return ObjectStorageConfig(
        bucket_name=settings.bucket_name,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        aws_endpoint_url_s3=settings.aws_endpoint_url_s3,
        aws_region=settings.aws_region,
        local_dir=settings.storage_dir,
        default_user_prefix=settings.default_storage_user_id,
    )


@lru_cache(maxsize=1)
def _s3_client() -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint_url_s3,
        region_name=settings.aws_region or "auto",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


_storage = ObjectStorage(_config, client_factory=lambda: _s3_client())

object_storage_enabled = _storage.enabled
is_remote_storage_ref = _storage.is_remote_storage_ref


def _tenant_prefix() -> str:
    team_id = tenant_id_ctx.get()
    if team_id is None:
        raise PermissionError("Storage requires an authenticated tenant")
    return f"tenants/{team_id}"


def _relative(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError("Invalid storage path")
    return str(path)


def save_bytes(relative_path: str, data: bytes, *, user_id: Optional[str] = None) -> str:
    """All new assets, including branding and imports, use the active team."""
    prefix = _tenant_prefix()
    relative_path = _relative(relative_path)
    if object_storage_enabled():
        return _storage.save_bytes(relative_path, data, user_id=prefix)
    return _storage.save_bytes(f"{prefix}/{relative_path}", data)


def _check_ref(storage_ref: str) -> None:
    prefix = _tenant_prefix()
    if os.path.isabs(storage_ref):
        root = Path(settings.storage_dir).resolve()
        try:
            relative = Path(storage_ref).resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise PermissionError("Storage reference outside storage root") from exc
    else:
        relative = _relative(storage_ref)
    if relative.startswith("tenants/") and not relative.startswith(prefix + "/"):
        raise PermissionError("Storage reference belongs to another tenant")
    # Existing unprefixed references remain readable only after their owning
    # database row has passed tenant RLS. They are never guessed as a fallback.


def read_bytes(storage_ref: str) -> bytes:
    _check_ref(storage_ref)
    return _storage.read_bytes(storage_ref)


def read_relative(relative_path: str, *, user_id: Optional[str] = None) -> bytes:
    relative_path = _relative(relative_path)
    prefix = _tenant_prefix()
    if object_storage_enabled():
        return read_bytes(f"{prefix}/{relative_path}")
    return read_bytes(str(Path(settings.storage_dir).resolve() / prefix / relative_path))


def presigned_get_url(storage_ref: str, *, expires_in: int = 300) -> Optional[str]:
    _check_ref(storage_ref)
    return _storage.presigned_get_url(storage_ref, expires_in=expires_in)


def delete_object(storage_ref: str) -> None:
    _check_ref(storage_ref)
    _storage.delete_object(storage_ref)


def overwrite_bytes(storage_ref: str, data: bytes) -> None:
    _check_ref(storage_ref)
    if object_storage_enabled() and not os.path.isabs(storage_ref):
        client = _s3_client()
        bucket = _config().bucket_name
        if not bucket:
            raise FileNotFoundError(storage_ref)
        client.put_object(Bucket=bucket, Key=storage_ref, Body=data)
        return
    parent = os.path.dirname(storage_ref)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(storage_ref, "wb") as handle:
        handle.write(data)
