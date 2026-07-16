from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


async def log_invocation(
    primitive: str,
    name: str,
    user_id: Any,
    duration_ms: float,
    row_count: Optional[int] = None,
) -> None:
    parts = [
        f"primitive={primitive}",
        f"name={name}",
        f"user_id={user_id}",
        f"duration_ms={duration_ms:.1f}",
    ]
    if row_count is not None:
        parts.append(f"row_count={row_count}")
    logger.info("mcp_invocation %s", " ".join(parts))


def _infer_row_count(result: Any) -> Optional[int]:
    if result is None:
        return 0
    if isinstance(result, dict):
        for key in ("results", "entries", "history", "labs", "treatments", "rows"):
            if key in result and isinstance(result[key], list):
                return len(result[key])
    return None


def instrument_tool(name: str) -> Callable[[F], F]:
    """Wrap an MCP tool handler with duration logging (no tokens or SQL bodies)."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from app.mcp.tools._common import _mcp_user_id

            ctx = kwargs.get("ctx")
            user_id = _mcp_user_id(ctx)
            start = time.perf_counter()
            result = await fn(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            await log_invocation("tool", name, user_id, duration_ms, _infer_row_count(result))
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
