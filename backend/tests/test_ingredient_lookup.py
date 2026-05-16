from __future__ import annotations

from typing import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias
from app.services.ingredient_lookup import IngredientLookupService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(async_db: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Seed a minimal set of ingredients covering the test scenarios."""
    async_db.add_all(
        [
            DietaryIngredient(canonical_name="tomato", histamine_score=2),
            DietaryIngredient(canonical_name="tomato paste", histamine_score=3),
            DietaryIngredient(canonical_name="basil", histamine_score=0),
            DietaryIngredient(canonical_name="flour", histamine_score=0),
            DietaryIngredient(canonical_name="parmesan cheese", histamine_score=2),
        ]
    )
    async_db.add_all(
        [
            IngredientAlias(alias="parmesan", canonical_name="parmesan cheese"),
            IngredientAlias(alias="tomate", canonical_name="tomato"),
        ]
    )
    await async_db.commit()
    yield async_db


# ---------------------------------------------------------------------------
# Step 1: exact canonical match
# ---------------------------------------------------------------------------


async def test_exact_canonical_match(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    result = await svc.lookup("tomato")
    assert result is not None
    assert result.canonical_name == "tomato"
    assert result.histamine_score == 2


async def test_exact_match_is_case_insensitive(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    result = await svc.lookup("TOMATO")
    assert result is not None
    assert result.canonical_name == "tomato"


async def test_exact_match_strips_whitespace(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    result = await svc.lookup("  tomato  ")
    assert result is not None
    assert result.canonical_name == "tomato"


async def test_multi_word_exact_match_preferred_over_head_noun(
    db: AsyncSession,
) -> None:
    svc = IngredientLookupService(db)
    result = await svc.lookup("tomato paste")
    assert result is not None
    assert result.canonical_name == "tomato paste"
    assert result.histamine_score == 3


# ---------------------------------------------------------------------------
# Step 2: alias lookup
# ---------------------------------------------------------------------------


async def test_alias_match(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    result = await svc.lookup("parmesan")
    assert result is not None
    assert result.canonical_name == "parmesan cheese"


async def test_alias_match_french(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    result = await svc.lookup("tomate")
    assert result is not None
    assert result.canonical_name == "tomato"


# ---------------------------------------------------------------------------
# Step 3: head-noun fallback (the fix for "cherry tomato")
# ---------------------------------------------------------------------------


async def test_head_noun_fallback_compound_name(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    result = await svc.lookup("cherry tomato")
    assert result is not None
    assert result.canonical_name == "tomato"
    assert result.histamine_score == 2


async def test_head_noun_fallback_with_qualifier(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    result = await svc.lookup("fresh basil")
    assert result is not None
    assert result.canonical_name == "basil"


async def test_head_noun_fallback_with_compound_qualifier(db: AsyncSession) -> None:
    """Multi-word qualifier still resolves via the last word."""
    svc = IngredientLookupService(db)
    result = await svc.lookup("extra fine wheat flour")
    assert result is not None
    assert result.canonical_name == "flour"


async def test_head_noun_fallback_uses_alias_table(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    result = await svc.lookup("aged parmesan")
    assert result is not None
    assert result.canonical_name == "parmesan cheese"


async def test_head_noun_not_used_for_single_word(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    assert await svc.lookup("tomatoes") is None


# ---------------------------------------------------------------------------
# Step 4: LIKE fallback (loose substring)
# ---------------------------------------------------------------------------


async def test_like_fallback_when_search_is_substring_of_canonical(
    db: AsyncSession,
) -> None:
    svc = IngredientLookupService(db)
    result = await svc.lookup("basi")
    assert result is not None
    assert result.canonical_name == "basil"


# ---------------------------------------------------------------------------
# Empty / no-match
# ---------------------------------------------------------------------------


async def test_empty_string_returns_none(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    assert await svc.lookup("") is None


async def test_whitespace_only_returns_none(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    assert await svc.lookup("   ") is None


async def test_no_match_returns_none(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    assert await svc.lookup("unicorn meat") is None


# ---------------------------------------------------------------------------
# Lookup chain priority
# ---------------------------------------------------------------------------


async def test_alias_wins_over_head_noun(db: AsyncSession) -> None:
    db.add(IngredientAlias(alias="san marzano tomato", canonical_name="tomato paste"))
    await db.commit()
    svc = IngredientLookupService(db)
    result = await svc.lookup("san marzano tomato")
    assert result is not None
    assert result.canonical_name == "tomato paste"  # via alias, not head noun


# ---------------------------------------------------------------------------
# Batch and suggest
# ---------------------------------------------------------------------------


async def test_lookup_batch(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    out = await svc.lookup_batch(["tomato", "cherry tomato", "unicorn"])
    assert out["tomato"] is not None
    assert out["tomato"].canonical_name == "tomato"
    assert out["cherry tomato"] is not None
    assert out["cherry tomato"].canonical_name == "tomato"
    assert out["unicorn"] is None


async def test_suggest_canonical_returns_substring_matches(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    results = await svc.suggest_canonical("tomato")
    names = {r.canonical_name for r in results}
    assert "tomato" in names
    assert "tomato paste" in names


async def test_suggest_canonical_respects_limit(db: AsyncSession) -> None:
    svc = IngredientLookupService(db)
    results = await svc.suggest_canonical("tomato", limit=1)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Expanded alias coverage (closes #15)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_with_expanded_aliases(
    async_db: AsyncSession,
) -> AsyncIterator[AsyncSession]:
    """Fixture with the canonicals + aliases representative of the expanded
    coverage."""
    async_db.add_all(
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
    async_db.add_all(
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
    await async_db.commit()
    yield async_db


async def test_yellow_bell_pepper_resolves_to_bell_pepper(
    db_with_expanded_aliases: AsyncSession,
) -> None:
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = await svc.lookup("yellow bell pepper")
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
async def test_bell_pepper_variants(
    db_with_expanded_aliases: AsyncSession, variant: str
) -> None:
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = await svc.lookup(variant)
    assert result is not None, f"{variant!r} did not resolve"
    assert result.canonical_name == "bell pepper"


async def test_microgreen_resolves_to_microgreens(
    db_with_expanded_aliases: AsyncSession,
) -> None:
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = await svc.lookup("microgreen")
    assert result is not None
    assert result.canonical_name == "microgreens"


async def test_microgreens_singular_and_plural(
    db_with_expanded_aliases: AsyncSession,
) -> None:
    """Both 'microgreen' and 'microgreens' resolve — the canonical itself
    is plural, and the alias covers the singular form."""
    svc = IngredientLookupService(db_with_expanded_aliases)
    a = await svc.lookup("microgreens")
    b = await svc.lookup("microgreen")
    assert a is not None and a.canonical_name == "microgreens"
    assert b is not None and b.canonical_name == "microgreens"


async def test_baby_greens_resolves_to_mixed_salad_greens(
    db_with_expanded_aliases: AsyncSession,
) -> None:
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = await svc.lookup("baby greens")
    assert result is not None
    assert result.canonical_name == "mixed salad greens"


async def test_tahini_dressing_resolves_to_tahini(
    db_with_expanded_aliases: AsyncSession,
) -> None:
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = await svc.lookup("tahini dressing")
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
async def test_common_plurals_resolve(
    db_with_expanded_aliases: AsyncSession, plural: str, canonical: str
) -> None:
    svc = IngredientLookupService(db_with_expanded_aliases)
    result = await svc.lookup(plural)
    assert result is not None, f"{plural!r} did not resolve"
    assert result.canonical_name == canonical
