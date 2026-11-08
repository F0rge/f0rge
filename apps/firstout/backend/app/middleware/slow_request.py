from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.http")

SLOW_REQUEST_SECONDS = 1.0


class SlowRequestMiddleware:
    """Warn when an HTTP request takes at least ``threshold_seconds``."""

    def __init__(self, app: ASGIApp, threshold_seconds: float = SLOW_REQUEST_SECONDS) -> None:
        self.app = app
        self.threshold_seconds = threshold_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - started
            if elapsed >= self.threshold_seconds:
                logger.warning(
                    "Slow request %s %s status=%s duration=%.3fs",
                    scope.get("method", ""),
                    scope.get("path", ""),
                    status_code,
                    elapsed,
                )
