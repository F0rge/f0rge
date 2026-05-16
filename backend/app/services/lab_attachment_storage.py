from __future__ import annotations

import hashlib
import os
from datetime import datetime

from app.exceptions import ValidationError

_ALLOWED_MIMES: dict[str, str] = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

_STORAGE_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "lab_attachments")
)


class LabAttachmentStorage:
    """Persists uploaded PDF/image lab documents to disk.

    Files are stored at lab_attachments/YYYY-MM/<sha256>.<ext>.
    SHA256 filenames guarantee deduplication — the same file uploaded twice
    will map to the same path.
    """

    def save(self, file_bytes: bytes, filename: str, mime_type: str) -> str:
        ext = _ALLOWED_MIMES.get(mime_type)
        if ext is None:
            raise ValidationError(f"Unsupported file type: {mime_type}")

        sha = hashlib.sha256(file_bytes).hexdigest()
        month_dir = datetime.utcnow().strftime("%Y-%m")
        storage_dir = os.path.join(_STORAGE_ROOT, month_dir)
        os.makedirs(storage_dir, exist_ok=True)

        dest_filename = f"{sha}.{ext}"
        dest_path = os.path.join(storage_dir, dest_filename)

        if not os.path.exists(dest_path):
            with open(dest_path, "wb") as f:
                f.write(file_bytes)

        return dest_path
