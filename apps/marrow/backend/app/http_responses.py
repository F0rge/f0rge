"""HTTP response helpers. Keep FastAPI Response types out of storage wiring."""

from __future__ import annotations

from typing import Optional

from fastapi.responses import Response


def file_response(
    content: bytes,
    media_type: str,
    cache_control: str,
    content_disposition: Optional[str] = None,
) -> Response:
    """Return a binary body. Callers stream bytes, never a presigned Location."""
    headers = {"Cache-Control": cache_control}
    if content_disposition is not None:
        headers["Content-Disposition"] = content_disposition
    return Response(
        content=content,
        media_type=media_type,
        headers=headers,
    )


def jpeg_response(content: bytes, cache_control: str) -> Response:
    """Return a JPEG body. Callers cache the bytes, never a presigned Location."""
    return file_response(content, "image/jpeg", cache_control)
