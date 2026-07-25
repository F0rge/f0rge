from __future__ import annotations

from typing import Literal

from app.services.feature_matrix import STATIC_COLUMNS

FeatureClass = Literal["lever", "context", "mirror", "not-a-feature"]
FeatureShape = Literal["binary", "threshold", "linear", "interaction"]


class TaxonomyError(KeyError):
    """Raised when a feature-matrix column has no taxonomy mapping."""


# Static class assignments — Part B Layer 2 (signals_method.md)
CLASS_BY_COLUMN: dict[str, FeatureClass] = {
    # Not features
    "date": "not-a-feature",
    "schema_version": "not-a-feature",
    "period_of_day": "not-a-feature",
    "overall": "not-a-feature",
    # Mirrors (same-day self-report / logging)
    "bloating": "mirror",
    "joint_pain": "mirror",
    "neuro": "mirror",
    "stress": "mirror",
    "sick": "mirror",
    "stool_status": "mirror",
    "bristol_type": "mirror",
    "photo_count": "mirror",
    "ingredient_count": "mirror",
    # Levers
    "hot_shower": "lever",
    "alcohol_units": "lever",
    "caffeine_servings": "lever",
    "had_alcohol": "lever",
    "had_caffeine": "lever",
    "manual_extra_dairy": "lever",
    "manual_extra_fodmap": "lever",
    "manual_extra_gluten": "lever",
    "manual_extra_histamine": "lever",
    "histamine_load_sum": "lever",
    "histamine_load_max": "lever",
    "fodmap_oligos_sum": "lever",
    "fodmap_fructose_sum": "lever",
    "fodmap_polyols_sum": "lever",
    "fodmap_lactose_sum": "lever",
    "gluten_exposure": "lever",
    "dairy_exposure": "lever",
    "hm_sleep_hours": "lever",
    "hm_sleep_start": "lever",
    "hm_sleep_end": "lever",
    # Context — weather
    "wx_temp_mean": "context",
    "wx_temp_min": "context",
    "wx_temp_max": "context",
    "wx_humidity_mean": "context",
    "wx_pressure_mean": "context",
    "wx_pressure_delta": "context",
    "wx_condition": "context",
    # Context — sleep architecture
    "hm_sleep_deep_min": "context",
    "hm_sleep_rem_min": "context",
    "hm_sleep_core_min": "context",
    "hm_sleep_awake_min": "context",
    "hm_sleep_deep_pct": "context",
    "hm_sleep_rem_pct": "context",
    "hm_sleep_efficiency": "context",
    # Physiology — class resolved by lag (see _PHYSIOLOGY_MIRROR_COLUMNS)
    "hm_hrv_mean": "context",
    "hm_hrv_std": "context",
    "hm_resting_hr": "context",
    "hm_spo2": "context",
    "hm_wrist_temp_deviation": "context",
    # Activity — class resolved by lag (see _ACTIVITY_LEVER_COLUMNS)
    "hm_steps": "context",
    "hm_active_minutes": "context",
    # sleep_quality resolved by lag
    "sleep_quality": "mirror",
}

_PHYSIOLOGY_MIRROR_COLUMNS = frozenset(
    {
        "hm_hrv_mean",
        "hm_hrv_std",
        "hm_resting_hr",
        "hm_spo2",
        "hm_wrist_temp_deviation",
    }
)

_ACTIVITY_LEVER_COLUMNS = frozenset({"hm_steps", "hm_active_minutes"})

