from __future__ import annotations

import io

import pytest
from PIL import Image

from f0rge_storage.images import resize_image
from f0rge_storage.object_storage import ObjectStorage, ObjectStorageConfig


def test_local_fallback_round_trip(tmp_path) -> None:
    storage = ObjectStorage(ObjectStorageConfig(local_dir=str(tmp_path)))
    assert not storage.enabled()

    ref = storage.save_bytes("photos/a.jpg", b"payload")
    assert ref == str(tmp_path / "photos" / "a.jpg")
    assert storage.exists_relative("photos/a.jpg")
    assert storage.read_relative("photos/a.jpg") == b"payload"
    assert storage.read_bytes(ref) == b"payload"

    with pytest.raises(FileExistsError):
        storage.save_bytes("photos/a.jpg", b"other")

    # Disabled storage never presigns and never treats refs as remote.
    assert storage.presigned_url_for_relative("photos/a.jpg") is None
    assert not storage.is_remote_storage_ref("photos/a.jpg")

    storage.delete_relative("photos/a.jpg")
    assert not storage.exists_relative("photos/a.jpg")


def test_key_layout() -> None:
    storage = ObjectStorage(ObjectStorageConfig(default_user_prefix="default-user"))
    assert storage.build_object_key("photos/a.jpg", user_id="u1") == "u1/photos/a.jpg"
    # Falls back to the default prefix and strips leading slashes.
    assert storage.build_object_key("/photos/a.jpg") == "default-user/photos/a.jpg"


def test_resolve_relative_key_local(tmp_path) -> None:
    storage = ObjectStorage(ObjectStorageConfig(local_dir=str(tmp_path)))
    storage.save_bytes("photos/a.jpg", b"payload")
    resolved = storage.resolve_relative_key("photos/a.jpg", user_id="u1")
    assert resolved == str(tmp_path / "photos" / "a.jpg")
    assert storage.resolve_relative_key("photos/missing.jpg", user_id="u1") is None


def test_resize_image_smoke() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (200, 100), "red").save(buf, format="PNG")

    out = resize_image(buf.getvalue(), max_dim=64)

    resized = Image.open(io.BytesIO(out))
    assert resized.format == "JPEG"
    assert resized.size == (64, 32)
