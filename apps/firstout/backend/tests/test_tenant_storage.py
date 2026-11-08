from __future__ import annotations

import uuid

import pytest

from app.services import object_storage as storage
from f0rge_db.organisation import tenant_id_ctx

pytestmark = pytest.mark.no_db


def test_storage_requires_tenant(monkeypatch):
    monkeypatch.setattr(storage.settings, "bucket_name", "")
    token = tenant_id_ctx.set(None)
    try:
        with pytest.raises(PermissionError):
            storage.save_bytes("logo.png", b"synthetic")
    finally:
        tenant_id_ctx.reset(token)


def test_storage_namespaces_and_rejects_foreign_reference(monkeypatch):
    monkeypatch.setattr(storage.settings, "bucket_name", "")
    first, second = uuid.uuid4(), uuid.uuid4()
    token = tenant_id_ctx.set(first)
    try:
        reference = storage.save_bytes("branding/logo.png", b"first")
        assert f"tenants/{first}/branding/logo.png" in reference
        assert storage.read_bytes(reference) == b"first"
        tenant_id_ctx.set(second)
        second_reference = storage.save_bytes("branding/logo.png", b"second")
        assert storage.read_bytes(second_reference) == b"second"
        for action in (storage.read_bytes, storage.delete_object, storage.presigned_get_url):
            with pytest.raises(PermissionError):
                action(reference)
        with pytest.raises(PermissionError):
            storage.overwrite_bytes(reference, b"overwrite")
    finally:
        tenant_id_ctx.reset(token)


@pytest.mark.parametrize("path", ["../logo", "/tmp/logo", "a/../../logo", "a\\logo"])
def test_storage_rejects_traversal(path, monkeypatch):
    monkeypatch.setattr(storage.settings, "bucket_name", "")
    token = tenant_id_ctx.set(uuid.uuid4())
    try:
        with pytest.raises(ValueError):
            storage.save_bytes(path, b"synthetic")
    finally:
        tenant_id_ctx.reset(token)
