from __future__ import annotations

import hashlib
import os
from datetime import datetime

from app.exceptions import ValidationError
from app.services import object_storage
from app.tenant import current_user_id

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
    """Persists uploaded PDF/image lab documents to disk or Tigris."""

    def save(self, file_bytes: bytes, filename: str, mime_type: str) -> str:
        del filename  # dedup is content-addressed; original name is not used on disk
        ext = _ALLOWED_MIMES.get(mime_type)
        if ext is None:
            raise ValidationError(f"Unsupported file type: {mime_type}")

        sha = hashlib.sha256(file_bytes).hexdigest()
        month_dir = datetime.utcnow().strftime("%Y-%m")
        dest_filename = f"{sha}.{ext}"
        relative_path = f"lab_attachments/{month_dir}/{dest_filename}"

        if object_storage.object_storage_enabled():
            user_id = str(current_user_id())
            key = object_storage.build_object_key(relative_path, user_id=user_id)
            if object_storage.object_exists(key):
                return key
            return object_storage.save_bytes(relative_path, file_bytes, user_id=user_id)

        storage_dir = os.path.join(_STORAGE_ROOT, month_dir)
        os.makedirs(storage_dir, exist_ok=True)
        dest_path = os.path.join(storage_dir, dest_filename)
        if not os.path.exists(dest_path):
            with open(dest_path, "wb") as handle:
                handle.write(file_bytes)
        return dest_path
