from __future__ import annotations

import datetime
import uuid
from typing import Any

from mcp.server.fastmcp import Context

from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.diet_flags import compute_photo_signal, parse_diet_risk_csv
from f0rge_db.tenant import current_user_id

_MAX_ENTRIES = 200
_MAX_LABS = 200
_MAX_LAB_HISTORY = 200


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


def _ingredient_to_dict(row: PhotoIngredient) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "canonical_name": row.canonical_name,
        "visible": row.visible,
        "confidence": row.confidence,
        "user_edited": row.user_edited,
        "histamine_score": row.histamine_score,
        "fodmap_oligos": row.fodmap_oligos,
        "fodmap_fructose": row.fodmap_fructose,
        "fodmap_polyols": row.fodmap_polyols,
        "fodmap_lactose": row.fodmap_lactose,
        "contains_gluten": row.contains_gluten,
        "contains_dairy": row.contains_dairy,
    }


def _analysis_to_dict(analysis: PhotoAnalysis, photo_id: int) -> dict[str, Any]:
    return {
        "id": analysis.id,
        "photo_id": photo_id,
        "status": analysis.status,
        "dish_name": analysis.dish_name,
        "cuisine": analysis.cuisine,
        "dish_confidence": analysis.dish_confidence,
        "ingredients": [_ingredient_to_dict(i) for i in analysis.ingredients],
        "error_message": analysis.error_message,
        "gluten_free_confirmed": analysis.gluten_free_confirmed,
        "lactose_free_confirmed": analysis.lactose_free_confirmed,
        "created_at": analysis.created_at.isoformat(),
        "updated_at": analysis.updated_at.isoformat(),
    }


def _meal_summary(photo: Photo, analysis: PhotoAnalysis | None) -> dict[str, Any]:
    dish = None
    if analysis is not None:
        dish = analysis.dish_name
    if photo.label:
        dish = photo.label
    return {
        "photo_id": photo.id,
        "meal_id": photo.meal_id,
        "name": dish,
        "meal_time": photo.meal_time.isoformat() if photo.meal_time else None,
        "has_photo": photo.filename is not None,
        "analysis_status": analysis.status if analysis is not None else None,
    }


def _day_summary(row: Entry) -> dict[str, Any]:
    return {
        "date": str(row.date),
        "overall": row.overall,
        "bloating": row.bloating,
        "notes_preview": (row.notes or "")[:120] if row.notes else None,
        "meal_count": len(row.photos) if row.photos is not None else 0,
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
        "symptom_events": row.symptom_events_json or [],
        "period_of_day": row.period_of_day,
    }


def _entry_to_day_dict(row: Entry) -> dict[str, Any]:
    base = _entry_to_dict(row)
    meals: list[dict[str, Any]] = []
    for photo in row.photos or []:
        analysis = photo.analysis if photo.analysis is not None else None
        meals.append(_meal_summary(photo, analysis))
    base["meals"] = meals
    return base
