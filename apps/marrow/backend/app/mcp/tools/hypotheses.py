from __future__ import annotations

import uuid
from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _mcp_user_id
from app.models.hypothesis import Hypothesis
from app.models.n_of_1_slot import NOf1Slot
from app.schemas.hypothesis import HypothesisUpdate, NOf1Upsert
from app.services.hypotheses import HypothesisService
from app.services.n_of_1 import NOf1Service


def _hypothesis_to_dict(row: Hypothesis) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "slug": row.slug,
        "title": row.title,
        "status": row.status,
        "layer": row.layer,
        "kill_test": row.kill_test,
        "next_move": row.next_move,
        "last_evidence": row.last_evidence,
        "cite": row.cite,
        "sort_order": row.sort_order,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _n_of_1_to_dict(row: NOf1Slot) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "change": row.change,
        "start": str(row.start),
        "watch_field": row.watch_field,
        "stop_rule": row.stop_rule,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def register_hypotheses_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("list_hypotheses")
    async def list_hypotheses(
        status: Optional[str] = None,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """List this user's tracked hypotheses (live, weakening, killed, parked).

        Killed rows stay on the scoreboard. This is a tracker, not a diagnosis.
        Optional status filter: live | weakening | killed | parked.
        """
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            rows = await HypothesisService(db).list(status)
        return {"hypotheses": [_hypothesis_to_dict(r) for r in rows]}

    @server.tool()
    @instrument_tool("update_hypothesis")
    async def update_hypothesis(
        hypothesis_id: Optional[str] = None,
        slug: Optional[str] = None,
        title: Optional[str] = None,
        status: Optional[str] = None,
        layer: Optional[int] = None,
        kill_test: Optional[str] = None,
        next_move: Optional[str] = None,
        last_evidence: Optional[str] = None,
        cite: Optional[str] = None,
        sort_order: Optional[int] = None,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Update one hypothesis by id or slug. Unspecified fields are left unchanged.

        Status values: live | weakening | killed | parked. Layer is 1, 2, or omit.
        There is no delete tool — mark status=killed instead.
        """
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        patch = HypothesisUpdate.model_validate(
            {
                key: value
                for key, value in {
                    "title": title,
                    "status": status,
                    "layer": layer,
                    "kill_test": kill_test,
                    "next_move": next_move,
                    "last_evidence": last_evidence,
                    "cite": cite,
                    "sort_order": sort_order,
                }.items()
                if value is not None
            }
        )
        async with mcp_tools.scoped_main_session(user_id) as db:
            service = HypothesisService(db)
            if hypothesis_id:
                row_id = uuid.UUID(hypothesis_id)
            elif slug:
                row_id = (await service.get_by_slug(slug)).id
            else:
                raise ValueError("Provide hypothesis_id or slug.")
            row = await service.update(row_id, patch)
        return _hypothesis_to_dict(row)

    @server.tool()
    @instrument_tool("get_n_of_1")
    async def get_n_of_1(ctx: Context = None) -> Optional[dict[str, Any]]:
        """Return the user's single n-of-1 experiment slot, or null if none is set."""
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            row = await NOf1Service(db).get()
        if row is None:
            return None
        return _n_of_1_to_dict(row)

    @server.tool()
    @instrument_tool("update_n_of_1")
    async def update_n_of_1(
        change: str,
        start: str,
        watch_field: str,
        stop_rule: str,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Create or replace the single n-of-1 experiment slot for this user."""
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        body = NOf1Upsert(
            change=change,
            start=start,
            watch_field=watch_field,
            stop_rule=stop_rule,
        )
        async with mcp_tools.scoped_main_session(user_id) as db:
            row = await NOf1Service(db).upsert(body)
        return _n_of_1_to_dict(row)
