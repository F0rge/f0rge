from __future__ import annotations

import asyncio
from typing import Optional
from urllib.parse import quote

from fastapi.responses import Response

from app.services.object_storage import read_bytes
from f0rge_core.exceptions import NotFoundError


def _content_disposition(filename: str) -> str:
    """ASCII ``filename`` for old clients, RFC 5987 ``filename*`` for the real name."""
    name = "".join(ch for ch in filename if ch.isprintable()).strip() or "download"
    fallback = "".join(ch if ch.isascii() and ch not in '"\\' else "_" for ch in name)
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def media_type_for_storage_key(storage_key: str) -> str:
    lower = storage_key.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    return "application/pdf"


async def serve_stored_pdf(
    storage_key: Optional[str],
    filename: str,
    not_found_message: str,
) -> Response:
    if not storage_key:
        raise NotFoundError(not_found_message)
    try:
        data = await asyncio.to_thread(read_bytes, storage_key)
    except FileNotFoundError as exc:
        raise NotFoundError(not_found_message) from exc
    return Response(
        content=data,
        media_type=media_type_for_storage_key(storage_key),
        headers={"Content-Disposition": _content_disposition(filename)},
    )
