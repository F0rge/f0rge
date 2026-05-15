from __future__ import annotations

from types import SimpleNamespace

from app.services.obsidian import (
    _compute_dietary_tags,
    _dietary_flags_line,
    _format_ingredient,
)


# ---------------------------------------------------------------------------
# Helpers for constructing mock ingredients / analyses
# ---------------------------------------------------------------------------


def make_ing(
    name: str = "test",
    *,
    histamine_score: int | None = None,
    contains_dairy: bool | None = False,
    contains_gluten: bool | None = False,
    fodmap_oligos: str | None = None,
    fodmap_fructose: str | None = None,
    fodmap_polyols: str | None = None,
    fodmap_lactose: str | None = None,
) -> SimpleNamespace:
    """Build a stand-in for a PhotoIngredient row. Attribute-only access."""
    return SimpleNamespace(
        name=name,
        histamine_score=histamine_score,
        contains_dairy=contains_dairy,
        contains_gluten=contains_gluten,
        fodmap_oligos=fodmap_oligos,
        fodmap_fructose=fodmap_fructose,
        fodmap_polyols=fodmap_polyols,
        fodmap_lactose=fodmap_lactose,
    )


def make_analysis(
    ingredients: list[SimpleNamespace],
    *,
    dish_name: str | None = None,
) -> SimpleNamespace:
    """Build a stand-in for a PhotoAnalysis row."""
    return SimpleNamespace(
        dish_name=dish_name,
        ingredients=ingredients,
    )


# ---------------------------------------------------------------------------
# _format_ingredient
# ---------------------------------------------------------------------------


def test_format_ingredient_no_flags() -> None:
    """Ingredient with no histamine/dairy/gluten/FODMAP yields just the name."""
    ing = make_ing(name="lettuce")
    assert _format_ingredient(ing) == "lettuce"


def test_format_ingredient_histamine_only() -> None:
    """Histamine score is annotated as H:<n>."""
    ing = make_ing(name="spinach", histamine_score=3)
    assert _format_ingredient(ing) == "spinach (H:3)"


def test_format_ingredient_histamine_zero_is_shown() -> None:
    """H:0 is meaningful (a real assessed score) — should not be elided here."""
    # _format_ingredient checks `is not None`, so 0 must be rendered.
    ing = make_ing(name="rice", histamine_score=0)
    assert _format_ingredient(ing) == "rice (H:0)"


def test_format_ingredient_histamine_none_is_omitted() -> None:
    """When histamine_score is None, no H: annotation appears."""
    ing = make_ing(name="apple", histamine_score=None)
    assert _format_ingredient(ing) == "apple"


def test_format_ingredient_dairy_flag() -> None:
    ing = make_ing(name="milk", contains_dairy=True)
    assert _format_ingredient(ing) == "milk (Dairy)"


def test_format_ingredient_gluten_flag() -> None:
    ing = make_ing(name="bread", contains_gluten=True)
    assert _format_ingredient(ing) == "bread (Gluten)"


def test_format_ingredient_single_fodmap_high() -> None:
    """A single FODMAP category at 'high' generates one tag."""
    ing = make_ing(name="onion", fodmap_oligos="high")
    assert _format_ingredient(ing) == "onion (F:O)"


def test_format_ingredient_fodmap_low_is_omitted() -> None:
    """FODMAP at 'low' or anything not equal to 'high' is not rendered."""
    ing = make_ing(
        name="strawberry",
        fodmap_oligos="low",
        fodmap_fructose="low",
        fodmap_polyols="low",
        fodmap_lactose="low",
    )
    assert _format_ingredient(ing) == "strawberry"


def test_format_ingredient_multiple_fodmaps_high() -> None:
    """Order matches FODMAP_ABBREV declaration: oligos, fructose, polyols, lactose."""
    ing = make_ing(
        name="apple",
        fodmap_fructose="high",
        fodmap_polyols="high",
    )
    assert _format_ingredient(ing) == "apple (F:Fr, F:P)"


def test_format_ingredient_all_fodmaps_high() -> None:
    """All four FODMAP groups at 'high' produce the full set, in declared order."""
    ing = make_ing(
        name="garlic",
        fodmap_oligos="high",
        fodmap_fructose="high",
        fodmap_polyols="high",
        fodmap_lactose="high",
    )
    assert _format_ingredient(ing) == "garlic (F:O, F:Fr, F:P, F:L)"


