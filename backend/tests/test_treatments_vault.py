from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.treatment import Treatment
from app.services.obsidian import _format_active_treatments, _render_markdown


async def _make_treatment(
    db: AsyncSession,
    name: str,
    normalized_name: str,
    start_date: datetime.date,
    end_date: Optional[datetime.date] = None,
) -> Treatment:
    t = Treatment(
        name=name,
        normalized_name=normalized_name,
        type="antimicrobial",
        start_date=start_date,
        end_date=end_date,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def _make_entry(db: AsyncSession, date: datetime.date) -> Entry:
    entry = Entry(
        date=date,
        schema_version=2,
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
    return entry


async def _active_treatments(db: AsyncSession, as_of: datetime.date) -> list[Treatment]:
    """Mirror app.services.obsidian_prefetch active-treatment selection so the
    render-layer tests get the same input the production caller assembles."""
    rows = (
        (
            await db.execute(
                select(Treatment)
                .where(Treatment.start_date <= as_of)
                .where(
                    (Treatment.end_date.is_(None)) | (Treatment.end_date >= as_of)
                )
                .order_by(Treatment.name.asc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


def _render(entry: Entry, active_treatments: list[Treatment]) -> str:
    return _render_markdown(
        entry=entry,
        photos=[],
        analyses={},
        active_sym_labels={},
        active_treatments=active_treatments,
        health=None,
        weather=None,
    )


# ---------------------------------------------------------------------------
# _format_active_treatments
# ---------------------------------------------------------------------------


def test_format_empty_list() -> None:
    assert _format_active_treatments([], datetime.date(2026, 5, 15)) == "None"


def test_format_single_treatment_day_1() -> None:
    t = Treatment(
        name="Allicin",
        normalized_name="allicin",
        type="antimicrobial",
        start_date=datetime.date(2026, 5, 15),
    )
    result = _format_active_treatments([t], datetime.date(2026, 5, 15))
    assert result == "Allicin (day 1)"


def test_format_day_count_start_is_day_1() -> None:
    """Day count: (as_of - start_date).days + 1 — start day is day 1 not day 0."""
    t = Treatment(
        name="Rifaximin",
        normalized_name="rifaximin",
        type="antibiotic",
        start_date=datetime.date(2026, 5, 1),
    )
    # 14 days later → day 15
    as_of = datetime.date(2026, 5, 15)
    result = _format_active_treatments([t], as_of)
    assert result == "Rifaximin (day 15)"


def test_format_multiple_treatments() -> None:
    allicin = Treatment(
        name="Allicin",
        normalized_name="allicin",
        type="antimicrobial",
        start_date=datetime.date(2026, 5, 8),
    )
    rifaximin = Treatment(
        name="Rifaximin",
        normalized_name="rifaximin",
        type="antibiotic",
        start_date=datetime.date(2026, 5, 13),
    )
    as_of = datetime.date(2026, 5, 15)
    result = _format_active_treatments([allicin, rifaximin], as_of)
    # allicin: day 8, rifaximin: day 3
    assert result == "Allicin (day 8), Rifaximin (day 3)"


# ---------------------------------------------------------------------------
# _render_markdown — frontmatter and table
# ---------------------------------------------------------------------------


async def test_render_markdown_with_active_treatment(
    async_db: AsyncSession,
) -> None:
    """active-treatments frontmatter and summary table row are written correctly."""
    entry_date = datetime.date(2026, 5, 15)
    entry = await _make_entry(async_db, entry_date)
    await _make_treatment(
        async_db, "Allicin", "allicin", datetime.date(2026, 5, 8)
    )

    content = _render(entry, await _active_treatments(async_db, entry_date))

    # Frontmatter: normalized_name appears in the list
    assert "active-treatments: [allicin]" in content
    # Summary table row
    assert "| Active treatments | Allicin (day 8) |" in content


async def test_render_markdown_no_active_treatment(
    async_db: AsyncSession,
) -> None:
    """With no treatments, frontmatter list is empty and table row shows None."""
    entry_date = datetime.date(2026, 5, 15)
    entry = await _make_entry(async_db, entry_date)

    content = _render(entry, await _active_treatments(async_db, entry_date))

    assert "active-treatments: []" in content
    assert "| Active treatments | None |" in content


async def test_render_markdown_multiple_treatments(
    async_db: AsyncSession,
) -> None:
    """Multiple active treatments all appear in frontmatter and table."""
    entry_date = datetime.date(2026, 5, 15)
    entry = await _make_entry(async_db, entry_date)
    # Both are active on entry_date
    await _make_treatment(
        async_db, "Allicin", "allicin", datetime.date(2026, 5, 8)
    )
    await _make_treatment(
        async_db, "Rifaximin", "rifaximin", datetime.date(2026, 5, 13)
    )

    content = _render(entry, await _active_treatments(async_db, entry_date))

    # The obsidian service orders by Treatment.name
    assert "active-treatments: [allicin, rifaximin]" in content
    assert "Allicin (day 8)" in content
    assert "Rifaximin (day 3)" in content


async def test_render_markdown_expired_treatment_excluded(
    async_db: AsyncSession,
) -> None:
    """Treatment that ended before the entry date must not appear."""
    entry_date = datetime.date(2026, 5, 15)
    entry = await _make_entry(async_db, entry_date)
    # Ended on May 14 — one day before entry
    await _make_treatment(
        async_db,
        "OldDrug",
        "olddrug",
        datetime.date(2026, 5, 1),
        datetime.date(2026, 5, 14),
    )

    content = _render(entry, await _active_treatments(async_db, entry_date))

    assert "active-treatments: []" in content
    assert "OldDrug" not in content


async def test_render_markdown_treatment_active_on_last_day(
    async_db: AsyncSession,
) -> None:
    """Treatment ending on the exact entry date is still active (inclusive)."""
    entry_date = datetime.date(2026, 5, 15)
    entry = await _make_entry(async_db, entry_date)
    await _make_treatment(
        async_db,
        "Berberine",
        "berberine",
        datetime.date(2026, 5, 1),
        datetime.date(2026, 5, 15),  # ends today — still active
    )

    content = _render(entry, await _active_treatments(async_db, entry_date))

    assert "active-treatments: [berberine]" in content
    assert "Berberine (day 15)" in content