# Declared shapes per family — Layer 3 (signals_method.md)
SHAPE_BY_COLUMN: dict[str, FeatureShape] = {
    "hot_shower": "binary",
    "had_alcohol": "binary",
    "had_caffeine": "binary",
    "gluten_exposure": "binary",
    "dairy_exposure": "binary",
    "manual_extra_dairy": "binary",
    "manual_extra_fodmap": "binary",
    "manual_extra_gluten": "binary",
    "manual_extra_histamine": "binary",
    "alcohol_units": "threshold",
    "caffeine_servings": "threshold",
    "histamine_load_sum": "threshold",
    "histamine_load_max": "threshold",
    "fodmap_oligos_sum": "threshold",
    "fodmap_fructose_sum": "threshold",
    "fodmap_polyols_sum": "threshold",
    "fodmap_lactose_sum": "threshold",
    "hm_sleep_hours": "threshold",
    "hm_sleep_start": "threshold",
    "hm_sleep_end": "threshold",
    "hm_steps": "threshold",
    "hm_active_minutes": "threshold",
    "wx_temp_mean": "linear",
    "wx_temp_min": "linear",
    "wx_temp_max": "linear",
    "wx_humidity_mean": "linear",
    "wx_pressure_mean": "linear",
    "wx_pressure_delta": "linear",
    "wx_condition": "threshold",
    "hm_sleep_deep_min": "linear",
    "hm_sleep_rem_min": "linear",
    "hm_sleep_core_min": "linear",
    "hm_sleep_awake_min": "linear",
    "hm_sleep_deep_pct": "linear",
    "hm_sleep_rem_pct": "linear",
    "hm_sleep_efficiency": "linear",
    "hm_hrv_mean": "linear",
    "hm_hrv_std": "linear",
    "hm_resting_hr": "linear",
    "hm_spo2": "linear",
    "hm_wrist_temp_deviation": "linear",
    "sleep_quality": "threshold",
    "bloating": "linear",
    "joint_pain": "linear",
    "neuro": "linear",
    "stress": "linear",
    "sick": "binary",
    "stool_status": "threshold",
    "bristol_type": "threshold",
    "photo_count": "linear",
    "ingredient_count": "linear",
}

# Exhaustive mirror list for tests — every column that is mirror at lag 0
MIRROR_COLUMNS_LAG0: frozenset[str] = frozenset(
    {
        "bloating",
        "joint_pain",
        "neuro",
        "stress",
        "sick",
        "stool_status",
        "bristol_type",
        "sleep_quality",
        "photo_count",
        "ingredient_count",
        "hm_steps",
        "hm_active_minutes",
    }
    | _PHYSIOLOGY_MIRROR_COLUMNS
)


def _resolve_static_class(column: str, lag: int) -> FeatureClass | None:
    base = CLASS_BY_COLUMN.get(column)
    if base is None:
        return None
    if base == "not-a-feature":
        return base
    if column in _PHYSIOLOGY_MIRROR_COLUMNS:
        return "mirror" if lag == 0 else "context"
    if column in _ACTIVITY_LEVER_COLUMNS:
        return "lever" if lag >= 1 else "mirror"
    if column == "sleep_quality":
        return "mirror" if lag == 0 else "context"
    return base


def _resolve_dynamic_class(column: str, lag: int) -> FeatureClass | None:
    if column.startswith("sym_"):
        return "mirror"
    if column.startswith("supp_"):
        return "lever"
    if column.startswith("tx_") and column.endswith("_active"):
        return "lever"
    _ = lag
    return None


def resolve_class(column: str, lag: int = 0) -> FeatureClass:
    """Return taxonomy class for a feature-matrix column at the given lag."""
    if lag < 0:
        raise TaxonomyError(f"lag must be >= 0, got {lag}")

    static = _resolve_static_class(column, lag)
    if static is not None:
        return static

    dynamic = _resolve_dynamic_class(column, lag)
    if dynamic is not None:
        return dynamic

    raise TaxonomyError(f"unknown feature-matrix column: {column!r}")


def resolve_shape(column: str) -> FeatureShape:
    """Return declared effect shape for a feature-matrix column."""
    if column in SHAPE_BY_COLUMN:
        return SHAPE_BY_COLUMN[column]
    if column.startswith("supp_"):
        return "binary"
    if column.startswith("tx_") and column.endswith("_active"):
        return "binary"
    if column.startswith("sym_"):
        return "linear"
    raise TaxonomyError(f"unknown feature-matrix column: {column!r}")


def all_static_columns_classified() -> bool:
    """True when every STATIC_COLUMNS entry has a static or dynamic class rule."""
    for col in STATIC_COLUMNS:
        resolve_class(col, lag=0)
        if col not in ("date", "schema_version", "period_of_day", "overall"):
            resolve_shape(col)
    return True
