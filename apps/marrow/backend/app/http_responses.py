"""HTTP response helpers. Keep FastAPI Response types out of storage wiring."""

from __future__ import annotations

from fastapi.responses import Response


def jpeg_response(content: bytes, cache_control: str) -> Response:
    """Return a JPEG body. Callers cache the bytes, never a presigned Location."""
    return Response(
        content=content,
        media_type="image/jpeg",
        headers={"Cache-Control": cache_control},
    )
