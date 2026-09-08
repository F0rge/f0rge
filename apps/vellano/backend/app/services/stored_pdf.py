from __future__ import annotations

import asyncio
from typing import Optional

from fastapi.responses import Response

from app.services.object_storage import read_bytes
from f0rge_core.exceptions import NotFoundError


def _content_disposition(filename: str) -> str:
    safe = filename.replace('"', "")
    return f'attachment; filename="{safe}"'


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
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(filename)},
    )
