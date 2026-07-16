from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import text

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _MAX_READ_SQL, _mcp_user_id

_GUARD_ERROR = (
    "Query rejected by read_sql guardrails. "
    "Use typed tools (get_entry, list_entries, list_labs, get_lab_history, get_lab_markers, "
    "list_treatments, get_photo_analysis, list_photos_for_entry, list_trackers, "
    "get_tracker_logs, list_health_metrics, get_weather_for_entry, search_health_data) "
    "for common lookups."
)

_FORBIDDEN_PATTERNS = (
    re.compile(r"\bselect\s+into\b", re.IGNORECASE),
    re.compile(r"\bcopy\b", re.IGNORECASE),
    re.compile(r"\bpg_sleep\s*\(", re.IGNORECASE),
)


def _strip_sql_string_literals(query: str) -> str:
    """Replace quoted string contents with spaces so guards ignore literals."""
    out: list[str] = []
    in_single = False
    in_double = False
    i = 0
    while i < len(query):
        ch = query[i]
        if ch == "'" and not in_double:
            if in_single and i + 1 < len(query) and query[i + 1] == "'":
                out.append("  ")
                i += 2
                continue
            in_single = not in_single
            out.append(" ")
        elif ch == '"' and not in_single:
            in_double = not in_double
            out.append(" ")
        elif in_single or in_double:
            out.append(" ")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _has_semicolon_outside_strings(query: str) -> bool:
    stripped = _strip_sql_string_literals(query)
    idx = stripped.find(";")
    if idx < 0:
        return False
    return bool(stripped[idx + 1 :].strip())


def _validate_read_sql(query: str) -> str | None:
    # Guards run on a version with string literals blanked so '--', '/*', and
    # words like "copy" inside quoted text do not false-positive.
    outside = _strip_sql_string_literals(query)
    if "--" in outside or "/*" in outside:
        return _GUARD_ERROR
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(outside):
            return _GUARD_ERROR
    if _has_semicolon_outside_strings(query):
        return _GUARD_ERROR
    return None


def register_sql_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("read_sql")
    async def read_sql(query: str, ctx: Context = None) -> dict[str, Any]:
        """Execute an arbitrary SELECT query via the read-only connection.

        Prefer the typed tools above (get_entry, list_labs, get_photo_analysis, etc.)
        for common lookups.
        Use this only for queries requiring joins or aggregations not covered by them.
        DML/DDL (INSERT, UPDATE, DELETE, DROP, etc.) will fail with a permission error
        because the connection uses the healthtracker_ro role which has SELECT-only access.
        Capped at 500 rows.
        """
        guard_error = _validate_read_sql(query)
        if guard_error is not None:
            return {"error": guard_error}

        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            try:
                result = await db.execute(text(query))
                keys = list(result.keys())
                rows = result.fetchmany(_MAX_READ_SQL)
            except Exception as exc:
                return {"error": str(exc)}
        return {
            "columns": keys,
            "rows": [dict(zip(keys, row)) for row in rows],
        }
