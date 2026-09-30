"""Pure, DB-free ingredient-name matching against a snapshot of one user's catalogue.

Used by the MCP ``search_ingredients`` tool and by the shared resolver
(``ingredient_resolver.py``). Nothing here touches SQLAlchemy sessions, so the
snapshot and every result are plain data that stay valid after a session closes.

Match types, best first (the first three may attach catalogue flags to a logged
ingredient; the rest are suggestions only):

* ``exact``        lowercased/stripped name equals a ``canonical_name``
* ``alias``        ... equals an alias of a canonical
* ``normalised``   equal after removing quantities/punctuation/accents and
                   singularising tokens ("Oat (40 g)" -> ``oats``)
* ``token_subset`` every token of the catalogue name occurs in the query
                   ("gluten-free rolled oats" -> ``oats``)
* ``fuzzy``        close spelling (typo) of a catalogue name or alias
* ``partial``      the query is only part of a longer catalogue name ("oat" -> ``oat milk``)
* ``prefix``       the query is the start of a catalogue name ("sunflow")
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable, Optional, Sequence

EXACT = "exact"
ALIAS = "alias"
NORMALISED = "normalised"
TOKEN_SUBSET = "token_subset"
FUZZY = "fuzzy"
PARTIAL = "partial"
PREFIX = "prefix"

# Match types that identify the same ingredient (safe to copy catalogue flags from).
FLAG_ATTACHING_TYPES = frozenset({EXACT, ALIAS, NORMALISED})
# Close-but-not-identical types: reported as "approximate", never flagged.
APPROXIMATE_TYPES = frozenset({TOKEN_SUBSET, FUZZY})

SCORE_EXACT = 1.0
SCORE_ALIAS = 0.98
SCORE_NORMALISED = 0.95
SCORE_NORMALISED_ALIAS = 0.93

MIN_PREFIX_LENGTH = 3
MIN_FUZZY_RATIO = 0.8
MAX_NAME_WORDS_BEFORE_COMPOSITE = 3

_WHITESPACE = re.compile(r"\s+")
_TOKEN = re.compile(r"[a-z0-9]+")
_UNITS = r"(?:kg|g|mg|ml|cl|dl|l|oz|lbs?|tbsp|tsp|cups?|pcs?|slices?|portions?|servings?)"
_QUANTITY = re.compile(rf"\(?\s*\b\d+(?:[.,]\d+)?\s*{_UNITS}\b\s*\)?")
_LEADING_COUNT = re.compile(r"^\s*\d+(?:[.,]\d+)?\s+(?=[a-z])")
_COMPOSITE_KEYWORDS = frozenset(
    {
        "muesli",
        "granola",
        "cereal",
        "bar",
        "sauce",
        "soup",
        "sandwich",
        "pizza",
        "burger",
        "lasagne",
        "lasagna",
        "curry",
        "stew",
        "salad",
        "meal",
    }
)


@dataclass(frozen=True)
class CatalogEntry:
    """One active catalogue row as plain data (attribute names mirror DietaryIngredient)."""

    canonical_name: str
    category: Optional[str]
    aliases: tuple[str, ...]
    histamine_score: Optional[int]
    fodmap_oligos: Optional[str]
    fodmap_fructose: Optional[str]
    fodmap_polyols: Optional[str]
    fodmap_lactose: Optional[str]
    contains_gluten: Optional[bool]
    contains_dairy: Optional[bool]

    @classmethod
    def from_model(cls, item: Any) -> "CatalogEntry":
        aliases = sorted({a.alias for a in item.aliases if a.alias != item.canonical_name})
        return cls(
            canonical_name=item.canonical_name,
            category=item.category,
            aliases=tuple(aliases),
            histamine_score=item.histamine_score,
            fodmap_oligos=item.fodmap_oligos,
            fodmap_fructose=item.fodmap_fructose,
            fodmap_polyols=item.fodmap_polyols,
            fodmap_lactose=item.fodmap_lactose,
            contains_gluten=item.contains_gluten,
            contains_dairy=item.contains_dairy,
        )


@dataclass(frozen=True)
class Candidate:
    entry: CatalogEntry
    match_type: str
    score: float
    matched_alias: Optional[str] = None


@dataclass(frozen=True)
class QueryInfo:
    raw: str
    tokens: tuple[str, ...]
    has_quantity: bool

    @property
    def key(self) -> str:
        return " ".join(self.tokens)


def collapse(text: str) -> str:
    return _WHITESPACE.sub(" ", text.strip().lower())


def _singular(token: str) -> str:
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith(("sses", "shes", "ches", "xes", "zes", "oes")):
        return token[:-2]
    if token.endswith(("ss", "us", "is")):
        return token
    if token.endswith("s"):
        return token[:-1]
    return token


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def analyse(text: str) -> QueryInfo:
    """Lowercase, drop quantities like ``(40 g)``, split into singularised tokens."""
    lowered = _strip_accents(collapse(text)).replace("'", "")
    without_quantity = _QUANTITY.sub(" ", lowered)
    has_quantity = without_quantity != lowered
    without_count = _LEADING_COUNT.sub("", without_quantity)
    if without_count != without_quantity:
        has_quantity = True
    tokens = tuple(_singular(t) for t in _TOKEN.findall(without_count))
    return QueryInfo(raw=collapse(text), tokens=tokens, has_quantity=has_quantity)


def looks_composite(info: QueryInfo) -> bool:
    """Heuristic: brand/quantity/many words/dish keywords suggest a product, not an ingredient."""
    if info.has_quantity:
        return True
    if len(info.tokens) > MAX_NAME_WORDS_BEFORE_COMPOSITE:
        return True
    return any(token in _COMPOSITE_KEYWORDS for token in info.tokens) or "ready meal" in info.key


def is_product_string(info: QueryInfo) -> bool:
    """Stronger than ``looks_composite``: a quantity or a product/dish keyword is present, so a
    partial catalogue hit (e.g. "...muesli (40 g)" -> ``muesli``) must not count as a match."""
    return info.has_quantity or any(t in _COMPOSITE_KEYWORDS for t in info.tokens)


class CatalogMatcher:
    """Index over a catalogue snapshot; ``match`` ranks candidates for one query."""

    def __init__(self, entries: Iterable[CatalogEntry]) -> None:
        self.entries: tuple[CatalogEntry, ...] = tuple(entries)
        self._by_name: dict[str, CatalogEntry] = {}
        self._by_alias: dict[str, CatalogEntry] = {}
        self._key_to_canonical: dict[str, CatalogEntry] = {}
        self._key_to_alias: dict[str, tuple[CatalogEntry, str]] = {}
        # (entry, label, alias-or-None, analysed label) for approximate scoring
        self._labels: list[tuple[CatalogEntry, Optional[str], QueryInfo]] = []
        for entry in self.entries:
            self._by_name[collapse(entry.canonical_name)] = entry
            canonical_info = analyse(entry.canonical_name)
            self._key_to_canonical.setdefault(canonical_info.key, entry)
            self._labels.append((entry, None, canonical_info))
            for alias in entry.aliases:
                self._by_alias.setdefault(collapse(alias), entry)
                alias_info = analyse(alias)
                self._key_to_alias.setdefault(alias_info.key, (entry, alias))
                self._labels.append((entry, alias, alias_info))

    def match(self, text: str, limit: int = 10) -> list[Candidate]:
        """Ranked candidates, best first. A direct hit (exact/alias/normalised) leads the list,
        followed by related approximate candidates for other catalogue entries."""
        info = analyse(text)
        if not info.raw or not info.tokens:
            return []
        direct = self._direct(info)
        approximate = self._approximate(info)
        if direct is None:
            return approximate[:limit]
        others = [c for c in approximate if c.entry.canonical_name != direct.entry.canonical_name]
        return [direct, *others][:limit]

    def _direct(self, info: QueryInfo) -> Optional[Candidate]:
        by_name = self._by_name.get(info.raw)
        if by_name is not None:
            return Candidate(by_name, EXACT, SCORE_EXACT)
        by_alias = self._by_alias.get(info.raw)
        if by_alias is not None:
            return Candidate(by_alias, ALIAS, SCORE_ALIAS, matched_alias=info.raw)
        canonical = self._key_to_canonical.get(info.key)
        if canonical is not None:
            return Candidate(canonical, NORMALISED, SCORE_NORMALISED)
        alias_hit = self._key_to_alias.get(info.key)
        if alias_hit is not None:
            entry, alias = alias_hit
            return Candidate(entry, NORMALISED, SCORE_NORMALISED_ALIAS, matched_alias=alias)
        return None

    def _approximate(self, info: QueryInfo) -> list[Candidate]:
        query_tokens = set(info.tokens)
        best: dict[str, Candidate] = {}
        for entry, alias, label in self._labels:
            scored = self._score_label(info, query_tokens, label)
            if scored is None:
                continue
            match_type, score = scored
            current = best.get(entry.canonical_name)
            if current is None or score > current.score:
                best[entry.canonical_name] = Candidate(entry, match_type, score, alias)
        return sorted(
            best.values(),
            key=lambda c: (-c.score, len(c.entry.canonical_name), c.entry.canonical_name),
        )

    @staticmethod
    def _score_label(
        info: QueryInfo, query_tokens: set[str], label: QueryInfo
    ) -> Optional[tuple[str, float]]:
        label_tokens = set(label.tokens)
        if not label_tokens:
            return None
        if label_tokens <= query_tokens:
            return TOKEN_SUBSET, round(0.55 + 0.25 * len(label_tokens) / len(query_tokens), 3)
        if query_tokens < label_tokens:
            return PARTIAL, round(0.4 + 0.15 * len(query_tokens) / len(label_tokens), 3)
        if len(info.key) >= MIN_PREFIX_LENGTH and label.key.startswith(info.key):
            return PREFIX, round(0.4 + 0.15 * len(info.key) / len(label.key), 3)
        if len(info.key) >= MIN_PREFIX_LENGTH:
            ratio = SequenceMatcher(None, info.key, label.key).ratio()
            if ratio >= MIN_FUZZY_RATIO:
                return FUZZY, round(0.4 + 0.3 * ratio, 3)
        return None


def compact_suggestion(candidate: Candidate) -> dict[str, Any]:
    return {
        "canonical_name": candidate.entry.canonical_name,
        "matched_alias": candidate.matched_alias,
        "match_type": candidate.match_type,
        "score": candidate.score,
    }


def top_suggestions(candidates: Sequence[Candidate], limit: int) -> list[dict[str, Any]]:
    return [compact_suggestion(c) for c in candidates[:limit]]