def test_format_ingredient_all_flags_combined() -> None:
    """Histamine -> Dairy -> Gluten -> FODMAPs, in that exact order."""
    ing = make_ing(
        name="lasagne",
        histamine_score=2,
        contains_dairy=True,
        contains_gluten=True,
        fodmap_lactose="high",
    )
    assert _format_ingredient(ing) == "lasagne (H:2, Dairy, Gluten, F:L)"


def test_format_ingredient_dairy_false_not_rendered() -> None:
    """contains_dairy=False/None must not produce 'Dairy'."""
    ing = make_ing(name="oat", contains_dairy=False)
    assert _format_ingredient(ing) == "oat"
    ing_none = make_ing(name="oat", contains_dairy=None)
    assert _format_ingredient(ing_none) == "oat"


# ---------------------------------------------------------------------------
# _dietary_flags_line
# ---------------------------------------------------------------------------


def test_dietary_flags_line_empty_ingredients() -> None:
    """No ingredients -> empty string (no 'Dietary flags:' header)."""
    a = make_analysis(ingredients=[])
    assert _dietary_flags_line(a) == ""


def test_dietary_flags_line_no_flags_set() -> None:
    """Ingredients with no flags -> empty string."""
    a = make_analysis([make_ing(name="lettuce"), make_ing(name="cucumber")])
    assert _dietary_flags_line(a) == ""


def test_dietary_flags_line_histamine_only() -> None:
    """Max histamine >= 1 produces 'Histamine <max>'."""
    a = make_analysis(
        [
            make_ing(name="x", histamine_score=1),
            make_ing(name="y", histamine_score=3),
            make_ing(name="z", histamine_score=2),
        ]
    )
    assert _dietary_flags_line(a) == "Dietary flags: Histamine 3"


def test_dietary_flags_line_histamine_zero_not_shown() -> None:
    """Max histamine == 0 is below the >=1 threshold; must not appear."""
    a = make_analysis(
        [
            make_ing(name="x", histamine_score=0),
            make_ing(name="y", histamine_score=0),
        ]
    )
    assert _dietary_flags_line(a) == ""


def test_dietary_flags_line_histamine_all_none() -> None:
    """All histamine_score=None -> max is None -> not shown."""
    a = make_analysis(
        [make_ing(name="x", histamine_score=None), make_ing(name="y")]
    )
    assert _dietary_flags_line(a) == ""


def test_dietary_flags_line_histamine_max_ignores_none() -> None:
    """A None histamine value among scored ones must not break the max."""
    a = make_analysis(
        [
            make_ing(name="x", histamine_score=None),
            make_ing(name="y", histamine_score=2),
            make_ing(name="z", histamine_score=None),
        ]
    )
    assert _dietary_flags_line(a) == "Dietary flags: Histamine 2"


def test_dietary_flags_line_dairy_only() -> None:
    a = make_analysis([make_ing(name="cheese", contains_dairy=True)])
    assert _dietary_flags_line(a) == "Dietary flags: Dairy"


def test_dietary_flags_line_gluten_only() -> None:
    a = make_analysis([make_ing(name="bread", contains_gluten=True)])
    assert _dietary_flags_line(a) == "Dietary flags: Gluten"


def test_dietary_flags_line_single_fodmap_category() -> None:
    a = make_analysis([make_ing(name="onion", fodmap_oligos="high")])
    assert _dietary_flags_line(a) == "Dietary flags: FODMAP-Oligos"


def test_dietary_flags_line_multiple_fodmap_categories() -> None:
    """Multiple FODMAP groups appear in their declared order."""
    a = make_analysis(
        [
            make_ing(name="apple", fodmap_fructose="high", fodmap_polyols="high"),
            make_ing(name="milk", fodmap_lactose="high"),
        ]
    )
    assert (
        _dietary_flags_line(a)
        == "Dietary flags: FODMAP-Fructose, FODMAP-Polyols, FODMAP-Lactose"
    )


def test_dietary_flags_line_fodmap_low_does_not_count() -> None:
    """'low' (not 'high') must not produce a FODMAP flag."""
    a = make_analysis(
        [
            make_ing(name="rice", fodmap_oligos="low", fodmap_fructose="low"),
        ]
    )
    assert _dietary_flags_line(a) == ""


def test_dietary_flags_line_mixed_flags() -> None:
    """Histamine, Dairy, Gluten, and FODMAPs combine in the declared order."""
    a = make_analysis(
        [
            make_ing(name="parmesan", histamine_score=2, contains_dairy=True),
            make_ing(name="pasta", contains_gluten=True),
            make_ing(name="garlic", fodmap_oligos="high"),
        ]
    )
    expected = "Dietary flags: Histamine 2, Dairy, Gluten, FODMAP-Oligos"
    assert _dietary_flags_line(a) == expected


