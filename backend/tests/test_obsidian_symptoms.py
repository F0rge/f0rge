from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.symptom_catalog import SymptomCatalogItem
from app.services.obsidian import _render_markdown


async def _make_entry(
    db: AsyncSession, symptoms_json: dict | None = None
) -> Entry:
    entry = Entry(
        date=datetime.date(2026, 5, 15),
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
        symptoms_json=symptoms_json if symptoms_json is not None else {},
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def _add_catalog_item(
    db: AsyncSession, key: str, label: str, archived: bool = False
) -> SymptomCatalogItem:
    item = SymptomCatalogItem(
        key=key,
        label=label,
        archived=archived,
        sort_order=0,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def _active_labels(db: AsyncSession) -> dict[str, str]:
    rows = (
        (
            await db.execute(
                select(SymptomCatalogItem).where(
                    SymptomCatalogItem.archived.is_(False)
                )
            )
        )
        .scalars()
        .all()
    )
    return {r.key: r.label for r in rows}


def _render(
    entry: Entry, active_labels: dict[str, str]
) -> str:
    return _render_markdown(
        entry=entry,
        photos=[],
        analyses={},
        active_sym_labels=active_labels,
        active_treatments=[],
        health=None,
        weather=None,
    )


# ---------------------------------------------------------------------------
# Empty symptoms
# ---------------------------------------------------------------------------


async def test_empty_symptoms_frontmatter(async_db: AsyncSession) -> None:
    entry = await _make_entry(async_db, {})
    md = _render(entry, await _active_labels(async_db))
    assert "symptoms-count: 0" in md
    # No sym-* lines should appear
    assert "sym-" not in md


async def test_empty_symptoms_summary_row(async_db: AsyncSession) -> None:
    entry = await _make_entry(async_db, {})
    md = _render(entry, await _active_labels(async_db))
    assert "| Symptoms | None today |" in md


# ---------------------------------------------------------------------------
# Active symptoms render correctly
# ---------------------------------------------------------------------------


async def test_active_symptoms_frontmatter(async_db: AsyncSession) -> None:
    await _add_catalog_item(async_db, "tinnitus", "Tinnitus")
    await _add_catalog_item(async_db, "vss", "Visual Snow")
    entry = await _make_entry(async_db, {"vss": 7, "tinnitus": 6})
    md = _render(entry, await _active_labels(async_db))

    assert "sym-tinnitus: 6" in md
    assert "sym-vss: 7" in md
    assert "symptoms-count: 2" in md


async def test_active_symptoms_sorted_in_frontmatter(async_db: AsyncSession) -> None:
    """sym-* lines appear in alphabetical key order."""
    await _add_catalog_item(async_db, "tinnitus", "Tinnitus")
    await _add_catalog_item(async_db, "vss", "Visual Snow")
    entry = await _make_entry(async_db, {"vss": 7, "tinnitus": 6})
    md = _render(entry, await _active_labels(async_db))

    tinnitus_pos = md.index("sym-tinnitus:")
    vss_pos = md.index("sym-vss:")
    assert tinnitus_pos < vss_pos


async def test_active_symptoms_summary_row(async_db: AsyncSession) -> None:
    await _add_catalog_item(async_db, "tinnitus", "Tinnitus")
    await _add_catalog_item(async_db, "vss", "Visual Snow")
    entry = await _make_entry(async_db, {"vss": 7, "tinnitus": 6})
    md = _render(entry, await _active_labels(async_db))

    # Both labels must appear in the summary row
    assert "Tinnitus 6/10" in md
    assert "Visual Snow 7/10" in md


# ---------------------------------------------------------------------------
# Archived symptoms are excluded
# ---------------------------------------------------------------------------


async def test_archived_symptom_excluded_from_frontmatter(
    async_db: AsyncSession,
) -> None:
    await _add_catalog_item(async_db, "vss", "Visual Snow", archived=True)
    entry = await _make_entry(async_db, {"vss": 7})
    md = _render(entry, await _active_labels(async_db))

    assert "sym-vss" not in md
    assert "symptoms-count: 0" in md


async def test_archived_symptom_summary_says_none_today(
    async_db: AsyncSession,
) -> None:
    await _add_catalog_item(async_db, "vss", "Visual Snow", archived=True)
    entry = await _make_entry(async_db, {"vss": 7})
    md = _render(entry, await _active_labels(async_db))
    assert "| Symptoms | None today |" in md
