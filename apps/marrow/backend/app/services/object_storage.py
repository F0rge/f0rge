"""Composition module: f0rge_storage's ObjectStorage wired to app settings.

Keeps the historical public surface — ``object_storage_enabled``,
``save_bytes``, ``read_relative``, ``presigned_get_url``, etc. — so
``from app.services import object_storage`` works unchanged across services
and tests.

Config is a factory (re-read per operation) because tests monkeypatch
``settings`` fields per test. ``_s3_client`` stays a module-level seam so
tests can monkeypatch the boto3 client — the S3 trust boundary — exactly as
before the lib extraction.
"""

from __future__ import annotations

from functools import lru_cache

import boto3
from botocore.client import BaseClient
from fastapi.responses import Response
from f0rge_storage.object_storage import ObjectStorage, ObjectStorageConfig

from app.config import settings


def _config() -> ObjectStorageConfig:
    return ObjectStorageConfig(
        bucket_name=settings.bucket_name,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        aws_endpoint_url_s3=settings.aws_endpoint_url_s3,
        aws_region=settings.aws_region,
        local_dir=settings.photo_dir,
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


# client_factory late-binds through the module global so monkeypatching
# ``object_storage._s3_client`` swaps the client for the instance too.
_storage = ObjectStorage(_config, client_factory=lambda: _s3_client())

object_storage_enabled = _storage.enabled
default_object_user_prefix = _storage.default_user_prefix
build_object_key = _storage.build_object_key
delete_relative = _storage.delete_relative
read_relative = _storage.read_relative
exists_relative = _storage.exists_relative
resolve_relative_key = _storage.resolve_relative_key
presigned_url_for_relative = _storage.presigned_url_for_relative
save_bytes = _storage.save_bytes
read_bytes = _storage.read_bytes
delete_object = _storage.delete_object
object_exists = _storage.object_exists
list_photo_filenames = _storage.list_filenames
presigned_get_url = _storage.presigned_get_url
is_remote_storage_ref = _storage.is_remote_storage_ref


def jpeg_response(content: bytes, cache_control: str) -> Response:
    """Return a JPEG body. Callers cache the bytes, never a presigned Location."""
    return Response(
        content=content,
        media_type="image/jpeg",
        headers={"Cache-Control": cache_control},
    )
