from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias
from app.services.ingredient_lookup import IngredientLookupService


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """In-memory SQLite for fast isolated tests."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    # Seed a minimal set of ingredients covering the test scenarios.
    session.add_all(
        [
            DietaryIngredient(canonical_name="tomato", histamine_score=2),
            DietaryIngredient(canonical_name="tomato paste", histamine_score=3),
            DietaryIngredient(canonical_name="basil", histamine_score=0),
            DietaryIngredient(canonical_name="flour", histamine_score=0),
            DietaryIngredient(canonical_name="parmesan cheese", histamine_score=2),
        ]
    )
    session.add_all(
        [
            IngredientAlias(alias="parmesan", canonical_name="parmesan cheese"),
            IngredientAlias(alias="tomate", canonical_name="tomato"),
        ]
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Step 1: exact canonical match
# ---------------------------------------------------------------------------


def test_exact_canonical_match(db: Session) -> None:
    svc = IngredientLookupService(db)
    result = svc.lookup("tomato")
    assert result is not None
    assert result.canonical_name == "tomato"
    assert result.histamine_score == 2


def test_exact_match_is_case_insensitive(db: Session) -> None:
    svc = IngredientLookupService(db)
    result = svc.lookup("TOMATO")
    assert result is not None
    assert result.canonical_name == "tomato"


def test_exact_match_strips_whitespace(db: Session) -> None:
    svc = IngredientLookupService(db)
    result = svc.lookup("  tomato  ")
    assert result is not None
    assert result.canonical_name == "tomato"


def test_multi_word_exact_match_preferred_over_head_noun(db: Session) -> None:
    """When the full string is itself a canonical, that should win — not
    fall through to the head-noun fallback that would resolve 'paste'."""
    svc = IngredientLookupService(db)
    result = svc.lookup("tomato paste")
    assert result is not None
    assert result.canonical_name == "tomato paste"
    assert result.histamine_score == 3


# ---------------------------------------------------------------------------
# Step 2: alias lookup
# ---------------------------------------------------------------------------


def test_alias_match(db: Session) -> None:
    svc = IngredientLookupService(db)
    result = svc.lookup("parmesan")
    assert result is not None
    assert result.canonical_name == "parmesan cheese"


def test_alias_match_french(db: Session) -> None:
    svc = IngredientLookupService(db)
    result = svc.lookup("tomate")
    assert result is not None
    assert result.canonical_name == "tomato"


# ---------------------------------------------------------------------------
# Step 3: head-noun fallback (the fix for "cherry tomato")
# ---------------------------------------------------------------------------


def test_head_noun_fallback_compound_name(db: Session) -> None:
    """Regression test: 'cherry tomato' should match 'tomato' via head-noun
    fallback even though no exact/alias/substring match exists."""
    svc = IngredientLookupService(db)
    result = svc.lookup("cherry tomato")
    assert result is not None
    assert result.canonical_name == "tomato"
    assert result.histamine_score == 2


def test_head_noun_fallback_with_qualifier(db: Session) -> None:
    svc = IngredientLookupService(db)
    result = svc.lookup("fresh basil")
    assert result is not None
    assert result.canonical_name == "basil"


def test_head_noun_fallback_with_compound_qualifier(db: Session) -> None:
    """Multi-word qualifier still resolves via the last word."""
    svc = IngredientLookupService(db)
    result = svc.lookup("extra fine wheat flour")
    assert result is not None
    assert result.canonical_name == "flour"


def test_head_noun_fallback_uses_alias_table(db: Session) -> None:
    """If the last word matches only an alias, follow it to the canonical."""
    svc = IngredientLookupService(db)
    result = svc.lookup("aged parmesan")
    assert result is not None
    assert result.canonical_name == "parmesan cheese"


def test_head_noun_not_used_for_single_word(db: Session) -> None:
    """Single-word inputs skip the head-noun branch (no last word to
    extract). They get exact, alias, or LIKE — but LIKE only matches when
    the search term is a substring of a canonical, not the other way
    around. So 'tomatoes' (plural) returns None unless an alias exists.
    Plural handling is a separate concern from compound names."""
    svc = IngredientLookupService(db)
    assert svc.lookup("tomatoes") is None


# ---------------------------------------------------------------------------
# Step 4: LIKE fallback (loose substring)
# ---------------------------------------------------------------------------


def test_like_fallback_when_search_is_substring_of_canonical(db: Session) -> None:
    """'basi' should LIKE-match 'basil'."""
    svc = IngredientLookupService(db)
    result = svc.lookup("basi")
    assert result is not None
    assert result.canonical_name == "basil"


# ---------------------------------------------------------------------------
# Empty / no-match
# ---------------------------------------------------------------------------


def test_empty_string_returns_none(db: Session) -> None:
    svc = IngredientLookupService(db)
    assert svc.lookup("") is None


def test_whitespace_only_returns_none(db: Session) -> None:
    svc = IngredientLookupService(db)
    assert svc.lookup("   ") is None


def test_no_match_returns_none(db: Session) -> None:
    svc = IngredientLookupService(db)
    assert svc.lookup("unicorn meat") is None


# ---------------------------------------------------------------------------
# Lookup chain priority
# ---------------------------------------------------------------------------


def test_alias_wins_over_head_noun(db: Session) -> None:
    """If a full-string alias exists, it should be used before falling back
    to the head-noun heuristic."""
    db.add(IngredientAlias(alias="san marzano tomato", canonical_name="tomato paste"))
    db.commit()
    svc = IngredientLookupService(db)
    result = svc.lookup("san marzano tomato")
    assert result is not None
    assert result.canonical_name == "tomato paste"  # via alias, not head noun


# ---------------------------------------------------------------------------
# Batch and suggest
# ---------------------------------------------------------------------------


def test_lookup_batch(db: Session) -> None:
    svc = IngredientLookupService(db)
    out = svc.lookup_batch(["tomato", "cherry tomato", "unicorn"])
    assert out["tomato"] is not None
    assert out["tomato"].canonical_name == "tomato"
    assert out["cherry tomato"] is not None
    assert out["cherry tomato"].canonical_name == "tomato"
    assert out["unicorn"] is None


def test_suggest_canonical_returns_substring_matches(db: Session) -> None:
    svc = IngredientLookupService(db)
    results = svc.suggest_canonical("tomato")
    names = {r.canonical_name for r in results}
    assert "tomato" in names
    assert "tomato paste" in names


def test_suggest_canonical_respects_limit(db: Session) -> None:
    svc = IngredientLookupService(db)
    results = svc.suggest_canonical("tomato", limit=1)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Expanded alias coverage (closes #15)
#
# The vision model surfaces a long tail of common food variants that
# previously rendered as "?" in the UI. These regressions guard the
# specific cases from the bug report plus the plurals/dressings batch.
# ---------------------------------------------------------------------------


@pytest.fixture
def db_with_expanded_aliases() -> Generator[Session, None, None]:
    """Fixture with the canonicals + aliases representative of the expanded
    coverage. Mirrors the rows produced by `scripts/build_aliases.py` for
    the cases under test, but stays self-contained so the test doesn't
    depend on the production DB."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    session.add_all(
        [
            DietaryIngredient(canonical_name="bell pepper", histamine_score=0),
            DietaryIngredient(canonical_name="black pepper", histamine_score=0),
            DietaryIngredient(canonical_name="tahini", histamine_score=0),
            DietaryIngredient(canonical_name="mixed salad greens", histamine_score=0),
            DietaryIngredient(canonical_name="microgreens", histamine_score=0),
            DietaryIngredient(canonical_name="tomato", histamine_score=2),
            DietaryIngredient(canonical_name="onion", histamine_score=0),
            DietaryIngredient(canonical_name="potato", histamine_score=0),
            DietaryIngredient(canonical_name="carrot", histamine_score=0),
            DietaryIngredient(canonical_name="mushroom", histamine_score=1),
            DietaryIngredient(canonical_name="egg", histamine_score=0),
            DietaryIngredient(canonical_name="mango", histamine_score=0),
        ]
    )
    session.add_all(
        [
            # Bell pepper colour variants
            IngredientAlias(alias="yellow bell pepper", canonical_name="bell pepper"),
            IngredientAlias(alias="red bell pepper", canonical_name="bell pepper"),
            IngredientAlias(alias="green bell pepper", canonical_name="bell pepper"),
            IngredientAlias(alias="orange bell pepper", canonical_name="bell pepper"),
            IngredientAlias(alias="sweet pepper", canonical_name="bell pepper"),
            IngredientAlias(alias="sweet peppers", canonical_name="bell pepper"),
            IngredientAlias(alias="bell peppers", canonical_name="bell pepper"),
            IngredientAlias(alias="capsicum", canonical_name="bell pepper"),
            # Microgreens / salad greens
            IngredientAlias(alias="microgreen", canonical_name="microgreens"),
            IngredientAlias(alias="micro greens", canonical_name="microgreens"),
            IngredientAlias(alias="sprouts", canonical_name="microgreens"),
            IngredientAlias(alias="baby greens", canonical_name="mixed salad greens"),
            IngredientAlias(alias="mixed greens", canonical_name="mixed salad greens"),
            IngredientAlias(alias="spring mix", canonical_name="mixed salad greens"),
            # Tahini-based dressings
            IngredientAlias(alias="tahini dressing", canonical_name="tahini"),
            IngredientAlias(alias="tahini sauce", canonical_name="tahini"),
            IngredientAlias(alias="sesame paste", canonical_name="tahini"),
            # Plurals
            IngredientAlias(alias="tomatoes", canonical_name="tomato"),
            IngredientAlias(alias="onions", canonical_name="onion"),
            IngredientAlias(alias="potatoes", canonical_name="potato"),
            IngredientAlias(alias="carrots", canonical_name="carrot"),
            IngredientAlias(alias="mushrooms", canonical_name="mushroom"),
            IngredientAlias(alias="eggs", canonical_name="egg"),
            IngredientAlias(alias="mangoes", canonical_name="mango"),
        ]
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_yellow_bell_pepper_resolves_to_bell_pepper(
    db_with_expanded_aliases: Session,
) -> None:
    """Regression for #15: 'yellow bell pepper' must hit the bell-pepper
    canonical, NOT 'black pepper' via a misleading head-noun fallback."""
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = svc.lookup("yellow bell pepper")
    assert result is not None
    assert result.canonical_name == "bell pepper"
    assert result.canonical_name != "black pepper"


@pytest.mark.parametrize(
    "variant",
    [
        "red bell pepper",
        "green bell pepper",
        "orange bell pepper",
        "sweet pepper",
        "sweet peppers",
        "bell peppers",
        "capsicum",
    ],
)
def test_bell_pepper_variants(db_with_expanded_aliases: Session, variant: str) -> None:
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = svc.lookup(variant)
    assert result is not None, f"{variant!r} did not resolve"
    assert result.canonical_name == "bell pepper"


def test_microgreen_resolves_to_microgreens(
    db_with_expanded_aliases: Session,
) -> None:
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = svc.lookup("microgreen")
    assert result is not None
    assert result.canonical_name == "microgreens"


def test_microgreens_singular_and_plural(
    db_with_expanded_aliases: Session,
) -> None:
    """Both 'microgreen' and 'microgreens' resolve — the canonical itself
    is plural, and the alias covers the singular form."""
    svc = IngredientLookupService(db_with_expanded_aliases)
    assert svc.lookup("microgreens").canonical_name == "microgreens"
    assert svc.lookup("microgreen").canonical_name == "microgreens"


def test_baby_greens_resolves_to_mixed_salad_greens(
    db_with_expanded_aliases: Session,
) -> None:
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = svc.lookup("baby greens")
    assert result is not None
    assert result.canonical_name == "mixed salad greens"


def test_tahini_dressing_resolves_to_tahini(
    db_with_expanded_aliases: Session,
) -> None:
    """Dressings inherit the dietary profile of their dominant base
    ingredient (tahini) rather than failing to match."""
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = svc.lookup("tahini dressing")
    assert result is not None
    assert result.canonical_name == "tahini"


@pytest.mark.parametrize(
    "plural,canonical",
    [
        ("tomatoes", "tomato"),
        ("onions", "onion"),
        ("potatoes", "potato"),
        ("carrots", "carrot"),
        ("mushrooms", "mushroom"),
        ("eggs", "egg"),
        ("mangoes", "mango"),
    ],
)
def test_common_plurals_resolve(
    db_with_expanded_aliases: Session, plural: str, canonical: str
) -> None:
    """Bare plural forms can't be resolved by the head-noun fallback (it
    operates on the LAST word of a multi-word input), so they need
    explicit aliases. This batch covers the most common ones surfaced by
    the vision model."""
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = svc.lookup(plural)
    assert result is not None, f"{plural!r} did not resolve"
    assert result.canonical_name == canonical
