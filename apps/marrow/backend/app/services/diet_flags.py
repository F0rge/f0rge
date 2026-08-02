from __future__ import annotations

from typing import Iterable, Literal, Optional

from pydantic import BaseModel

from app.models.dietary_ingredient import DietaryIngredient
from app.models.entry import Entry
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient

DietFlag = Literal["high-histamine", "high-fodmap", "gluten", "dairy"]

FLAG_VOCAB: frozenset[str] = frozenset({"high-histamine", "high-fodmap", "gluten", "dairy"})

# Score at or above this level is considered a high-histamine trigger; score 1 is
# "compatible with minor restrictions" on the SIGHI scale and does not warrant a flag.
HISTAMINE_FLAG_THRESHOLD = 2

_FODMAP_COLUMNS = (
    "fodmap_oligos",
    "fodmap_fructose",
    "fodmap_polyols",
    "fodmap_lactose",
)

# Used when a meal is marked lactose-free: keep every FODMAP axis except lactose,
# so a lactose-only "high" ingredient no longer drives the high-fodmap flag.
_FODMAP_COLUMNS_NO_LACTOSE = (
    "fodmap_oligos",
    "fodmap_fructose",
    "fodmap_polyols",
)


class PhotoScores(BaseModel):
    histamine_load: int  # sum of histamine_score across confirmed ingredients
    fodmap_count: int  # count of ingredients with any subcategory == "high"
    gluten_count: int  # count of ingredients with contains_gluten = true
    dairy_count: int  # count of ingredients with contains_dairy = true


class PhotoSignal(BaseModel):
    flags: set[str]  # subset of FLAG_VOCAB
    scores: PhotoScores
    sources: dict[str, list[str]]  # flag -> [ingredient_name, ...] for UI source line


def parse_diet_risk_csv(raw: Optional[str]) -> set[str]:
    """Parse the legacy ``diet_risk`` column into user-added flag strings.

    Drops ``"normal"`` and ``"not-sure"`` (they are not flags under the new model).
    Filters to FLAG_VOCAB so unknown tokens never leak downstream.
    """
    if not raw:
        return set()
    tokens = {t.strip() for t in raw.split(",") if t.strip()}
    return tokens & FLAG_VOCAB


def _aggregate(
    ingredients: Iterable[PhotoIngredient],
    *,
    gluten_free_ids: frozenset[int] = frozenset(),
    lactose_free_ids: frozenset[int] = frozenset(),
) -> PhotoSignal:
    """Walk a flat ingredient iterable and compute flags + scores + sources.

    Single source of truth for the flag/scoring rules; callers pass already-loaded
    ingredients (never triggers ORM lazy loads).

    ``gluten_free_ids`` / ``lactose_free_ids`` hold the ``analysis_id`` of meals the
    user marked gluten-free / lactose-free. For those meals we suppress the gluten
    flag entirely and drop the lactose axis from the high-fodmap check (dairy still
    counts). Only ``ing.analysis_id`` (a plain column) is read to decide this — never
    ``ing.analysis``, which would lazy-load and raise MissingGreenlet in async
    contexts that hold a detached session.
    """
    flags: set[str] = set()
    histamine_load = 0
    fodmap_ingredient_ids: set[int] = set()
    gluten_count = 0
    dairy_count = 0
    sources: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {flag: set() for flag in FLAG_VOCAB}

    def _add_source(flag: str, name: str) -> None:
        if name in seen[flag]:
            return
        seen[flag].add(name)
        sources.setdefault(flag, []).append(name)

    for ing in ingredients:
        score = ing.histamine_score or 0
        histamine_load += score

        if score >= HISTAMINE_FLAG_THRESHOLD:
            flags.add("high-histamine")
            _add_source("high-histamine", ing.name)

        cols = (
            _FODMAP_COLUMNS_NO_LACTOSE if ing.analysis_id in lactose_free_ids else _FODMAP_COLUMNS
        )
        if any(getattr(ing, col) == "high" for col in cols):
            flags.add("high-fodmap")
            fodmap_ingredient_ids.add(ing.id)
            _add_source("high-fodmap", ing.name)

        if ing.contains_gluten and ing.analysis_id not in gluten_free_ids:
            flags.add("gluten")
            gluten_count += 1
            _add_source("gluten", ing.name)

        if ing.contains_dairy:
            flags.add("dairy")
            dairy_count += 1
            _add_source("dairy", ing.name)

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


