"""S3-compatible object storage with a local-filesystem fallback.

Ported verbatim from marrow's ``app/services/object_storage.py``, with the
settings coupling replaced by explicit parameterization: apps build an
:class:`ObjectStorage` from an :class:`ObjectStorageConfig` (or a zero-arg
callable returning one) and expose whatever module-level surface they need.

Semantics preserved exactly:
- keys are user-prefixed: ``{user_id or default_user_prefix}/{relative_path}``
- storage is "enabled" only when bucket + credentials + endpoint are all set;
  otherwise every operation falls back to the local filesystem under
  ``local_dir``
- ``save_bytes`` refuses to overwrite an existing object (local or remote)
- absolute paths are always treated as local refs, even when S3 is enabled
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class ObjectStorageConfig:
    """Connection + layout settings for an S3-compatible store.

    Leave the AWS fields empty to run on the local filesystem under
    ``local_dir`` instead (dev/test fallback).
    """

    bucket_name: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_endpoint_url_s3: str = ""
    aws_region: str = "auto"
    local_dir: str = "photos"
    default_user_prefix: str = ""


@lru_cache(maxsize=4)
def _default_client(
    endpoint_url: str, region: str, access_key_id: str, secret_access_key: str
) -> BaseClient:
    """Build (and reuse) a boto3 client per distinct connection tuple."""
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region or "auto",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )


class ObjectStorage:
    """One configured store instance; apps build exactly one at import time.

    ``config`` may be a static :class:`ObjectStorageConfig` or a zero-arg
    callable returning one. A callable is re-read on every operation so a live
    settings object stays authoritative (marrow's tests monkeypatch settings
    fields per test).

    ``client_factory`` overrides how the boto3 client is obtained — the app
    owns that seam so its tests can stub the S3 trust boundary. When omitted,
    clients are built from the current config and cached via ``lru_cache``.
    """

    def __init__(
        self,
        config: ObjectStorageConfig | Callable[[], ObjectStorageConfig],
        *,
        client_factory: Optional[Callable[[], BaseClient]] = None,
    ) -> None:
        self._get_config = config if callable(config) else (lambda: config)
        self._client_factory = client_factory

    def _client(self) -> BaseClient:
        if self._client_factory is not None:
            return self._client_factory()
        cfg = self._get_config()
        return _default_client(
            cfg.aws_endpoint_url_s3,
            cfg.aws_region,
            cfg.aws_access_key_id,
            cfg.aws_secret_access_key,
        )

    def _local_root(self) -> str:
        return os.path.abspath(self._get_config().local_dir)

    def enabled(self) -> bool:
        cfg = self._get_config()
        return bool(
            cfg.bucket_name
            and cfg.aws_access_key_id
            and cfg.aws_secret_access_key
            and cfg.aws_endpoint_url_s3
        )

    def default_user_prefix(self) -> str:
        return self._get_config().default_user_prefix

    def build_object_key(self, relative_path: str, user_id: Optional[str] = None) -> str:
        prefix = user_id or self.default_user_prefix()
        return f"{prefix}/{relative_path.lstrip('/')}"

    def delete_relative(self, relative_path: str, *, user_id: Optional[str] = None) -> None:
        if not self.enabled():
            local_path = os.path.join(self._local_root(), relative_path)
            if os.path.exists(local_path):
                os.unlink(local_path)
            return
        self.delete_object(self.build_object_key(relative_path, user_id=user_id))

    def read_relative(self, relative_path: str, *, user_id: Optional[str] = None) -> bytes:
        if not self.enabled():
            local_path = os.path.join(self._local_root(), relative_path)
            with open(local_path, "rb") as handle:
                return handle.read()
        key = self.resolve_relative_key(relative_path, user_id=user_id)
        if key is None:
            raise FileNotFoundError(relative_path)
        return self.read_bytes(key)

    def exists_relative(self, relative_path: str, *, user_id: Optional[str] = None) -> bool:
        return self.resolve_relative_key(relative_path, user_id=user_id) is not None

    def resolve_relative_key(
        self, relative_path: str, *, user_id: Optional[str] = None
    ) -> Optional[str]:
        """Return the concrete storage key/path that holds ``relative_path``.

        Tries ``{user_id}/…``, then the configured default user prefix, then a
        bare (unprefixed) key — Railway/Tigris syncs have used all three layouts.
        """
        rel = relative_path.lstrip("/")
        if not self.enabled():
            local_path = os.path.join(self._local_root(), rel)
            return local_path if os.path.exists(local_path) else None

        seen: set[str] = set()
        candidates: list[str] = []
        for uid in (user_id, self.default_user_prefix(), None):
            key = self.build_object_key(rel, user_id=uid) if uid else rel
            if key in seen:
                continue
            seen.add(key)
            candidates.append(key)
        for key in candidates:
            if self.object_exists(key):
                return key
        return None

    def presigned_url_for_relative(
        self, relative_path: str, *, expires_in: int = 300, user_id: Optional[str] = None
    ) -> Optional[str]:
        if not self.enabled():
            return None
        key = self.resolve_relative_key(relative_path, user_id=user_id)
        if key is None:
            return None
        return self.presigned_get_url(key, expires_in=expires_in)

    def save_bytes(self, relative_path: str, data: bytes, *, user_id: Optional[str] = None) -> str:
        """Persist bytes; returns the storage key (S3) or absolute local path."""
        if not self.enabled():
            local_path = os.path.join(self._local_root(), relative_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            if os.path.exists(local_path):
                raise FileExistsError(f"Refusing to overwrite existing object: {local_path}")
            with open(local_path, "wb") as handle:
                handle.write(data)
            return local_path

        key = self.build_object_key(relative_path, user_id=user_id)
        client = self._client()
        bucket = self._get_config().bucket_name
        try:
            client.head_object(Bucket=bucket, Key=key)
            raise FileExistsError(f"Refusing to overwrite existing object: {key}")
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in ("404", "NoSuchKey", "NotFound"):
                raise
        client.put_object(Bucket=bucket, Key=key, Body=data)
        return key

    def read_bytes(self, storage_ref: str) -> bytes:
        if self.enabled() and not os.path.isabs(storage_ref):
            response = self._client().get_object(
                Bucket=self._get_config().bucket_name, Key=storage_ref
            )
            return response["Body"].read()
        with open(storage_ref, "rb") as handle:
            return handle.read()

    def delete_object(self, storage_ref: str) -> None:
        if self.enabled() and not os.path.isabs(storage_ref):
            self._client().delete_object(Bucket=self._get_config().bucket_name, Key=storage_ref)
            return
        if os.path.exists(storage_ref):
            os.unlink(storage_ref)

    def object_exists(self, storage_ref: str) -> bool:
        if self.enabled() and not os.path.isabs(storage_ref):
            try:
                self._client().head_object(Bucket=self._get_config().bucket_name, Key=storage_ref)
                return True
            except ClientError:
                return False
        return os.path.exists(storage_ref)

    def list_filenames(self, prefix: str, *, user_id: Optional[str] = None) -> set[str]:
        """Return bare filenames under the user prefix that start with ``prefix``."""
        if not self.enabled():
            local_root = self._local_root()
            if not os.path.isdir(local_root):
                return set()
            return {name for name in os.listdir(local_root) if name.startswith(prefix)}

        user_prefix = user_id or self.default_user_prefix()
        s3_prefix = f"{user_prefix}/"
        names: set[str] = set()
        client = self._client()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._get_config().bucket_name, Prefix=s3_prefix):
            for item in page.get("Contents", []):
                key = item.get("Key", "")
                if not key.startswith(s3_prefix):
                    continue
                name = key[len(s3_prefix) :]
                if name.startswith(prefix):
                    names.add(name)
        return names

    def presigned_get_url(self, storage_ref: str, *, expires_in: int = 300) -> Optional[str]:
        if not self.enabled() or os.path.isabs(storage_ref):
            return None
        return self._client().generate_presigned_url(
            "get_object",
            Params={"Bucket": self._get_config().bucket_name, "Key": storage_ref},
            ExpiresIn=expires_in,
        )

    def is_remote_storage_ref(self, storage_ref: str) -> bool:
        return self.enabled() and not os.path.isabs(storage_ref) and "://" not in storage_ref
