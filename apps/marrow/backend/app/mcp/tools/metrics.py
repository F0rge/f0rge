from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import or_, select

from app.mcp.observability import instrument_tool
from app.mcp.tools._common import (
    _HEALTH_METRIC_TYPE_FIELDS,
    _MAX_LIST_ROWS,
    _mcp_user_id,
    _validate_date,
)
from app.models.health_metrics import HealthMetric
from f0rge_db.tenant import owned_by_user


def _health_metric_to_dict(row: HealthMetric) -> dict[str, Any]:
    return {
        "id": row.id,
        "date": str(row.date),
        "hrv_mean": row.hrv_mean,
        "hrv_std": row.hrv_std,
        "resting_hr": row.resting_hr,
        "sleep_hours": row.sleep_hours,
        "sleep_deep_min": row.sleep_deep_min,
        "sleep_rem_min": row.sleep_rem_min,
        "sleep_core_min": row.sleep_core_min,
        "sleep_awake_min": row.sleep_awake_min,
        "sleep_deep_pct": row.sleep_deep_pct,
        "sleep_rem_pct": row.sleep_rem_pct,
        "sleep_efficiency": row.sleep_efficiency,
        "sleep_start": row.sleep_start,
        "sleep_end": row.sleep_end,
        "steps": row.steps,
        "active_minutes": row.active_minutes,
        "spo2": row.spo2,
        "wrist_temp_deviation": row.wrist_temp_deviation,
        "source": row.source,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def register_metrics_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("list_health_metrics")
    async def list_health_metrics(
        start_date: str,
        end_date: str,
        metric_type: Optional[str] = None,
        ctx: Context = None,
    ) -> dict[str, Any]:
        """List Apple Health auto-export metrics in an inclusive date range.

        Optional metric_type filters to rows with data in a category: sleep, hrv,
        activity, or vitals. Capped at 200 rows. For one day combined with entry
        and weather, prefer get_entry or get_weather_for_entry.
        """
        start = _validate_date(start_date, "start_date")
        end = _validate_date(end_date, "end_date")
        if metric_type is not None and metric_type not in _HEALTH_METRIC_TYPE_FIELDS:
            allowed = ", ".join(sorted(_HEALTH_METRIC_TYPE_FIELDS))
            raise ValueError(f"Invalid metric_type {metric_type!r}; expected one of: {allowed}")

        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            stmt = (
                select(HealthMetric)
                .where(
                    owned_by_user(HealthMetric.user_id),
                    HealthMetric.date >= start,
                    HealthMetric.date <= end,
                )
                .order_by(HealthMetric.date)
                .limit(_MAX_LIST_ROWS)
            )
            if metric_type is not None:
                fields = _HEALTH_METRIC_TYPE_FIELDS[metric_type]
                stmt = stmt.where(
                    or_(*(getattr(HealthMetric, field).is_not(None) for field in fields))
                )
            rows = (await db.execute(stmt)).scalars().all()

        return {"metrics": [_health_metric_to_dict(r) for r in rows]}
