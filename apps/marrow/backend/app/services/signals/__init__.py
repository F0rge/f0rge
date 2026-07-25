from __future__ import annotations

from app.services.signals.baseline import BaselineResult, compute_baseline_residuals
from app.services.signals.effects import EffectResult, estimate_all_effects, estimate_effect
from app.services.signals.interactions import InteractionResult, compute_interactions
from app.services.signals.taxonomy import (
    FeatureClass,
    FeatureShape,
    TaxonomyError,
    resolve_class,
    resolve_shape,
)

__all__ = [
    "BaselineResult",
    "EffectResult",
    "FeatureClass",
    "FeatureShape",
    "InteractionResult",
    "TaxonomyError",
    "compute_baseline_residuals",
    "compute_interactions",
    "estimate_all_effects",
    "estimate_effect",
    "resolve_class",
    "resolve_shape",
]