def test_dietary_flags_line_all_flags() -> None:
    """All possible flags present simultaneously."""
    a = make_analysis(
        [
            make_ing(
                name="everything",
                histamine_score=3,
                contains_dairy=True,
                contains_gluten=True,
                fodmap_oligos="high",
                fodmap_fructose="high",
                fodmap_polyols="high",
                fodmap_lactose="high",
            )
        ]
    )
    expected = (
        "Dietary flags: Histamine 3, Dairy, Gluten, "
        "FODMAP-Oligos, FODMAP-Fructose, FODMAP-Polyols, FODMAP-Lactose"
    )
    assert _dietary_flags_line(a) == expected


# ---------------------------------------------------------------------------
# _compute_dietary_tags
# ---------------------------------------------------------------------------


def test_compute_dietary_tags_empty_list() -> None:
    """No confirmed analyses -> empty frontmatter and empty tags."""
    fm, tags = _compute_dietary_tags([])
    assert fm == {}
    assert tags == []


def test_compute_dietary_tags_single_no_flags() -> None:
    """Single confirmed analysis, no dietary flags: only food-photos field."""
    a = make_analysis(
        [make_ing(name="lettuce"), make_ing(name="cucumber")],
        dish_name="salad",
    )
    fm, tags = _compute_dietary_tags([a])
    assert fm == {"food-photos": "1", "dishes": '"salad"'}
    assert tags == []


def test_compute_dietary_tags_single_with_dish_name() -> None:
    """dish_name populates the 'dishes' frontmatter field, quoted."""
    a = make_analysis([make_ing(name="x")], dish_name="omelette")
    fm, _ = _compute_dietary_tags([a])
    assert fm["dishes"] == '"omelette"'


def test_compute_dietary_tags_dish_name_none_omits_field() -> None:
    """A None dish_name must not produce a 'dishes' frontmatter field."""
    a = make_analysis([make_ing(name="x")], dish_name=None)
    fm, _ = _compute_dietary_tags([a])
    assert "dishes" not in fm
    assert fm["food-photos"] == "1"


def test_compute_dietary_tags_multiple_dishes_joined() -> None:
    """Multiple dish names are joined by ', ' inside the quoted value."""
    a1 = make_analysis([make_ing(name="x")], dish_name="eggs")
    a2 = make_analysis([make_ing(name="y")], dish_name="toast")
    a3 = make_analysis([make_ing(name="z")], dish_name="coffee")
    fm, _ = _compute_dietary_tags([a1, a2, a3])
    assert fm["dishes"] == '"eggs, toast, coffee"'
    assert fm["food-photos"] == "3"


def test_compute_dietary_tags_dish_name_skips_falsy() -> None:
    """Empty/None dish names are filtered out of the joined list."""
    a1 = make_analysis([make_ing(name="x")], dish_name="eggs")
    a2 = make_analysis([make_ing(name="y")], dish_name=None)
    a3 = make_analysis([make_ing(name="z")], dish_name="")
    a4 = make_analysis([make_ing(name="w")], dish_name="toast")
    fm, _ = _compute_dietary_tags([a1, a2, a3, a4])
    assert fm["dishes"] == '"eggs, toast"'
    assert fm["food-photos"] == "4"


def test_compute_dietary_tags_max_histamine_across_analyses() -> None:
    """Max histamine aggregates across all ingredients in all analyses."""
    a1 = make_analysis(
        [
            make_ing(name="x", histamine_score=1),
            make_ing(name="y", histamine_score=2),
        ]
    )
    a2 = make_analysis(
        [
            make_ing(name="z", histamine_score=3),
            make_ing(name="w", histamine_score=0),
        ]
    )
    fm, tags = _compute_dietary_tags([a1, a2])
    assert fm["max-histamine"] == "3"
    assert "histamine-3" in tags


def test_compute_dietary_tags_max_histamine_zero_no_tag() -> None:
    """max-histamine == 0 records the field but does NOT add a histamine-N tag."""
    a = make_analysis(
        [
            make_ing(name="x", histamine_score=0),
            make_ing(name="y", histamine_score=0),
        ]
    )
    fm, tags = _compute_dietary_tags([a])
    assert fm["max-histamine"] == "0"
    assert not any(t.startswith("histamine-") for t in tags)


