from __future__ import annotations

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.diet_flags import compute_effective_counts, compute_photo_signal

_DATE = datetime.date(2026, 1, 1)


# ---------------------------------------------------------------------------
# Local ORM helpers — not added to conftest
# ---------------------------------------------------------------------------


async def _make_entry(db: AsyncSession) -> Entry:
    entry = Entry(
        date=_DATE,
        schema_version=3,
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
        symptoms_json={},
    )
    db.add(entry)
    await db.flush()
    return entry


async def _make_photo(db: AsyncSession, entry: Entry) -> Photo:
    photo = Photo(
        entry_id=entry.id,
        filename="test.jpg",
    )
    db.add(photo)
    await db.flush()
    return photo


async def _make_analysis(
    db: AsyncSession, photo: Photo, status: str = "confirmed"
) -> PhotoAnalysis:
    analysis = PhotoAnalysis(
        photo_id=photo.id,
        status=status,
    )
    db.add(analysis)
    await db.flush()
    return analysis


async def _make_ingredient(
    db: AsyncSession,
    analysis: PhotoAnalysis,
    *,
    name: str = "test_ingredient",
    histamine_score: int | None = None,
    fodmap_oligos: str | None = None,
    fodmap_fructose: str | None = None,
    fodmap_polyols: str | None = None,
    fodmap_lactose: str | None = None,
    contains_gluten: bool | None = None,
    contains_dairy: bool | None = None,
) -> PhotoIngredient:
    ing = PhotoIngredient(
        analysis_id=analysis.id,
        name=name,
        confidence=0.9,
        histamine_score=histamine_score,
        fodmap_oligos=fodmap_oligos,
        fodmap_fructose=fodmap_fructose,
        fodmap_polyols=fodmap_polyols,
        fodmap_lactose=fodmap_lactose,
        contains_gluten=contains_gluten,
        contains_dairy=contains_dairy,
    )
    db.add(ing)
    await db.flush()
    return ing


async def _build(
    db: AsyncSession, status: str = "confirmed"
) -> tuple[PhotoAnalysis, int]:
    """Convenience: entry -> photo -> analysis. Returns (analysis, entry_id)."""
    entry = await _make_entry(db)
    photo = await _make_photo(db, entry)
    analysis = await _make_analysis(db, photo, status=status)
    return analysis, entry.id


async def _load_entry(db: AsyncSession, entry_id: int) -> Entry:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Entry)
        .options(
            selectinload(Entry.photos)
            .selectinload(Photo.analysis)
            .selectinload(PhotoAnalysis.ingredients)
        )
        .where(Entry.id == entry_id)
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# 1. Histamine threshold boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score, expect_flag",
    [
        (0, False),
        (1, False),
        (2, True),
        (3, True),
    ],
)
async def test_histamine_threshold_boundary(
    async_db: AsyncSession, score: int, expect_flag: bool
) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="ing", histamine_score=score)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert ("high-histamine" in signal.flags) == expect_flag


# ---------------------------------------------------------------------------
# 2. Histamine load is a sum
# ---------------------------------------------------------------------------


async def test_histamine_load_sum_with_flag(async_db: AsyncSession) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="a", histamine_score=3)
    await _make_ingredient(async_db, analysis, name="b", histamine_score=2)
    await _make_ingredient(async_db, analysis, name="c", histamine_score=2)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert signal.scores.histamine_load == 7
    assert "high-histamine" in signal.flags


async def test_histamine_load_sum_without_flag(async_db: AsyncSession) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="a", histamine_score=1)
    await _make_ingredient(async_db, analysis, name="b", histamine_score=1)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert signal.scores.histamine_load == 2
    assert "high-histamine" not in signal.flags


# ---------------------------------------------------------------------------
# 3. FODMAP subcategories trigger individually
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "col",
    ["fodmap_oligos", "fodmap_fructose", "fodmap_polyols", "fodmap_lactose"],
)
async def test_fodmap_high_subcategory_triggers_flag(
    async_db: AsyncSession, col: str
) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="ing", **{col: "high"})
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert "high-fodmap" in signal.flags


@pytest.mark.parametrize(
    "col",
    ["fodmap_oligos", "fodmap_fructose", "fodmap_polyols", "fodmap_lactose"],
)
async def test_fodmap_moderate_does_not_trigger_flag(
    async_db: AsyncSession, col: str
) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="ing", **{col: "moderate"})
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert "high-fodmap" not in signal.flags


@pytest.mark.parametrize(
    "col",
    ["fodmap_oligos", "fodmap_fructose", "fodmap_polyols", "fodmap_lactose"],
)
async def test_fodmap_none_does_not_trigger_flag(
    async_db: AsyncSession, col: str
) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="ing")
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert "high-fodmap" not in signal.flags


# ---------------------------------------------------------------------------
# 4. FODMAP count dedupes per ingredient
# ---------------------------------------------------------------------------


