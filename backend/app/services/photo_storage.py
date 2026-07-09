from __future__ import annotations

import io
import os

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from app.config import settings

# Register HEIF/HEIC support with Pillow at import time. iPhone defaults to
# HEIC for camera-roll photos, and without this call Image.open() raises
# UnidentifiedImageError on .heic uploads. Idempotent — safe to call once.
# The resize_image() pipeline below always re-encodes to JPEG, so this
# only widens the input format set, not the on-disk storage format.
register_heif_opener()


def resize_image(file_bytes: bytes, max_dim: int = 2048, quality: int = 85) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))

    # Handle EXIF rotation
    img = ImageOps.exif_transpose(img)

    # Convert to RGB for JPEG output (handles RGBA, palette, etc.)
    if img.mode not in ("RGB",):
        img = img.convert("RGB")

    # Resize if larger than max_dim
    if img.width > max_dim or img.height > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def save_photo(file_bytes: bytes, filename: str) -> None:
    photo_dir = os.path.abspath(settings.photo_dir)
    os.makedirs(photo_dir, exist_ok=True)
    local_path = os.path.join(photo_dir, filename)

    # Defense-in-depth: refuse to overwrite an existing file. The caller
    # (photo upload router) is responsible for picking a non-colliding
    # filename; if it ever gets that wrong, we'd rather fail loudly here
    # than silently destroy a prior photo on disk.
    if os.path.exists(local_path):
        raise FileExistsError(f"Refusing to overwrite existing photo file: {local_path}")

    with open(local_path, "wb") as f:
        f.write(file_bytes)


def delete_photo(filename: str) -> None:
    local_path = os.path.join(os.path.abspath(settings.photo_dir), filename)
    if os.path.exists(local_path):
        os.unlink(local_path)
