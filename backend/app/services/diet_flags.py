from __future__ import annotations

from pydantic import BaseModel

from app.models.entry import Entry

# Score at or above this level is considered a high-histamine trigger; score 1 is
# "compatible with minor restrictions" on the SIGHI scale and does not warrant a flag.
HISTAMINE_FLAG_THRESHOLD = 2


class PhotoScores(BaseModel):
    histamine_load: int  # sum of histamine_score across confirmed ingredients
    fodmap_count: int  # count of ingredients with any subcategory == "high"
    gluten_count: int  # count of ingredients with contains_gluten = true
    dairy_count: int  # count of ingredients with contains_dairy = true


class PhotoSignal(BaseModel):
    flags: set[str]  # subset of {"high-histamine", "high-fodmap", "gluten", "dairy"}
    scores: PhotoScores
    sources: dict[str, list[str]]  # flag -> [ingredient_name, ...] for UI source line


def compute_photo_signal(entry: Entry) -> PhotoSignal:
    """Aggregate confirmed PhotoIngredient rows under `entry` into flags + scores + sources.

    Accepts the ORM Entry object (already eager-loaded via lazy='selectin').
    Does NOT re-query. If you find yourself adding a Session parameter, stop and reconsider.
    """
    flags: set[str] = set()
    histamine_load = 0
    fodmap_ingredient_ids: set[int] = set()
    gluten_count = 0
    dairy_count = 0
    sources: dict[str, list[str]] = {}

    # Track seen names per flag to deduplicate sources
    seen_histamine: set[str] = set()
    seen_fodmap: set[str] = set()
    seen_gluten: set[str] = set()
    seen_dairy: set[str] = set()

    for photo in entry.photos:
        analysis = photo.analysis
        if analysis is None or analysis.status != "confirmed":
            continue
        for ing in analysis.ingredients:
            score = ing.histamine_score or 0
            histamine_load += score

            # --- high-histamine flag ---
            if score >= HISTAMINE_FLAG_THRESHOLD:
                flags.add("high-histamine")
                if ing.name not in seen_histamine:
                    seen_histamine.add(ing.name)
                    sources.setdefault("high-histamine", []).append(ing.name)

            # --- high-fodmap flag ---
            is_high_fodmap = any(
                getattr(ing, col) == "high"
                for col in (
                    "fodmap_oligos",
                    "fodmap_fructose",
                    "fodmap_polyols",
                    "fodmap_lactose",
                )
            )
            if is_high_fodmap:
                flags.add("high-fodmap")
                fodmap_ingredient_ids.add(ing.id)
                if ing.name not in seen_fodmap:
                    seen_fodmap.add(ing.name)
                    sources.setdefault("high-fodmap", []).append(ing.name)

            # --- gluten flag ---
            if ing.contains_gluten:
                flags.add("gluten")
                gluten_count += 1
                if ing.name not in seen_gluten:
                    seen_gluten.add(ing.name)
                    sources.setdefault("gluten", []).append(ing.name)

            # --- dairy flag ---
            if ing.contains_dairy:
                flags.add("dairy")
                dairy_count += 1
                if ing.name not in seen_dairy:
                    seen_dairy.add(ing.name)
                    sources.setdefault("dairy", []).append(ing.name)

    return PhotoSignal(
        flags=flags,
        scores=PhotoScores(
            histamine_load=histamine_load,
            fodmap_count=len(fodmap_ingredient_ids),
            gluten_count=gluten_count,
            dairy_count=dairy_count,
        ),
        sources=sources,
    )


def compute_effective_counts(
    entry: Entry,
    user_added_flags: list[str],
) -> dict[str, int]:
    """Return per-flag counts that include manual additions.

    For each flag (high-fodmap, gluten, dairy): photo count + 1 if the flag is in
    user_added_flags AND not already in photo-derived flags (so we don't double-count
    when both sources agree).
    histamine-load is photo-only — manual additions do NOT bump it (a binary assertion
    has no numeric dose).

    Returns a dict with the four keys used by the vault writer:
      {"histamine_load": int, "fodmap_count": int, "gluten_count": int, "dairy_count": int}
    """
    signal = compute_photo_signal(entry)
    scores = signal.scores
    photo_flags = signal.flags

    def _manual_bump(flag: str) -> int:
        """Return 1 if the user manually asserted this flag and photos didn't find it."""
        return 1 if flag in user_added_flags and flag not in photo_flags else 0

    return {
        "histamine_load": scores.histamine_load,
        "fodmap_count": scores.fodmap_count + _manual_bump("high-fodmap"),
        "gluten_count": scores.gluten_count + _manual_bump("gluten"),
        "dairy_count": scores.dairy_count + _manual_bump("dairy"),
    }
