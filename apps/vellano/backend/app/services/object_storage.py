"""Composition module: f0rge_storage ObjectStorage wired to Vellano settings."""

from __future__ import annotations

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
save_bytes = _storage.save_bytes
read_bytes = _storage.read_bytes
read_relative = _storage.read_relative
presigned_get_url = _storage.presigned_get_url
is_remote_storage_ref = _storage.is_remote_storage_ref
