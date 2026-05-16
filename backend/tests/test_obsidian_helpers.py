"""Tests for the Obsidian vault renderer.

Regression coverage for issue #13: the vision model emits ingredients with
`visible=true` (seen in the photo) and `visible=false` (inferred from
common recipes). The UI filters to visible=true; the vault must do the
same so it reflects exactly what the user reviewed and confirmed on
screen.
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.obsidian import (
    _compute_dietary_tags,
    _dietary_flags_line,
    _format_ingredient,
    _render_markdown,
)


# --- helpers -----------------------------------------------------------


def _ing(
    name: str,
    *,
    visible: bool = True,
    histamine_score: int | None = None,
    contains_dairy: bool | None = None,
    contains_gluten: bool | None = None,
    fodmap_oligos: str | None = None,
    fodmap_fructose: str | None = None,
    fodmap_polyols: str | None = None,
    fodmap_lactose: str | None = None,
) -> SimpleNamespace:
    """Build a PhotoIngredient-like duck-typed object for helper tests."""
    return SimpleNamespace(
        name=name,
        visible=visible,
        histamine_score=histamine_score,
        contains_dairy=contains_dairy,
        contains_gluten=contains_gluten,
        fodmap_oligos=fodmap_oligos,
        fodmap_fructose=fodmap_fructose,
        fodmap_polyols=fodmap_polyols,
        fodmap_lactose=fodmap_lactose,
    )


def _analysis(
    *,
    ingredients: list[SimpleNamespace],
    dish_name: str = "carbonara",
) -> SimpleNamespace:
    return SimpleNamespace(
        dish_name=dish_name,
        dish_confidence=0.9,
        ingredients=ingredients,
    )


# --- _format_ingredient: behavior unchanged ----------------------------


def test_format_ingredient_unchanged_for_visible_item() -> None:
    """The per-ingredient formatter is intentionally unaware of `visible` —
    it formats whatever it is handed. Filtering happens at the callers."""
    ing = _ing("tomato", histamine_score=2, contains_dairy=False)
    assert _format_ingredient(ing) == "tomato (H:2)"


def test_format_ingredient_unchanged_for_invisible_item() -> None:
    """Even an invisible ingredient should format correctly if passed in.
    The filter is the caller's job, not the formatter's."""
    ing = _ing("garlic", visible=False, histamine_score=1)
    assert _format_ingredient(ing) == "garlic (H:1)"


def test_format_ingredient_with_all_flags() -> None:
    ing = _ing(
        "parmesan",
        histamine_score=3,
        contains_dairy=True,
        contains_gluten=False,
        fodmap_lactose="high",
    )
    out = _format_ingredient(ing)
    assert out.startswith("parmesan (")
    assert "H:3" in out
    assert "Dairy" in out
    assert "F:L" in out


# --- _format_ingredient: moderate FODMAP markers (issue #14) -----------


def test_format_ingredient_moderate_lactose_emits_marker() -> None:
    """Heavy cream is the canonical example: moderate-lactose alone must
    still surface in the vault, with a `?` suffix to distinguish from high."""
    ing = _ing(
        "heavy cream",
        contains_dairy=True,
        fodmap_lactose="moderate",
    )
    out = _format_ingredient(ing)
    assert "F:L?" in out
    # Must NOT emit the high marker.
    assert "F:L," not in out
    assert not out.endswith("F:L)")


def test_format_ingredient_moderate_each_fodmap_category() -> None:
    """Every FODMAP category should emit a `?`-suffixed marker at moderate."""
    ing = _ing(
        "mixed",
        fodmap_oligos="moderate",
        fodmap_fructose="moderate",
        fodmap_polyols="moderate",
        fodmap_lactose="moderate",
    )
    out = _format_ingredient(ing)
    assert "F:O?" in out
    assert "F:Fr?" in out
    assert "F:P?" in out
    assert "F:L?" in out


def test_format_ingredient_high_and_moderate_mixed_categories() -> None:
    """When one category is `high` and another is `moderate`, both render
    with their own marker (high gets the bare abbrev, moderate gets `?`)."""
    ing = _ing(
        "complex",
        fodmap_lactose="high",
        fodmap_oligos="moderate",
    )
    out = _format_ingredient(ing)
    # Lactose at high: bare marker, not `F:L?`.
    assert "F:L" in out
    assert "F:L?" not in out
    # Oligos at moderate: `?` marker.
    assert "F:O?" in out


def test_format_ingredient_low_fodmap_emits_no_marker() -> None:
    """A `low` FODMAP value must not emit any marker."""
    ing = _ing("rice", fodmap_oligos="low", fodmap_lactose="low")
    out = _format_ingredient(ing)
    assert "F:" not in out


# --- _dietary_flags_line: must skip visible=false ----------------------


def test_dietary_flags_line_ignores_invisible_histamine() -> None:
    """A hidden high-histamine ingredient must NOT inflate the dish's
    histamine flag — the user never saw it in the UI."""
    analysis = _analysis(
        ingredients=[
            _ing("lettuce", histamine_score=0),
            _ing("aged-parmesan-inferred", visible=False, histamine_score=3),
        ]
    )
    line = _dietary_flags_line(analysis)
    # max histamine from visible items only is 0 → no Histamine flag.
    assert "Histamine" not in line


def test_dietary_flags_line_uses_visible_histamine() -> None:
    """When the visible items have histamine ≥1, the flag should show."""
    analysis = _analysis(
        ingredients=[
            _ing("tomato", histamine_score=2),
            _ing("hidden-thing", visible=False, histamine_score=0),
        ]
    )
    assert "Histamine 2" in _dietary_flags_line(analysis)


def test_dietary_flags_line_ignores_invisible_dairy_and_gluten() -> None:
    """Hidden dairy/gluten flags must not appear in the per-photo summary."""
    analysis = _analysis(
        ingredients=[
            _ing("rice", contains_dairy=False, contains_gluten=False),
            _ing("hidden-cheese", visible=False, contains_dairy=True),
            _ing("hidden-wheat", visible=False, contains_gluten=True),
        ]
    )
    line = _dietary_flags_line(analysis)
    assert "Dairy" not in line
    assert "Gluten" not in line


def test_dietary_flags_line_ignores_invisible_fodmap() -> None:
    """Hidden FODMAP-high items must not appear in the per-photo summary."""
    analysis = _analysis(
        ingredients=[
            _ing("plain-rice", fodmap_oligos="low"),
            _ing("hidden-onion", visible=False, fodmap_oligos="high"),
            _ing("hidden-pear", visible=False, fodmap_polyols="high"),
        ]
    )
    line = _dietary_flags_line(analysis)
    assert "FODMAP-Oligos" not in line
    assert "FODMAP-Polyols" not in line


def test_dietary_flags_line_all_invisible_yields_empty() -> None:
    """If every ingredient is invisible, no flags are produced."""
    analysis = _analysis(
        ingredients=[
            _ing(
                "hidden-cheese",
                visible=False,
                histamine_score=3,
                contains_dairy=True,
                fodmap_lactose="high",
            ),
        ]
    )
    assert _dietary_flags_line(analysis) == ""


# --- _dietary_flags_line: moderate FODMAP support (issue #14) ----------


def test_dietary_flags_line_moderate_only_emits_suffixed_label() -> None:
    """All-moderate FODMAP visible items must surface with `(moderate)` suffix."""
    analysis = _analysis(
        ingredients=[
            _ing("heavy cream", contains_dairy=True, fodmap_lactose="moderate"),
        ]
    )
    line = _dietary_flags_line(analysis)
    assert "FODMAP-Lactose (moderate)" in line
    # Must NOT emit the bare (high) form for this category.
    assert "FODMAP-Lactose," not in line
    assert not line.endswith("FODMAP-Lactose")


def test_dietary_flags_line_high_beats_moderate_same_category() -> None:
    """If any visible ingredient is `high` for a category, suppress the
    `(moderate)` form for that same category — high wins."""
    analysis = _analysis(
        ingredients=[
            _ing("cheese", fodmap_lactose="high"),
            _ing("milk", fodmap_lactose="moderate"),
        ]
    )
    line = _dietary_flags_line(analysis)
    assert "FODMAP-Lactose" in line
    # No `(moderate)` flag for the same category.
    assert "FODMAP-Lactose (moderate)" not in line


def test_dietary_flags_line_high_one_category_moderate_other() -> None:
    """High for one category and moderate for another should produce both,
    each with its own marker."""
    analysis = _analysis(
        ingredients=[
            _ing("onion", fodmap_oligos="high"),
            _ing("banana", fodmap_fructose="moderate"),
        ]
    )
    line = _dietary_flags_line(analysis)
    assert "FODMAP-Oligos" in line
    assert "FODMAP-Oligos (moderate)" not in line
    assert "FODMAP-Fructose (moderate)" in line


def test_dietary_flags_line_moderate_ignored_when_invisible() -> None:
    """Invisible moderate items must not surface (same rule as `high`)."""
    analysis = _analysis(
        ingredients=[
            _ing("rice", fodmap_lactose="low"),
            _ing("hidden-cream", visible=False, fodmap_lactose="moderate"),
        ]
    )
    line = _dietary_flags_line(analysis)
    assert "FODMAP-Lactose" not in line


# --- _compute_dietary_tags: aggregates only visible --------------------


def test_compute_dietary_tags_skips_invisible_max_histamine() -> None:
    """The frontmatter `max-histamine` must reflect only visible items."""
    analysis = _analysis(
        ingredients=[
            _ing("tomato", histamine_score=1),
            _ing("hidden-aged-cheese", visible=False, histamine_score=3),
        ]
    )
    fm, tags = _compute_dietary_tags([analysis])
    assert fm.get("max-histamine") == "1"
    assert "histamine-1" in tags
    assert "histamine-3" not in tags


def test_compute_dietary_tags_skips_invisible_fodmap_and_gluten() -> None:
    """Invisible items must not contribute fodmap-* or contains-* tags."""
    analysis = _analysis(
        ingredients=[
            _ing("rice", contains_gluten=False),
            _ing("hidden-wheat", visible=False, contains_gluten=True),
            _ing("hidden-onion", visible=False, fodmap_oligos="high"),
        ]
    )
    _, tags = _compute_dietary_tags([analysis])
    assert "contains-gluten" not in tags
    assert "fodmap-high-oligos" not in tags


def test_compute_dietary_tags_keeps_dishes_even_with_all_invisible() -> None:
    """An analysis with only invisible ingredients still has a confirmed
    dish_name and should appear in the `dishes` aggregate. Only the
    ingredient-derived tags should disappear."""
    analysis = _analysis(
        dish_name="mystery dish",
        ingredients=[
            _ing("hidden-thing", visible=False, histamine_score=3),
        ],
    )
    fm, tags = _compute_dietary_tags([analysis])
    assert fm["food-photos"] == "1"
    assert "mystery dish" in fm["dishes"]
    # No ingredient-derived data should leak through.
    assert "max-histamine" not in fm
    assert tags == []


def test_compute_dietary_tags_aggregates_visible_across_analyses() -> None:
    """Aggregation across multiple confirmed analyses still filters per-row."""
    a1 = _analysis(
        ingredients=[
            _ing("tomato", histamine_score=2),
            _ing("hidden-pepper", visible=False, histamine_score=3),
        ]
    )
    a2 = _analysis(
        dish_name="salad",
        ingredients=[
            _ing("lettuce", contains_dairy=False),
            _ing("hidden-blue-cheese", visible=False, contains_dairy=True),
        ],
    )
    fm, tags = _compute_dietary_tags([a1, a2])
    # max-histamine is 2 (visible only), not 3.
    assert fm["max-histamine"] == "2"
    assert "histamine-2" in tags
    assert "contains-dairy" not in tags


# --- _compute_dietary_tags: moderate FODMAP frontmatter tags (issue #14)


def test_compute_dietary_tags_moderate_only_emits_moderate_tag() -> None:
    """Visible moderate-only FODMAP items must yield a `fodmap-moderate-*` tag."""
    analysis = _analysis(
        ingredients=[
            _ing("heavy cream", contains_dairy=True, fodmap_lactose="moderate"),
        ]
    )
    _, tags = _compute_dietary_tags([analysis])
    assert "fodmap-moderate-lactose" in tags
    # No high tag for a category that only has moderate.
    assert "fodmap-high-lactose" not in tags


def test_compute_dietary_tags_high_beats_moderate_same_category() -> None:
    """For one category, when both `high` and `moderate` ingredients exist,
    only the `high` tag is emitted (no duplicate moderate tag)."""
    analysis = _analysis(
        ingredients=[
            _ing("cheese", fodmap_lactose="high"),
            _ing("milk", fodmap_lactose="moderate"),
        ]
    )
    _, tags = _compute_dietary_tags([analysis])
    assert "fodmap-high-lactose" in tags
    assert "fodmap-moderate-lactose" not in tags


def test_compute_dietary_tags_high_one_category_moderate_other() -> None:
    """High in one category and moderate in another should produce both tags
    — high tag for the high category, moderate tag for the moderate category."""
    analysis = _analysis(
        ingredients=[
            _ing("onion", fodmap_oligos="high"),
            _ing("banana", fodmap_fructose="moderate"),
        ]
    )
    _, tags = _compute_dietary_tags([analysis])
    assert "fodmap-high-oligos" in tags
    assert "fodmap-moderate-oligos" not in tags
    assert "fodmap-moderate-fructose" in tags
    assert "fodmap-high-fructose" not in tags


def test_compute_dietary_tags_moderate_ignored_when_invisible() -> None:
    """Invisible moderate ingredients must not contribute any tag."""
    analysis = _analysis(
        ingredients=[
            _ing("rice", fodmap_lactose="low"),
            _ing("hidden-cream", visible=False, fodmap_lactose="moderate"),
        ]
    )
    _, tags = _compute_dietary_tags([analysis])
    assert "fodmap-moderate-lactose" not in tags
    assert "fodmap-high-lactose" not in tags


def test_compute_dietary_tags_moderate_aggregates_across_analyses() -> None:
    """Cross-analysis: a moderate level in one photo + high in another for
    the same category should still resolve to only the high tag."""
    a1 = _analysis(
        ingredients=[_ing("milk", fodmap_lactose="moderate")],
    )
    a2 = _analysis(
        dish_name="cheese plate",
        ingredients=[_ing("cheese", fodmap_lactose="high")],
    )
    _, tags = _compute_dietary_tags([a1, a2])
    assert "fodmap-high-lactose" in tags
    assert "fodmap-moderate-lactose" not in tags


# --- end-to-end via _render_markdown -----------------------------------
#
# _render_markdown no longer touches the DB — the async caller pre-fetches all
# data and passes it as plain objects. The fixture builds Entry/Photo objects
# in-memory (via async_db.add + commit so auto-IDs populate for FK targets)
# and constructs the analyses dict that the renderer consumes.


async def _seed_entry_with_mixed_visibility(
    db: AsyncSession,
) -> tuple[Entry, list[Photo], dict[int, PhotoAnalysis]]:
    entry = Entry(
        date=datetime.date(2026, 5, 15),
        overall=2,
        bloating=0,
        stool_status="normal",
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        hot_shower=False,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    photo = Photo(
        entry_id=entry.id,
        filename="2026-05-15_photo-1.jpg",
        original_filename="lunch.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)

    analysis = PhotoAnalysis(
        photo_id=photo.id,
        status="confirmed",
        dish_name="pasta carbonara",
        dish_confidence=0.92,
        model_id="google/gemini-3-flash-preview",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    ingredients = [
        # Visible — should appear in markdown.
        PhotoIngredient(
            analysis_id=analysis.id,
            name="spaghetti",
            visible=True,
            confidence=0.95,
            user_edited=False,
            contains_gluten=True,
        ),
        PhotoIngredient(
            analysis_id=analysis.id,
            name="egg",
            visible=True,
            confidence=0.9,
            user_edited=False,
            histamine_score=1,
        ),
        # Invisible — must NOT appear in markdown and must NOT affect tags.
        PhotoIngredient(
            analysis_id=analysis.id,
            name="aged-pecorino-inferred",
            visible=False,
            confidence=0.4,
            user_edited=False,
            histamine_score=3,
            contains_dairy=True,
            fodmap_lactose="high",
        ),
        PhotoIngredient(
            analysis_id=analysis.id,
            name="garlic-inferred",
            visible=False,
            confidence=0.3,
            user_edited=False,
            fodmap_oligos="high",
        ),
    ]
    for ing in ingredients:
        db.add(ing)
    await db.commit()
    # Bind ingredients to the analysis collection so _render_markdown can iterate.
    analysis.ingredients = ingredients
    return entry, [photo], {photo.id: analysis}


def _render(
    entry: Entry,
    photos: list[Photo],
    analyses: dict[int, PhotoAnalysis],
) -> str:
    """Test wrapper supplying defaults for the optional context args."""
    return _render_markdown(
        entry=entry,
        photos=photos,
        analyses=analyses,
        active_sym_labels={},
        active_treatments=[],
        health=None,
        weather=None,
    )


async def test_render_markdown_excludes_invisible_from_inline_ingredients(
    async_db: AsyncSession,
) -> None:
    """The 'Ingredients: ...' line must list only visible items."""
    entry, photos, analyses = await _seed_entry_with_mixed_visibility(async_db)
    md = _render(entry, photos, analyses)

    ing_lines = [ln for ln in md.splitlines() if ln.startswith("Ingredients:")]
    assert len(ing_lines) == 1
    line = ing_lines[0]
    # Visible items present.
    assert "spaghetti" in line
    assert "egg" in line
    # Invisible items absent.
    assert "aged-pecorino-inferred" not in line
    assert "garlic-inferred" not in line


async def test_render_markdown_excludes_invisible_from_dietary_flags(
    async_db: AsyncSession,
) -> None:
    """Per-photo 'Dietary flags' line must ignore invisible items."""
    entry, photos, analyses = await _seed_entry_with_mixed_visibility(async_db)
    md = _render(entry, photos, analyses)

    flags_lines = [ln for ln in md.splitlines() if ln.startswith("Dietary flags:")]
    assert len(flags_lines) == 1
    flags = flags_lines[0]
    # Histamine 1 from the visible egg.
    assert "Histamine 1" in flags
    # The hidden pecorino had histamine 3, dairy, fodmap-lactose — none should appear.
    assert "Histamine 3" not in flags
    assert "Dairy" not in flags
    assert "FODMAP-Lactose" not in flags
    # The hidden garlic-inferred had fodmap-oligos high.
    assert "FODMAP-Oligos" not in flags
    # Gluten comes from the visible spaghetti and SHOULD appear.
    assert "Gluten" in flags


async def test_render_markdown_excludes_invisible_from_frontmatter_tags(
    async_db: AsyncSession,
) -> None:
    """Frontmatter aggregates must reflect only visible ingredients."""
    entry, photos, analyses = await _seed_entry_with_mixed_visibility(async_db)
    md = _render(entry, photos, analyses)

    # max-histamine is 1 (from visible egg), not 3 (from invisible pecorino).
    assert "max-histamine: 1" in md
    assert "max-histamine: 3" not in md
    # contains-gluten tag must appear (from visible spaghetti).
    assert "  - contains-gluten" in md
    # contains-dairy tag must NOT appear (only invisible pecorino had it).
    assert "  - contains-dairy" not in md
    # fodmap-high-lactose must NOT appear (only invisible pecorino).
    assert "fodmap-high-lactose" not in md
    # fodmap-high-oligos must NOT appear (only invisible garlic).
    assert "fodmap-high-oligos" not in md


async def test_render_markdown_keeps_photo_embed_and_dish_when_all_invisible(
    async_db: AsyncSession,
) -> None:
    """If every ingredient is invisible (rare edge case), the photo embed
    and dish header must still render — only the 'Ingredients:' line should
    be suppressed."""
    entry = Entry(
        date=datetime.date(2026, 5, 16),
        overall=2,
        bloating=0,
        stool_status="normal",
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        hot_shower=False,
    )
    async_db.add(entry)
    await async_db.commit()
    await async_db.refresh(entry)
    photo = Photo(
        entry_id=entry.id,
        filename="2026-05-16_photo-1.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    async_db.add(photo)
    await async_db.commit()
    await async_db.refresh(photo)
    analysis = PhotoAnalysis(
        photo_id=photo.id,
        status="confirmed",
        dish_name="mystery soup",
        dish_confidence=0.5,
        model_id="test-model",
    )
    async_db.add(analysis)
    await async_db.commit()
    await async_db.refresh(analysis)
    ing = PhotoIngredient(
        analysis_id=analysis.id,
        name="inferred-broth",
        visible=False,
        confidence=0.3,
        user_edited=False,
    )
    async_db.add(ing)
    await async_db.commit()
    analysis.ingredients = [ing]

    md = _render(entry, [photo], {photo.id: analysis})
    # Photo embed present.
    assert "![[attachments/2026-05-16_photo-1.jpg]]" in md
    # Dish header present.
    assert "**mystery soup**" in md
    # No 'Ingredients:' line because nothing visible to show.
    assert not any(ln.startswith("Ingredients:") for ln in md.splitlines())
