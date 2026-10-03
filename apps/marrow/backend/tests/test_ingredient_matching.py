"""Pure unit tests for the catalogue matcher + resolver (no database)."""

from __future__ import annotations

import pytest

from app.services.ingredient_matching import CatalogEntry, CatalogMatcher, analyse, looks_composite
from app.services.ingredient_resolver import IngredientResolver, dedupe_names


def _entry(name: str, aliases: tuple[str, ...] = (), **overrides) -> CatalogEntry:
    values = {
        "category": "x",
        "histamine_score": 0,
        "fodmap_oligos": "low",
        "fodmap_fructose": "low",
        "fodmap_polyols": "low",
        "fodmap_lactose": "low",
        "contains_gluten": False,
        "contains_dairy": False,
    }
    values.update(overrides)
    return CatalogEntry(canonical_name=name, aliases=aliases, **values)


CATALOGUE = [
    _entry("oats", ("rolled oats", "porridge")),
    _entry("oat milk"),
    _entry("sunflower oil"),
    _entry("raisin", ("raisins",)),
    _entry("tomato"),
    _entry("tomato paste"),
    _entry("milk", contains_dairy=True),
    _entry("muesli", ("granola",), contains_gluten=True),
    _entry("bread"),
]


@pytest.mark.parametrize(
    ("text", "tokens", "quantity"),
    [
        ("Oats (40 g)", ("oat",), True),
        ("  40g   oats ", ("oat",), True),
        ("2 eggs", ("egg",), True),
        ("Crème fraîche", ("creme", "fraiche"), False),
        ("Gluten-Free Rolled Oats", ("gluten", "free", "rolled", "oat"), False),
        ("tomatoes", ("tomato",), False),
        ("glass", ("glass",), False),
    ],
)
def test_analyse(text: str, tokens: tuple[str, ...], quantity: bool) -> None:
    info = analyse(text)
    assert info.tokens == tokens
    assert info.has_quantity is quantity


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("oats", False),
        ("red bell pepper", False),
        ("Auchan gluten-free crunchy dried fruit muesli (40 g)", True),
        ("chicken noodle soup", True),
        ("ham and cheese sandwich", True),
        ("one two three four five", True),
    ],
)
def test_looks_composite(text: str, expected: bool) -> None:
    assert looks_composite(analyse(text)) is expected


@pytest.mark.parametrize(
    ("text", "match_type", "canonical"),
    [
        ("oats", "exact", "oats"),
        ("OATS ", "exact", "oats"),
        ("rolled oats", "alias", "oats"),
        ("raisins", "alias", "raisin"),
        ("oat", "normalised", "oats"),
        ("tomatoes", "normalised", "tomato"),
        ("oats (40 g)", "normalised", "oats"),
        ("sunflwer oil", "fuzzy", "sunflower oil"),
        ("gluten-free rolled oats", "token_subset", "oats"),
    ],
)
def test_matcher_top_candidate(text: str, match_type: str, canonical: str) -> None:
    top = CatalogMatcher(CATALOGUE).match(text)[0]
    assert (top.match_type, top.entry.canonical_name) == (match_type, canonical)


def test_matcher_ranks_direct_hit_before_related_partials() -> None:
    candidates = CatalogMatcher(CATALOGUE).match("oat")
    assert [c.entry.canonical_name for c in candidates][:2] == ["oats", "oat milk"]
    assert candidates[0].score > candidates[1].score


def test_matcher_empty_and_nonsense() -> None:
    matcher = CatalogMatcher(CATALOGUE)
    assert matcher.match("   ") == []
    assert matcher.match("(40 g)") == []
    assert matcher.match("zzqqxx") == []


@pytest.mark.parametrize(
    ("text", "status", "canonical", "flags"),
    [
        ("oats", "exact", "oats", True),
        ("granola", "alias", "muesli", True),
        ("tomatoes", "normalised", "tomato", True),
        ("gluten-free rolled oats", "approximate", None, False),
        ("milk chocolate", "approximate", None, False),
        ("sunflwer oil", "approximate", None, False),
        ("Auchan gluten-free crunchy dried fruit muesli (40 g)", "unmatched", None, False),
        ("quinoa", "unmatched", None, False),
    ],
)
def test_resolver_status_and_flag_attachment(
    text: str, status: str, canonical: str | None, flags: bool
) -> None:
    resolution = IngredientResolver(CATALOGUE).resolve(text)
    assert resolution.status == status
    assert (resolution.entry.canonical_name if resolution.entry else None) == canonical
    assert resolution.attaches_flags is flags


def test_resolver_product_string_keeps_suggestions_and_composite_flag() -> None:
    resolution = IngredientResolver(CATALOGUE).resolve(
        "Auchan gluten-free crunchy dried fruit muesli (40 g)"
    )
    assert resolution.composite_suspected is True
    assert [s["canonical_name"] for s in resolution.suggestions][:1] == ["muesli"]
    assert resolution.suggestions[0]["match_type"] == "token_subset"


def test_dedupe_names() -> None:
    kept, dropped = dedupe_names(["Oats", "oats ", "", "  ", "raisin", "RAISIN"])
    assert kept == ["Oats", "raisin"]
    assert dropped == ["oats", "RAISIN"]
