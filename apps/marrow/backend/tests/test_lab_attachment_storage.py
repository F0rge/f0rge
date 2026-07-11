from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from f0rge_core.exceptions import ValidationError
from app.services import lab_attachment_storage as storage_module
from app.services.lab_attachment_storage import LabAttachmentStorage


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> LabAttachmentStorage:
    """Point the storage root at tmp_path so we don't pollute the repo."""
    monkeypatch.setattr(storage_module, "_STORAGE_ROOT", str(tmp_path))
    return LabAttachmentStorage()


def test_save_pdf_writes_under_year_month_dir(
    storage: LabAttachmentStorage, tmp_path: Path
) -> None:
    content = b"%PDF-1.4\nfake pdf body\n%EOF"
    path = storage.save(content, "report.pdf", "application/pdf")

    assert os.path.exists(path)
    expected_month = datetime.utcnow().strftime("%Y-%m")
    assert expected_month in path
    assert path.endswith(".pdf")
    # Filename is sha256 of bytes — not the original filename.
    assert "report" not in os.path.basename(path)


def test_save_jpeg(storage: LabAttachmentStorage) -> None:
    path = storage.save(b"fake-jpeg-bytes", "scan.jpg", "image/jpeg")
    assert path.endswith(".jpg")
    assert os.path.exists(path)


def test_save_png(storage: LabAttachmentStorage) -> None:
    path = storage.save(b"fake-png-bytes", "scan.png", "image/png")
    assert path.endswith(".png")
    assert os.path.exists(path)


def test_save_webp(storage: LabAttachmentStorage) -> None:
    path = storage.save(b"fake-webp-bytes", "scan.webp", "image/webp")
    assert path.endswith(".webp")
    assert os.path.exists(path)


def test_save_unsupported_mime_raises(storage: LabAttachmentStorage) -> None:
    with pytest.raises(ValidationError) as exc_info:
        storage.save(b"some bytes", "evil.zip", "application/zip")
    assert "application/zip" in str(exc_info.value.detail)


def test_save_idempotent_same_bytes_same_path(
    storage: LabAttachmentStorage,
) -> None:
    content = b"identical bytes payload"
    p1 = storage.save(content, "first.pdf", "application/pdf")
    p2 = storage.save(content, "different-filename.pdf", "application/pdf")
    assert p1 == p2
    # File still on disk and not duplicated.
    assert os.path.exists(p1)


def test_save_different_bytes_different_path(
    storage: LabAttachmentStorage,
) -> None:
    p1 = storage.save(b"payload A", "a.pdf", "application/pdf")
    p2 = storage.save(b"payload B", "b.pdf", "application/pdf")
    assert p1 != p2


def test_save_filename_is_sha256(storage: LabAttachmentStorage) -> None:
    import hashlib

    content = b"deterministic content"
    expected_sha = hashlib.sha256(content).hexdigest()
    path = storage.save(content, "anything.pdf", "application/pdf")
    assert expected_sha in os.path.basename(path)
