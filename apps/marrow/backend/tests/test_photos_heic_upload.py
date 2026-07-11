"""Regression test for HEIC upload support.

iPhone defaults to HEIC for camera-roll photos. Before pillow-heif was
registered, ``Image.open()`` raised ``UnidentifiedImageError`` on every
.heic upload and the photo router returned a 500 with an obscure traceback.

This test exercises ``resize_image()`` directly — the same function the
upload service calls in a worker thread — with both:

1. an HEIC payload (the case that used to fail), and
2. a PNG payload (the case that always worked) to assert the fix doesn't
   regress the existing decoder set.

If pillow-heif is missing or its opener isn't registered, generating the
HEIC payload itself will raise — so the test is self-bootstrapping.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.photo_storage import resize_image


def _png_bytes() -> bytes:
    img = Image.new("RGB", (32, 32), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _heic_bytes() -> bytes:
    """Encode a small RGB image as HEIC.

    pillow-heif >=0.18 exposes HEIF write support via the same Pillow
    save() interface once ``register_heif_opener()`` has run. If the
    package isn't installed, this raises ImportError or KeyError on save
    and the test fails fast with a clear cause.
    """
    img = Image.new("RGB", (32, 32), color="red")
    buf = io.BytesIO()
    img.save(buf, format="HEIF")
    return buf.getvalue()


def test_resize_image_accepts_heic_input() -> None:
    """The regression: a HEIC payload must round-trip through resize_image
    without UnidentifiedImageError, producing a valid JPEG."""
    out = resize_image(_heic_bytes())

    assert isinstance(out, bytes) and len(out) > 0
    # Output must be a valid JPEG, regardless of the input format.
    reopened = Image.open(io.BytesIO(out))
    assert reopened.format == "JPEG"
    assert reopened.size == (32, 32)


def test_resize_image_still_accepts_png_input() -> None:
    """Sanity: the pre-existing PNG path still works after the HEIF opener
    is registered. Guards against the (unlikely) case where pillow-heif's
    plugin order shadows another decoder."""
    out = resize_image(_png_bytes())

    assert isinstance(out, bytes) and len(out) > 0
    reopened = Image.open(io.BytesIO(out))
    assert reopened.format == "JPEG"
    assert reopened.size == (32, 32)


def test_resize_image_rejects_garbage() -> None:
    """Non-image bytes must still raise — pillow-heif must not silently
    accept arbitrary binary."""
    with pytest.raises(Exception):  # noqa: BLE001 — PIL/heif may raise different types
        resize_image(b"this is not an image, not even close")
