from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import text

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _MAX_READ_SQL, _mcp_user_id

_GUARD_ERROR = (
    "Query rejected by read_sql guardrails. "
    "Use typed tools (get_entry, list_entries, list_labs, get_lab_history, list_treatments) "
    "for common lookups."
)

_FORBIDDEN_PATTERNS = (
    re.compile(r"\bselect\s+into\b", re.IGNORECASE),
    re.compile(r"\bcopy\b", re.IGNORECASE),
    re.compile(r"\bpg_sleep\s*\(", re.IGNORECASE),
)


def _has_semicolon_outside_strings(query: str) -> bool:
    in_single = False
    in_double = False
    i = 0
    while i < len(query):
        ch = query[i]
        if ch == "'" and not in_double:
            if in_single and i + 1 < len(query) and query[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ";" and not in_single and not in_double:
            if query[i + 1 :].strip():
                return True
        i += 1
    return False


def _validate_read_sql(query: str) -> str | None:
    if "--" in query or "/*" in query:
        return _GUARD_ERROR
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(query):
            return _GUARD_ERROR
    if _has_semicolon_outside_strings(query):
        return _GUARD_ERROR
    return None


def register_sql_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("read_sql")
    async def read_sql(query: str, ctx: Context = None) -> dict[str, Any]:
        """Execute an arbitrary SELECT query via the read-only connection.

        Prefer the typed tools above (get_entry, list_labs, etc.) for common lookups.
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