def flags_from_dietary_ingredients(items: list[DietaryIngredient]) -> list[str]:
    """Compute diet flag strings from catalog rows (no meal/analysis context)."""
    ingredients = [
        PhotoIngredient(
            id=0,
            analysis_id=0,
            name=item.canonical_name,
            canonical_name=item.canonical_name,
            histamine_score=item.histamine_score,
            fodmap_oligos=item.fodmap_oligos,
            fodmap_fructose=item.fodmap_fructose,
            fodmap_polyols=item.fodmap_polyols,
            fodmap_lactose=item.fodmap_lactose,
            contains_gluten=item.contains_gluten,
            contains_dairy=item.contains_dairy,
        )
        for item in items
    ]
    return sorted(_aggregate(ingredients).flags)


def compute_photo_signal(entry: Entry) -> PhotoSignal:
    """Aggregate confirmed PhotoIngredient rows under ``entry`` into flags + scores.

    Accepts the ORM Entry object (already eager-loaded via lazy='selectin').
    Does NOT re-query. If you find yourself adding a Session parameter, stop.
    """
    ingredients: list[PhotoIngredient] = []
    gluten_free_ids: set[int] = set()
    lactose_free_ids: set[int] = set()
    for photo in entry.photos:
        analysis = photo.analysis
        if analysis is None or analysis.status != "confirmed":
            continue
        if analysis.gluten_free_confirmed:
            gluten_free_ids.add(analysis.id)
        if analysis.lactose_free_confirmed:
            lactose_free_ids.add(analysis.id)
        ingredients.extend(analysis.ingredients)
    return _aggregate(
        ingredients,
        gluten_free_ids=frozenset(gluten_free_ids),
        lactose_free_ids=frozenset(lactose_free_ids),
    )


def compute_signal_from_analyses(
    analyses: Iterable[PhotoAnalysis],
) -> PhotoSignal:
    """Alternate entry point for callers that already hold confirmed PhotoAnalysis rows.

    Use when analyses come from a separate prefetch query (not from
    ``entry.photos[*].analysis``, which can trigger MissingGreenlet). Caller is
    responsible for status filtering.
    """
    ingredients: list[PhotoIngredient] = []
    gluten_free_ids: set[int] = set()
    lactose_free_ids: set[int] = set()
    for analysis in analyses:
        if analysis.gluten_free_confirmed:
            gluten_free_ids.add(analysis.id)
        if analysis.lactose_free_confirmed:
            lactose_free_ids.add(analysis.id)
        ingredients.extend(analysis.ingredients)
    return _aggregate(
        ingredients,
        gluten_free_ids=frozenset(gluten_free_ids),
        lactose_free_ids=frozenset(lactose_free_ids),
    )


def compute_effective_counts(
    signal: PhotoSignal,
    user_added_flags: Iterable[str],
) -> dict[str, int]:
    """Return per-flag counts that include manual additions.

    For each count flag (high-fodmap, gluten, dairy): photo count + 1 if the user
    asserted the flag and photos did NOT find it (so we don't double-count when
    both sources agree). ``histamine_load`` is photo-only — manual additions never
    bump it (a binary user assertion has no numeric dose).
    """
    user_set = set(user_added_flags)
    scores = signal.scores
    photo_flags = signal.flags

    def _bump(flag: str) -> int:
        return 1 if flag in user_set and flag not in photo_flags else 0

    return {
        "histamine_load": scores.histamine_load,
        "fodmap_count": scores.fodmap_count + _bump("high-fodmap"),
        "gluten_count": scores.gluten_count + _bump("gluten"),
        "dairy_count": scores.dairy_count + _bump("dairy"),
    }