def test_compute_dietary_tags_max_histamine_all_none_omits_field() -> None:
    """No scored ingredients -> no max-histamine field, no histamine tag."""
    a = make_analysis(
        [make_ing(name="x"), make_ing(name="y", histamine_score=None)]
    )
    fm, tags = _compute_dietary_tags([a])
    assert "max-histamine" not in fm
    assert not any(t.startswith("histamine-") for t in tags)


def test_compute_dietary_tags_fodmap_tags_each_category() -> None:
    """Each FODMAP category at 'high' produces its own tag in declared order."""
    a = make_analysis(
        [
            make_ing(name="onion", fodmap_oligos="high"),
            make_ing(name="apple", fodmap_fructose="high"),
            make_ing(name="plum", fodmap_polyols="high"),
            make_ing(name="milk", fodmap_lactose="high"),
        ]
    )
    _, tags = _compute_dietary_tags([a])
    # Order is fixed: oligos, fructose, polyols, lactose
    fodmap_tags = [t for t in tags if t.startswith("fodmap-high-")]
    assert fodmap_tags == [
        "fodmap-high-oligos",
        "fodmap-high-fructose",
        "fodmap-high-polyols",
        "fodmap-high-lactose",
    ]


def test_compute_dietary_tags_fodmap_low_no_tag() -> None:
    """FODMAP 'low' values must not generate fodmap-high-* tags."""
    a = make_analysis(
        [
            make_ing(name="rice", fodmap_oligos="low", fodmap_fructose="low"),
        ]
    )
    _, tags = _compute_dietary_tags([a])
    assert not any(t.startswith("fodmap-high-") for t in tags)


def test_compute_dietary_tags_gluten_and_dairy_aggregation() -> None:
    """One ingredient with gluten and another with dairy each contribute."""
    a = make_analysis(
        [
            make_ing(name="bread", contains_gluten=True),
            make_ing(name="cheese", contains_dairy=True),
        ]
    )
    _, tags = _compute_dietary_tags([a])
    assert "contains-gluten" in tags
    assert "contains-dairy" in tags


def test_compute_dietary_tags_gluten_dairy_false_no_tag() -> None:
    """When all ingredients are flag-free, no gluten/dairy tags appear."""
    a = make_analysis(
        [
            make_ing(name="rice", contains_gluten=False, contains_dairy=False),
        ]
    )
    _, tags = _compute_dietary_tags([a])
    assert "contains-gluten" not in tags
    assert "contains-dairy" not in tags


def test_compute_dietary_tags_food_photos_count() -> None:
    """food-photos equals the number of confirmed analyses passed in."""
    analyses = [make_analysis([make_ing(name=f"x{i}")]) for i in range(5)]
    fm, _ = _compute_dietary_tags(analyses)
    assert fm["food-photos"] == "5"


def test_compute_dietary_tags_full_aggregation() -> None:
    """End-to-end: mixed analyses produce the correct combined fm and tags."""
    a1 = make_analysis(
        [
            make_ing(
                name="parmesan",
                histamine_score=2,
                contains_dairy=True,
                fodmap_lactose="high",
            ),
            make_ing(name="pasta", contains_gluten=True, fodmap_oligos="high"),
        ],
        dish_name="pasta carbonara",
    )
    a2 = make_analysis(
        [
            make_ing(name="apple", histamine_score=1, fodmap_fructose="high"),
        ],
        dish_name="fruit bowl",
    )
    fm, tags = _compute_dietary_tags([a1, a2])

    assert fm["food-photos"] == "2"
    assert fm["dishes"] == '"pasta carbonara, fruit bowl"'
    assert fm["max-histamine"] == "2"

    # Histamine tag from the max
    assert "histamine-2" in tags
    # FODMAP tags
    assert "fodmap-high-oligos" in tags
    assert "fodmap-high-fructose" in tags
    assert "fodmap-high-lactose" in tags
    assert "fodmap-high-polyols" not in tags
    # Gluten / dairy
    assert "contains-gluten" in tags
    assert "contains-dairy" in tags


def test_compute_dietary_tags_analyses_without_ingredients() -> None:
    """A confirmed analysis with zero ingredients still counts toward food-photos."""
    a = make_analysis([], dish_name="mystery dish")
    fm, tags = _compute_dietary_tags([a])
    assert fm["food-photos"] == "1"
    assert fm["dishes"] == '"mystery dish"'
    assert "max-histamine" not in fm
    assert tags == []
