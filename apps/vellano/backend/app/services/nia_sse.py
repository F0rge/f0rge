from __future__ import annotations

from typing import Mapping

from starlette.responses import Response

NIA_SSE_HEADERS: dict[str, str] = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def apply_nia_sse_headers(response: Response) -> Response:
    """Stop proxies (nginx, Railway, Next rewrite) from buffering AG-UI SSE."""
    for key, value in NIA_SSE_HEADERS.items():
        response.headers[key] = value
    if not response.media_type:
        response.media_type = "text/event-stream"
    return response


def nia_sse_header_map() -> Mapping[str, str]:
    return dict(NIA_SSE_HEADERS)
