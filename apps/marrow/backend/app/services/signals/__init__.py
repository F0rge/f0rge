from __future__ import annotations

from app.services.signals.attribution import (
    AttributionContext,
    ContributionRow,
    DayAttribution,
    build_attribution_context,
    compute_calibration_series,
    compute_day_attribution,
    largest_remainder_round,
)
from app.services.signals.baseline import BaselineResult, compute_baseline_residuals
from app.services.signals.effects import EffectResult, estimate_all_effects
from app.services.signals.interactions import InteractionResult, compute_interactions
from app.services.signals.quality import (
    ModelQuality,
    NoiseFloorEstimate,
    compute_model_quality,
    estimate_noise_floor,
    estimate_noise_floor_ar1,
)
from app.services.signals.unexplained import (
    UnexplainedResult,
    detect_unexplained,
    has_full_coverage,
    rank_tracker_proposals,
)
from app.services.signals.taxonomy import (
    FeatureClass,
    FeatureShape,
    TaxonomyError,
    resolve_class,
    resolve_shape,
)

__all__ = [
    "AttributionContext",
    "BaselineResult",
    "ContributionRow",
    "DayAttribution",
    "EffectResult",
    "FeatureClass",
    "FeatureShape",
    "InteractionResult",
    "ModelQuality",
    "NoiseFloorEstimate",
    "TaxonomyError",
    "UnexplainedResult",
    "build_attribution_context",
    "compute_baseline_residuals",
    "compute_calibration_series",
    "compute_day_attribution",
    "compute_interactions",
    "compute_model_quality",
    "detect_unexplained",
    "estimate_all_effects",
    "estimate_effect",
    "estimate_noise_floor",
    "estimate_noise_floor_ar1",
    "has_full_coverage",
    "largest_remainder_round",
    "rank_tracker_proposals",
    "resolve_class",
    "resolve_shape",
]
