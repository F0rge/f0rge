from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import Float, select, text

from f0rge_core.exceptions import ConflictError
from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _mcp_user_id
from app.models.embedding import Embedding
from app.services.llm.factory import build_embedding_client
from f0rge_db.tenant import owned_by_user


def register_search_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("search_health_data")
    async def search_health_data(query: str, k: int = 8, ctx: Context = None) -> dict[str, Any]:
        """Semantic search across all health data using vector similarity.

        Embeds the query and returns the closest chunks from the embedding table.
        Prefer this tool for open-ended questions. Use the typed tools for structured
        date-range or marker-specific lookups.
        """
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_main_session(user_id) as db:
            try:
                client = await build_embedding_client(db)
            except ConflictError as exc:
                return {"error": exc.detail}
            _, model = await mcp_tools.resolve_embedding_credentials(db)

        async with mcp_tools.scoped_ro_session(user_id) as ro_db:
            probe = await ro_db.execute(
                select(Embedding.id).where(owned_by_user(Embedding.user_id)).limit(1)
            )
            if probe.scalar_one_or_none() is None:
                return {
                    "results": [],
                    "note": "embedding table is empty — run the backfill script",
                }

        query_vec = await client.embed(query, model=model)

        async with mcp_tools.scoped_ro_session(user_id) as ro_db:
            stmt = (
                select(
                    Embedding.source_table,
                    Embedding.source_id,
                    Embedding.chunk_text,
                    (Embedding.embedding.op("<=>", return_type=Float())(query_vec)).label(
                        "distance"
                    ),
                )
                .where(
                    owned_by_user(Embedding.user_id),
                    Embedding.embedding_model == model,
                )
                .order_by(text("distance"))
                .limit(k)
            )
            rows = (await ro_db.execute(stmt)).all()

        return {
            "results": [
                {
                    "source_table": r.source_table,
                    "source_id": r.source_id,
                    "chunk_text": r.chunk_text,
                    "distance": float(r.distance),
                }
                for r in rows
            ]
        }
