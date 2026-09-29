from __future__ import annotations

import copy
from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import (
    _MAX_ENTRIES,
    _day_summary,
    _entry_to_day_dict,
    _mcp_user_id,
    _validate_date,
)
from app.models.entry import Entry
from app.models.photo import Photo
from app.schemas.entry import EntryCreate, EntryUpdate, SymptomEvent
from app.services.entries import EntryService
from app.services.entry_orchestrator import EntryOrchestrator
from app.services.entries import get_or_create_entry
from f0rge_db.tenant import owned_by_user


def register_days_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("get_day")
    async def get_day(date: str, ctx: Context = None) -> Optional[dict[str, Any]]:
        """One check-in: scores, symptoms, notes, and meal summaries for an ISO date."""
        parsed = _validate_date(date, "date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            stmt = (
                select(Entry)
                .where(owned_by_user(Entry.user_id), Entry.date == parsed)
                .options(selectinload(Entry.photos).selectinload(Photo.analysis))
            )
            row = (await db.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            return _entry_to_day_dict(row)

    @server.tool()
    @instrument_tool("list_days")
    async def list_days(start_date: str, end_date: str, ctx: Context = None) -> dict[str, Any]:
        """List check-ins in an inclusive date range with short summaries (max 200)."""
        start = _validate_date(start_date, "start_date")
        end = _validate_date(end_date, "end_date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            stmt = (
                select(Entry)
                .where(
                    owned_by_user(Entry.user_id),
                    Entry.date >= start,
                    Entry.date <= end,
                )
                .options(selectinload(Entry.photos))
                .order_by(Entry.date)
                .limit(_MAX_ENTRIES)
            )
            rows = (await db.execute(stmt)).scalars().all()
            return {"days": [_day_summary(r) for r in rows]}

    @server.tool()
    @instrument_tool("save_day")
    async def save_day(
        date: str,
        overall: Optional[int] = None,
        bloating: Optional[int] = None,
        joint_pain: Optional[int] = None,
        neuro: Optional[int] = None,
        sleep_quality: Optional[int] = None,
        stress: Optional[int] = None,
        stool_status: Optional[str] = None,
        bristol_type: Optional[int] = None,
        stool_completeness: Optional[str] = None,
        notes: Optional[str] = None,
        symptoms_json: Optional[dict[str, int]] = None,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Create or update a check-in: scores, symptoms map, stool fields, and notes."""
        parsed = _validate_date(date, "date")
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        patch = {
            k: v
            for k, v in {
                "overall": overall,
                "bloating": bloating,
                "joint_pain": joint_pain,
                "neuro": neuro,
                "sleep_quality": sleep_quality,
                "stress": stress,
                "stool_status": stool_status,
                "bristol_type": bristol_type,
                "stool_completeness": stool_completeness,
                "notes": notes,
                "symptoms_json": symptoms_json,
            }.items()
            if v is not None
        }

        async with mcp_tools.scoped_main_session(user_id) as db:
            orchestrator = EntryOrchestrator(db)
            existing = await EntryService(db).crud.get_by_date(parsed)
            if existing is None:
                body = EntryCreate(
                    date=parsed,
                    diet_risk="",
                    supplements="",
                    sick=False,
                    hot_shower=False,
                    joint_pain=patch.get("joint_pain", 0),
                    neuro=patch.get("neuro", 0),
                    **patch,
                )
                response = await orchestrator.create_entry(body)
            else:
                response = await orchestrator.update_entry(parsed, EntryUpdate(**patch))

            return {
                "date": str(response.date),
                "overall": response.overall,
                "bloating": response.bloating,
                "notes": response.notes,
                "symptoms_json": response.symptoms_json,
                "stool_status": response.stool_status,
            }

    @server.tool()
    @instrument_tool("log_flare")
    async def log_flare(
        date: str,
        key: str,
        severity: int,
        time: Optional[str] = None,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Log a symptom flare at a specific wall-clock time (HH:MM) on the given day."""
        parsed = _validate_date(date, "date")
        event = SymptomEvent(key=key, severity=severity, time=time)
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_main_session(user_id) as db:
            entry = await get_or_create_entry(db, parsed)
            events = copy.deepcopy(entry.symptom_events_json or [])
            events.append(event.model_dump())
            symptoms = dict(entry.symptoms_json or {})
            symptoms[key] = severity
            orchestrator = EntryOrchestrator(db)
            response = await orchestrator.update_entry(
                parsed,
                EntryUpdate(symptom_events=events, symptoms_json=symptoms),
            )
            return {
                "date": str(response.date),
                "symptom_events": [e.model_dump() for e in response.symptom_events],
                "symptoms_json": response.symptoms_json,
            }
