from __future__ import annotations

import datetime
import uuid
from typing import Any

from mcp.server.fastmcp import Context

from app.models.entry import Entry
from app.services.diet_flags import compute_photo_signal, parse_diet_risk_csv
from f0rge_db.tenant import current_user_id

_MAX_ENTRIES = 200
_MAX_LABS = 200
_MAX_LAB_HISTORY = 200
_MAX_LIST_ROWS = 200
_MAX_READ_SQL = 500

_HEALTH_METRIC_TYPE_FIELDS: dict[str, tuple[str, ...]] = {
    "sleep": (
        "sleep_hours",
        "sleep_deep_min",
        "sleep_rem_min",
        "sleep_core_min",
        "sleep_awake_min",
        "sleep_deep_pct",
        "sleep_rem_pct",
        "sleep_efficiency",
        "sleep_start",
        "sleep_end",
    ),
    "hrv": ("hrv_mean", "hrv_std"),
    "activity": ("steps", "active_minutes"),
    "vitals": ("resting_hr", "spo2", "wrist_temp_deviation"),
}


def _validate_date(value: str, field: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO date for {field}: {value!r}") from exc


def _mcp_user_id(ctx: Context | None) -> uuid.UUID:
    if ctx is not None and ctx.client_id:
        return uuid.UUID(ctx.client_id)
    import app.mcp.tools as mcp_tools

    access_token = mcp_tools.get_access_token()
    if access_token is not None and access_token.client_id:
        return uuid.UUID(access_token.client_id)
    return current_user_id()


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
