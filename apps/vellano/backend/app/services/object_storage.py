"""Composition module: f0rge_storage ObjectStorage wired to Vellano settings."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

import boto3
from botocore.client import BaseClient
from f0rge_storage.object_storage import ObjectStorage, ObjectStorageConfig

from app.config import settings
from app.tenancy.context import tenant_ctx

_storage_by_prefix: dict[str, ObjectStorage] = {}


def _config_for_prefix(prefix: str) -> ObjectStorageConfig:
    return ObjectStorageConfig(
        bucket_name=settings.bucket_name,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        aws_endpoint_url_s3=settings.aws_endpoint_url_s3,
        aws_region=settings.aws_region,
        local_dir=os.path.join(settings.storage_dir, prefix),
        default_user_prefix=prefix,
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


def storage_for_current_tenant() -> ObjectStorage:
    ctx = tenant_ctx.get()
    prefix = ctx.storage_prefix if ctx is not None else settings.default_storage_user_id
    cached = _storage_by_prefix.get(prefix)
    if cached is not None:
        return cached

    def factory(p: str = prefix) -> ObjectStorageConfig:
        return _config_for_prefix(p)

    store = ObjectStorage(factory, client_factory=lambda: _s3_client())
    _storage_by_prefix[prefix] = store
    return store


def object_storage_enabled() -> bool:
    return storage_for_current_tenant().enabled()


def save_bytes(relative_path: str, data: bytes, *, user_id: Optional[str] = None) -> str:
    return storage_for_current_tenant().save_bytes(relative_path, data, user_id=user_id)


def read_bytes(storage_ref: str) -> bytes:
    return storage_for_current_tenant().read_bytes(storage_ref)


def read_relative(relative_path: str, *, user_id: Optional[str] = None) -> bytes:
    return storage_for_current_tenant().read_relative(relative_path, user_id=user_id)


def presigned_get_url(storage_ref: str, *, expires_in: int = 300) -> Optional[str]:
    return storage_for_current_tenant().presigned_get_url(storage_ref, expires_in=expires_in)


def is_remote_storage_ref(storage_ref: str) -> bool:
    return storage_for_current_tenant().is_remote_storage_ref(storage_ref)


def delete_object(storage_ref: str) -> None:
    storage_for_current_tenant().delete_object(storage_ref)


def overwrite_bytes(storage_ref: str, data: bytes) -> None:
    if object_storage_enabled() and not os.path.isabs(storage_ref):
        client = _s3_client()
        bucket = _config_for_prefix(settings.default_storage_user_id).bucket_name
        if not bucket:
            raise FileNotFoundError(storage_ref)
        client.put_object(Bucket=bucket, Key=storage_ref, Body=data)
        return
    parent = os.path.dirname(storage_ref)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(storage_ref, "wb") as handle:
        handle.write(data)
