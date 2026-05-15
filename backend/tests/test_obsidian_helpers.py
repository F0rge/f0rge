"""Tests for the Obsidian vault renderer.

Regression coverage for issue #13: the vision model emits ingredients with
`visible=true` (seen in the photo) and `visible=false` (inferred from
common recipes). The UI filters to visible=true; the vault must do the
same so it reflects exactly what the user reviewed and confirmed on
screen.
"""

from __future__ import annotations

import datetime
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
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


# --- end-to-end via _render_markdown -----------------------------------


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_entry_with_mixed_visibility(db: Session) -> tuple[Entry, list[Photo]]:
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
    db.commit()

    photo = Photo(
        entry_id=entry.id,
        filename="2026-05-15_photo-1.jpg",
        original_filename="lunch.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    db.commit()

    analysis = PhotoAnalysis(
        photo_id=photo.id,
        status="confirmed",
        dish_name="pasta carbonara",
        dish_confidence=0.92,
        model_id="google/gemini-3-flash-preview",
    )
    db.add(analysis)
    db.commit()

    db.add_all(
        [
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
    )
    db.commit()
    return entry, [photo]


def test_render_markdown_excludes_invisible_from_inline_ingredients(
    db: Session,
) -> None:
    """The 'Ingredients: ...' line must list only visible items."""
    entry, photos = _seed_entry_with_mixed_visibility(db)
    md = _render_markdown(db, entry, photos)

    ing_lines = [ln for ln in md.splitlines() if ln.startswith("Ingredients:")]
    assert len(ing_lines) == 1
    line = ing_lines[0]
    # Visible items present.
    assert "spaghetti" in line
    assert "egg" in line
    # Invisible items absent.
    assert "aged-pecorino-inferred" not in line
    assert "garlic-inferred" not in line


def test_render_markdown_excludes_invisible_from_dietary_flags(
    db: Session,
) -> None:
    """Per-photo 'Dietary flags' line must ignore invisible items."""
    entry, photos = _seed_entry_with_mixed_visibility(db)
    md = _render_markdown(db, entry, photos)

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


def test_render_markdown_excludes_invisible_from_frontmatter_tags(
    db: Session,
) -> None:
    """Frontmatter aggregates must reflect only visible ingredients."""
    entry, photos = _seed_entry_with_mixed_visibility(db)
    md = _render_markdown(db, entry, photos)

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


def test_render_markdown_keeps_photo_embed_and_dish_when_all_invisible(
    db: Session,
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
    db.add(entry)
    db.commit()
    photo = Photo(
        entry_id=entry.id,
        filename="2026-05-16_photo-1.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    db.commit()
    analysis = PhotoAnalysis(
        photo_id=photo.id,
        status="confirmed",
        dish_name="mystery soup",
        dish_confidence=0.5,
        model_id="test-model",
    )
    db.add(analysis)
    db.commit()
    db.add(
        PhotoIngredient(
            analysis_id=analysis.id,
            name="inferred-broth",
            visible=False,
            confidence=0.3,
            user_edited=False,
        )
    )
    db.commit()

    md = _render_markdown(db, entry, [photo])
    # Photo embed present.
    assert "![[attachments/2026-05-16_photo-1.jpg]]" in md
    # Dish header present.
    assert "**mystery soup**" in md
    # No 'Ingredients:' line because nothing visible to show.
    assert not any(ln.startswith("Ingredients:") for ln in md.splitlines())
