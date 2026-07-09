from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional
import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.config import settings


def object_storage_enabled() -> bool:
    return bool(
        settings.bucket_name
        and settings.aws_access_key_id
        and settings.aws_secret_access_key
        and settings.aws_endpoint_url_s3
    )


def default_object_user_prefix() -> str:
    return settings.default_storage_user_id


def _object_key(relative_path: str, user_id: Optional[str] = None) -> str:
    prefix = user_id or default_object_user_prefix()
    return f"{prefix}/{relative_path.lstrip('/')}"


@lru_cache(maxsize=1)
def _s3_client() -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=settings.aws_endpoint_url_s3,
        region_name=settings.aws_region or "auto",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def build_object_key(relative_path: str, user_id: Optional[str] = None) -> str:
    return _object_key(relative_path, user_id=user_id)


def delete_relative(relative_path: str, *, user_id: Optional[str] = None) -> None:
    if not object_storage_enabled():
        local_path = os.path.join(os.path.abspath(settings.photo_dir), relative_path)
        if os.path.exists(local_path):
            os.unlink(local_path)
        return
    delete_object(build_object_key(relative_path, user_id=user_id))


def read_relative(relative_path: str, *, user_id: Optional[str] = None) -> bytes:
    if not object_storage_enabled():
        local_path = os.path.join(os.path.abspath(settings.photo_dir), relative_path)
        with open(local_path, "rb") as handle:
            return handle.read()
    return read_bytes(build_object_key(relative_path, user_id=user_id))


def exists_relative(relative_path: str, *, user_id: Optional[str] = None) -> bool:
    if not object_storage_enabled():
        return os.path.exists(os.path.join(os.path.abspath(settings.photo_dir), relative_path))
    return object_exists(build_object_key(relative_path, user_id=user_id))


def presigned_url_for_relative(relative_path: str, *, expires_in: int = 300) -> Optional[str]:
    if not object_storage_enabled():
        return None
    return presigned_get_url(build_object_key(relative_path), expires_in=expires_in)


def save_bytes(relative_path: str, data: bytes, *, user_id: Optional[str] = None) -> str:
    """Persist bytes; returns the storage key (S3) or absolute local path."""
    if not object_storage_enabled():
        local_root = os.path.abspath(settings.photo_dir)
        local_path = os.path.join(local_root, relative_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        if os.path.exists(local_path):
            raise FileExistsError(f"Refusing to overwrite existing object: {local_path}")
        with open(local_path, "wb") as handle:
            handle.write(data)
        return local_path

    key = _object_key(relative_path, user_id=user_id)
    client = _s3_client()
    try:
        client.head_object(Bucket=settings.bucket_name, Key=key)
        raise FileExistsError(f"Refusing to overwrite existing object: {key}")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code not in ("404", "NoSuchKey", "NotFound"):
            raise
    client.put_object(Bucket=settings.bucket_name, Key=key, Body=data)
    return key


def read_bytes(storage_ref: str) -> bytes:
    if object_storage_enabled() and not os.path.isabs(storage_ref):
        response = _s3_client().get_object(Bucket=settings.bucket_name, Key=storage_ref)
        return response["Body"].read()
    with open(storage_ref, "rb") as handle:
        return handle.read()


def delete_object(storage_ref: str) -> None:
    if object_storage_enabled() and not os.path.isabs(storage_ref):
        _s3_client().delete_object(Bucket=settings.bucket_name, Key=storage_ref)
        return
    if os.path.exists(storage_ref):
        os.unlink(storage_ref)


def object_exists(storage_ref: str) -> bool:
    if object_storage_enabled() and not os.path.isabs(storage_ref):
        try:
            _s3_client().head_object(Bucket=settings.bucket_name, Key=storage_ref)
            return True
        except ClientError:
            return False
    return os.path.exists(storage_ref)


def list_photo_filenames(prefix: str) -> set[str]:
    """Return bare filenames matching ``{date}_photo-*`` for collision detection."""
    if not object_storage_enabled():
        photo_dir = os.path.abspath(settings.photo_dir)
        if not os.path.isdir(photo_dir):
            return set()
        return {name for name in os.listdir(photo_dir) if name.startswith(prefix)}

    user_prefix = default_object_user_prefix()
    s3_prefix = f"{user_prefix}/"
    names: set[str] = set()
    client = _s3_client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.bucket_name, Prefix=s3_prefix):
        for item in page.get("Contents", []):
            key = item.get("Key", "")
            if not key.startswith(s3_prefix):
                continue
            name = key[len(s3_prefix) :]
            if name.startswith(prefix):
                names.add(name)
    return names


def presigned_get_url(storage_ref: str, *, expires_in: int = 300) -> Optional[str]:
    if not object_storage_enabled() or os.path.isabs(storage_ref):
        return None
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.bucket_name, "Key": storage_ref},
        ExpiresIn=expires_in,
    )


def is_remote_storage_ref(storage_ref: str) -> bool:
    return object_storage_enabled() and not os.path.isabs(storage_ref) and "://" not in storage_ref
