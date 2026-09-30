"""Shared ingredient-name resolver for the MCP meal tools.

Classifies each submitted ingredient name against the caller's *active* catalogue:

* ``exact`` / ``alias`` / ``normalised``: the same ingredient -> catalogue flags are attached
* ``approximate``: a close but not identical catalogue entry (token subset such as
  "gluten-free rolled oats" -> ``oats``, or a typo) -> stored **unflagged** with suggestions,
  because silently attaching another ingredient's flags was the original bug
* ``unmatched``: nothing close, or a product string with a quantity/dish keyword such as
  "auchan ... muesli (40 g)" (suggestions still returned; archived catalogue entries count as
  unmatched) -> stored unflagged

It deliberately does not reuse ``IngredientLookupService.lookup`` (head-noun and ILIKE fallbacks
treat loose matches as real ones); that service is unchanged for the UI and Airflow callers.
Catalogue entries are never created here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.dietary_ingredient_catalog import DietaryIngredientCRUD
from app.services.ingredient_matching import (
    APPROXIMATE_TYPES,
    FLAG_ATTACHING_TYPES,
    CatalogEntry,
    CatalogMatcher,
    Candidate,
    analyse,
    is_product_string,
    looks_composite,
    top_suggestions,
)

APPROXIMATE = "approximate"
UNMATCHED = "unmatched"
MAX_SUGGESTIONS = 5
MAX_INGREDIENTS_PER_CALL = 40

COMPOSITE_HINT = (
    "Looks like a product or dish rather than a single ingredient. Split it into its "
    "constituent ingredients (from the pack's ingredient list or photo) and put the brand, "
    "pack size and quantity in the meal name."
)


@dataclass(frozen=True)
class Resolution:
    input_name: str
    status: str
    entry: Optional[CatalogEntry] = None
    matched_alias: Optional[str] = None
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    composite_suspected: bool = False

    @property
    def attaches_flags(self) -> bool:
        return self.entry is not None


def dedupe_names(names: Sequence[str]) -> tuple[list[str], list[str]]:
    """Strip blanks, drop case-insensitive duplicates. Returns (kept, duplicates_dropped)."""
    kept: list[str] = []
    seen: set[str] = set()
    dropped: list[str] = []
    for raw in names:
        name = (raw or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            dropped.append(name)
            continue
        seen.add(key)
        kept.append(name)
    return kept, dropped


class IngredientResolver:
    """Resolver over a catalogue snapshot (plain data, safe after the session closes)."""

    def __init__(self, entries: Sequence[CatalogEntry]) -> None:
        self.matcher = CatalogMatcher(entries)

    @classmethod
    async def for_current_user(cls, db: AsyncSession) -> "IngredientResolver":
        """Snapshot the current user's ACTIVE catalogue (archived rows are excluded)."""
        rows = await DietaryIngredientCRUD(db).list(include_archived=False)
        return cls([CatalogEntry.from_model(row) for row in rows])

    def resolve(self, name: str) -> Resolution:
        candidates = self.matcher.match(name, limit=MAX_SUGGESTIONS)
        info = analyse(name)
        best: Optional[Candidate] = candidates[0] if candidates else None
        if best is not None and best.match_type in FLAG_ATTACHING_TYPES:
            return Resolution(
                input_name=name,
                status=best.match_type,
                entry=best.entry,
                matched_alias=best.matched_alias,
                suggestions=top_suggestions(candidates[1:], MAX_SUGGESTIONS),
            )
        close = best is not None and best.match_type in APPROXIMATE_TYPES
        # A branded/quantified product string is never "approximately" one ingredient: the client
        # must decompose it. Suggestions are still returned.
        status = APPROXIMATE if close and not is_product_string(info) else UNMATCHED
        return Resolution(
            input_name=name,
            status=status,
            suggestions=top_suggestions(candidates, MAX_SUGGESTIONS),
            composite_suspected=looks_composite(info),
        )

    def resolve_many(self, names: Sequence[str]) -> list[Resolution]:
        return [self.resolve(name) for name in names]