async def test_fodmap_count_dedupes_per_ingredient(async_db: AsyncSession) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(
        async_db,
        analysis,
        name="onion",
        fodmap_oligos="high",
        fodmap_polyols="high",
    )
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert signal.scores.fodmap_count == 1


# ---------------------------------------------------------------------------
# 5. Gluten and dairy flags
# ---------------------------------------------------------------------------


async def test_gluten_true_produces_flag_and_count(async_db: AsyncSession) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="bread", contains_gluten=True)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert "gluten" in signal.flags
    assert signal.scores.gluten_count == 1


async def test_gluten_false_produces_no_flag(async_db: AsyncSession) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="rice", contains_gluten=False)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert "gluten" not in signal.flags
    assert signal.scores.gluten_count == 0


async def test_gluten_none_produces_no_flag(async_db: AsyncSession) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="mystery", contains_gluten=None)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert "gluten" not in signal.flags


async def test_dairy_true_produces_flag_and_count(async_db: AsyncSession) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="milk", contains_dairy=True)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert "dairy" in signal.flags
    assert signal.scores.dairy_count == 1


async def test_dairy_false_produces_no_flag(async_db: AsyncSession) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="oat", contains_dairy=False)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert "dairy" not in signal.flags
    assert signal.scores.dairy_count == 0


async def test_dairy_none_produces_no_flag(async_db: AsyncSession) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="mystery", contains_dairy=None)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert "dairy" not in signal.flags


# ---------------------------------------------------------------------------
# 6. Unconfirmed ingredients are ignored
# ---------------------------------------------------------------------------


async def test_unconfirmed_analysis_is_ignored(async_db: AsyncSession) -> None:
    analysis, entry_id = await _build(async_db, status="complete")
    await _make_ingredient(
        async_db,
        analysis,
        name="aged cheese",
        histamine_score=3,
        fodmap_oligos="high",
        contains_gluten=True,
        contains_dairy=True,
    )
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    assert signal.flags == set()
    assert signal.scores.histamine_load == 0
    assert signal.scores.fodmap_count == 0
    assert signal.scores.gluten_count == 0
    assert signal.scores.dairy_count == 0


# ---------------------------------------------------------------------------
# 7. Empty entry
# ---------------------------------------------------------------------------


async def test_empty_entry_returns_zero_scores(async_db: AsyncSession) -> None:
    entry = await _make_entry(async_db)
    await async_db.commit()
    await async_db.refresh(entry)

    signal = compute_photo_signal(entry)

    assert signal.flags == set()
    assert signal.scores.histamine_load == 0
    assert signal.scores.fodmap_count == 0
    assert signal.scores.gluten_count == 0
    assert signal.scores.dairy_count == 0
    assert signal.sources == {}


# ---------------------------------------------------------------------------
# 8. Sources deduplicate by name
# ---------------------------------------------------------------------------


async def test_sources_deduplicate_same_ingredient_name(
    async_db: AsyncSession,
) -> None:
    analysis, entry_id = await _build(async_db)
    # Two separate PhotoIngredient rows both named "bread" with gluten
    await _make_ingredient(async_db, analysis, name="bread", contains_gluten=True)
    await _make_ingredient(async_db, analysis, name="bread", contains_gluten=True)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    signal = compute_photo_signal(entry)

    # gluten_count counts rows (2), but sources deduplicates names
    assert signal.scores.gluten_count == 2
    assert signal.sources["gluten"] == ["bread"]


# ---------------------------------------------------------------------------
# 9. compute_effective_counts merges correctly
# ---------------------------------------------------------------------------


async def test_effective_counts_user_adds_gluten_not_in_photos(
    async_db: AsyncSession,
) -> None:
    entry = await _make_entry(async_db)
    await async_db.commit()
    await async_db.refresh(entry)

    counts = compute_effective_counts(compute_photo_signal(entry), ["gluten"])

    assert counts["gluten_count"] == 1


async def test_effective_counts_no_double_count_when_photos_and_user_agree(
    async_db: AsyncSession,
) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="bread", contains_gluten=True)
    await _make_ingredient(async_db, analysis, name="pasta", contains_gluten=True)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    counts = compute_effective_counts(compute_photo_signal(entry), ["gluten"])

    # Photos already found gluten (count=2); user also asserts gluten — no extra bump
    assert counts["gluten_count"] == 2


async def test_effective_counts_manual_histamine_does_not_bump_load(
    async_db: AsyncSession,
) -> None:
    analysis, entry_id = await _build(async_db)
    await _make_ingredient(async_db, analysis, name="spinach", histamine_score=3)
    await _make_ingredient(async_db, analysis, name="tomato", histamine_score=2)
    await _make_ingredient(async_db, analysis, name="avocado", histamine_score=2)
    await async_db.commit()

    entry = await _load_entry(async_db, entry_id)
    counts = compute_effective_counts(compute_photo_signal(entry), ["high-histamine"])

    assert counts["histamine_load"] == 7
