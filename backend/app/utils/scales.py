from __future__ import annotations

# Single source of truth for core wellbeing scale polarity + on-disk domain.
# Stored values mix directions (overall/sleep_quality/neuro: higher = better;
# bloating/stress/joint_pain: higher = worse) and mix domains across
# schema_version (v<=3: 1-3, neuro -1/0/1; v>=4: 1-5 for every scale,
# including neuro -- see EntryCreate.schema_version's v4 comment). This module
# does not rewire any consumer (insights, etc.) -- it's the documented,
# tested mapping for future callers to use instead of re-deriving direction
# ad hoc per field.

SCALE_DIRECTION: dict[str, str] = {
    "overall": "higher_better",
    "sleep_quality": "higher_better",
    "neuro": "higher_better",
    "bloating": "higher_worse",
    "stress": "higher_worse",
    "joint_pain": "higher_worse",
}


def normalize_scale(field: str, value: int, schema_version: int) -> float:
    """Map a stored scale value to 0..1, where 1.0 always means "best"."""
    direction = SCALE_DIRECTION[field]
    if schema_version >= 4:
        lo, hi = 1, 5
    elif field == "neuro":
        lo, hi = -1, 1
    else:
        lo, hi = 1, 3

    fraction = (value - lo) / (hi - lo)
    return fraction if direction == "higher_better" else 1.0 - fraction
