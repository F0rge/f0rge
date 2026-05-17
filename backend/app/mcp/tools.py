from __future__ import annotations

import datetime
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import Float, func, select, text

from app.exceptions import ConflictError
from app.mcp.database import make_main_session, make_ro_session
from app.models.embedding import Embedding
from app.models.entry import Entry
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.models.treatment import Treatment
from app.services.diet_flags import compute_photo_signal, parse_diet_risk_csv
from app.services.llm.factory import (
    build_embedding_client,
    resolve_embedding_credentials,
)

_MAX_ENTRIES = 200
_MAX_LABS = 200
_MAX_LAB_HISTORY = 200
_MAX_READ_SQL = 500


def _validate_date(value: str, field: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO date for {field}: {value!r}") from exc


def register_tools(server: FastMCP) -> None:
    """Register all 7 MCP tools onto the server instance."""

    @server.tool()
    async def search_health_data(query: str, k: int = 8) -> dict[str, Any]:
        """Semantic search across all health data using vector similarity.

        Embeds the query and returns the closest chunks from the embedding table.
        Prefer this tool for open-ended questions. Use the typed tools for structured
        date-range or marker-specific lookups.
        """
        async with make_main_session() as db:
            try:
                client = await build_embedding_client(db)
            except ConflictError as exc:
                return {"error": exc.detail}
            _, model = await resolve_embedding_credentials(db)

        # Cheap probe before paying for the embedding API call.
        async with make_ro_session() as ro_db:
            probe = await ro_db.execute(text("SELECT 1 FROM embedding LIMIT 1"))
            if probe.scalar_one_or_none() is None:
                return {
                    "results": [],
                    "note": "embedding table is empty — run the backfill script",
                }

        query_vec = await client.embed(query, model=model)

        async with make_ro_session() as ro_db:
            # pgvector cosine distance operator <=>
            stmt = (
                select(
                    Embedding.source_table,
                    Embedding.source_id,
                    Embedding.chunk_text,
                    (
                        Embedding.embedding.op("<=>", return_type=Float())(query_vec)
                    ).label("distance"),
                )
                .where(Embedding.embedding_model == model)
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

    @server.tool()
    async def get_entry(date: str) -> Optional[dict[str, Any]]:
        """Fetch one health log entry by ISO date (YYYY-MM-DD).

        Returns null if no entry exists for that date.
        """
        parsed = _validate_date(date, "date")
        async with make_ro_session() as db:
            result = await db.execute(select(Entry).where(Entry.date == parsed))
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return _entry_to_dict(row)

    @server.tool()
    async def list_entries(start_date: str, end_date: str) -> dict[str, Any]:
        """List health log entries in an inclusive date range (YYYY-MM-DD).

        Capped at 200 rows. Use a narrower range if you need more granularity.
        """
        start = _validate_date(start_date, "start_date")
        end = _validate_date(end_date, "end_date")
        async with make_ro_session() as db:
            stmt = (
                select(Entry)
                .where(Entry.date >= start, Entry.date <= end)
                .order_by(Entry.date)
                .limit(_MAX_ENTRIES)
            )
            rows = (await db.execute(stmt)).scalars().all()
        return {"entries": [_entry_to_dict(r) for r in rows]}

    @server.tool()
    async def get_lab_history(marker_canonical_name: str) -> dict[str, Any]:
        """Fetch all recorded values for a lab marker by its canonical name.

        Results ordered newest-first. Capped at 200 rows.
        """
        async with make_ro_session() as db:
            stmt = (
                select(
                    LabMarker.value,
                    LabMarker.unit,
                    LabMarker.flag,
                    Lab.lab_date.label("date"),
                )
                .join(Lab, LabMarker.lab_id == Lab.id)
                .where(LabMarker.canonical_name == marker_canonical_name)
                .order_by(Lab.lab_date.desc())
                .limit(_MAX_LAB_HISTORY)
            )
            rows = (await db.execute(stmt)).all()
        return {
            "marker": marker_canonical_name,
            "history": [
                {
                    "date": str(r.date),
                    "value": r.value,
                    "unit": r.unit,
                    "flag": r.flag,
                }
                for r in rows
            ],
        }

    @server.tool()
    async def list_labs(start_date: str, end_date: str) -> dict[str, Any]:
        """List lab uploads with marker counts in an inclusive date range.

        Capped at 200 rows.
        """
        start = _validate_date(start_date, "start_date")
        end = _validate_date(end_date, "end_date")
        async with make_ro_session() as db:
            stmt = (
                select(Lab, func.count(LabMarker.id).label("marker_count"))
                .outerjoin(LabMarker, LabMarker.lab_id == Lab.id)
                .where(Lab.lab_date >= start, Lab.lab_date <= end)
                .group_by(Lab.id)
                .order_by(Lab.lab_date.desc())
                .limit(_MAX_LABS)
            )
            rows = (await db.execute(stmt)).all()
        return {
            "labs": [
                {
                    "id": r.Lab.id,
                    "date": str(r.Lab.lab_date),
                    "name": r.Lab.name,
                    "type": r.Lab.type,
                    "marker_count": r.marker_count,
                }
                for r in rows
            ]
        }

    @server.tool()
    async def list_treatments(active_only: bool = True) -> dict[str, Any]:
        """List treatments. When active_only=True, only treatments with no end_date are returned."""
        async with make_ro_session() as db:
            stmt = select(Treatment).order_by(Treatment.start_date.desc())
            if active_only:
                stmt = stmt.where(Treatment.end_date.is_(None))
            rows = (await db.execute(stmt)).scalars().all()
        return {
            "treatments": [
                {
                    "id": r.id,
                    "name": r.name,
                    "type": r.type,
                    "start_date": str(r.start_date),
                    "end_date": str(r.end_date) if r.end_date else None,
                    "dose": r.dose,
                    "notes": r.notes,
                }
                for r in rows
            ]
        }

    @server.tool()
    async def read_sql(query: str) -> dict[str, Any]:
        """Execute an arbitrary SELECT query via the read-only connection.

        Prefer the typed tools above (get_entry, list_labs, etc.) for common lookups.
        Use this only for queries requiring joins or aggregations not covered by them.
        DML/DDL (INSERT, UPDATE, DELETE, DROP, etc.) will fail with a permission error
        because the connection uses the healthtracker_ro role which has SELECT-only access.
        Capped at 500 rows.
        """
        async with make_ro_session() as db:
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


def _entry_to_dict(row: Entry) -> dict[str, Any]:
    _user_added = parse_diet_risk_csv(row.diet_risk)
    _signal = compute_photo_signal(row)
    _effective = sorted(_signal.flags | _user_added)
    return {
        "id": row.id,
        "date": str(row.date),
        "overall": row.overall,
        "bloating": row.bloating,
        "joint_pain": row.joint_pain,
        "neuro": row.neuro,
        "sleep_quality": row.sleep_quality,
        "stress": row.stress,
        # diet_risk: raw column preserved as audit trail (legacy CSV / user-added flags).
        "diet_risk": row.diet_risk,
        "effective_flags": _effective,
        "sick": row.sick,
        "hot_shower": row.hot_shower,
        "alcohol_units": row.alcohol_units,
        "caffeine_servings": row.caffeine_servings,
        "stool_status": row.stool_status,
        "bristol_type": row.bristol_type,
        "notes": row.notes,
        "symptoms_json": row.symptoms_json,
        "period_of_day": row.period_of_day,
    }
