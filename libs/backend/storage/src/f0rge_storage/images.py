"""Generic image helpers (Pillow + HEIC/HEIF support).

Importing this module registers the HEIF opener so ``resize_image`` accepts
iPhone HEIC payloads anywhere the lib is used. ``register_heif_opener`` is
idempotent, so app-side re-registration is harmless.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()


def resize_image(file_bytes: bytes, max_dim: int = 2048, quality: int = 85) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    if img.width > max_dim or img.height > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
