from __future__ import annotations

import datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.models.lab_marker_alias import LabMarkerAlias
from app.models.lab_marker_catalog import LabMarkerCatalog
from app.schemas.lab_marker import LabMarkerCatalogCreate
from app.services.lab_catalog import LabMarkerCatalogService


@pytest_asyncio.fixture
async def service(async_db: AsyncSession) -> LabMarkerCatalogService:
    return LabMarkerCatalogService(async_db)


async def _seed_catalog(
    db: AsyncSession,
    canonical: str,
    display: str = "X",
    aliases: list[str] | None = None,
) -> LabMarkerCatalog:
    item = LabMarkerCatalog(
        canonical_name=canonical,
        display_name=display,
        common_units=[],
    )
    db.add(item)
    await db.flush()
    for a in aliases or []:
        db.add(LabMarkerAlias(catalog_id=item.id, alias=a.lower(), language=None))
    await db.commit()
    await db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# resolve_or_create — lookup chain
# ---------------------------------------------------------------------------


async def test_resolve_or_create_exact_canonical_hit(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    existing = await _seed_catalog(async_db, "hemoglobin", "Hemoglobin")
    result = await service.resolve_or_create("hemoglobin", "Hemoglobin")
    assert result.id == existing.id
    # No new alias should be created — input matches canonical exactly.
    assert (
        await async_db.execute(select(func.count()).select_from(LabMarkerAlias))
    ).scalar_one() == 0


async def test_resolve_or_create_alias_hit_case_insensitive(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    existing = await _seed_catalog(
        async_db, "hemoglobin", "Hemoglobin", aliases=["hemoglobina", "hb"]
    )
    # Input is upper-case alias.
    result = await service.resolve_or_create("HEMOGLOBINA", "Hemoglobina")
    assert result.id == existing.id
    # Should not create a new catalog item.
    assert (
        await async_db.execute(select(func.count()).select_from(LabMarkerCatalog))
    ).scalar_one() == 1


async def test_resolve_or_create_ilike_canonical_hit(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    """If exact lookup misses but ilike matches, return the existing item."""
    existing = await _seed_catalog(async_db, "hemoglobin", "Hemoglobin")
    # Different casing — normalized form equals canonical, so ilike fires.
    result = await service.resolve_or_create("Hemoglobin", "Hemoglobin")
    assert result.id == existing.id


async def test_resolve_or_create_creates_new_when_no_match(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    result = await service.resolve_or_create("brand_new_marker", "Brand New Marker")
    assert result.id is not None
    assert result.canonical_name == "brand_new_marker"
    assert result.display_name == "Brand New Marker"
    # When input == canonical, no alias is created.
    assert (
        await async_db.execute(select(func.count()).select_from(LabMarkerAlias))
    ).scalar_one() == 0


async def test_resolve_or_create_registers_alias_when_input_differs(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    """If we have to create a new entry AND input differs from canonical,
    register the input as an alias."""
    result = await service.resolve_or_create("Vitamin D-25 OH", "Vitamin D")
    assert result.canonical_name == "vitamin_d_25_oh"

    aliases = (
        (
            await async_db.execute(
                select(LabMarkerAlias).where(LabMarkerAlias.catalog_id == result.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(aliases) == 1
    assert aliases[0].alias == "vitamin d-25 oh"


# ---------------------------------------------------------------------------
# add_alias
# ---------------------------------------------------------------------------


async def test_add_alias_happy_path(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    item = await _seed_catalog(async_db, "hemoglobin", "Hemoglobin")
    alias = await service.add_alias(item.id, "Hb", language="en")
    await async_db.commit()
    assert alias.alias == "hb"  # stored lowercased
    assert alias.language == "en"


async def test_add_alias_conflict_on_duplicate(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    item = await _seed_catalog(async_db, "hemoglobin", "Hemoglobin", aliases=["hb"])
    with pytest.raises(ConflictError):
        await service.add_alias(item.id, "HB", language=None)


async def test_add_alias_not_found(service: LabMarkerCatalogService) -> None:
    with pytest.raises(NotFoundError):
        await service.add_alias(99999, "anything", language=None)


# ---------------------------------------------------------------------------
# create_catalog_item
# ---------------------------------------------------------------------------


async def test_create_catalog_item_normalizes_canonical(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    body = LabMarkerCatalogCreate(
        canonical_name="Vitamin D",
        display_name="Vitamin D",
        common_units=["ng/mL"],
    )
    item = await service.create_catalog_item(body)
    await async_db.commit()
    assert item.canonical_name == "vitamin_d"


async def test_create_catalog_item_conflict_on_duplicate_canonical(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    await _seed_catalog(async_db, "hemoglobin", "Hemoglobin")
    body = LabMarkerCatalogCreate(canonical_name="Hemoglobin", display_name="Hb")
    with pytest.raises(ConflictError):
        await service.create_catalog_item(body)


# ---------------------------------------------------------------------------
# get_marker_history — order + skip null-value rows
# ---------------------------------------------------------------------------


async def _add_lab_with_marker(
    db: AsyncSession,
    catalog_id: int,
    *,
    lab_date: datetime.date,
    canonical: str,
    value: float | None,
) -> None:
    lab = Lab(
        lab_date=lab_date,
        name=f"Lab {lab_date}",
        type="blood",
        source_kind="text",
    )
    db.add(lab)
    await db.flush()
    marker = LabMarker(
        lab_id=lab.id,
        catalog_id=catalog_id,
        canonical_name=canonical,
        display_name=canonical,
        value=value,
        flag="normal" if value is not None else "unknown",
    )
    db.add(marker)
    await db.commit()


async def test_get_marker_history_ascending_date(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    catalog = await _seed_catalog(async_db, "hemoglobin", "Hemoglobin")
    await _add_lab_with_marker(
        async_db,
        catalog.id,
        lab_date=datetime.date(2026, 3, 1),
        canonical="hemoglobin",
        value=15.0,
    )
    await _add_lab_with_marker(
        async_db,
        catalog.id,
        lab_date=datetime.date(2026, 1, 1),
        canonical="hemoglobin",
        value=14.0,
    )
    await _add_lab_with_marker(
        async_db,
        catalog.id,
        lab_date=datetime.date(2026, 5, 1),
        canonical="hemoglobin",
        value=13.0,
    )

    history = await service.get_marker_history("hemoglobin")
    assert [p.lab_date for p in history] == [
        datetime.date(2026, 1, 1),
        datetime.date(2026, 3, 1),
        datetime.date(2026, 5, 1),
    ]
    assert [p.value for p in history] == [14.0, 15.0, 13.0]


async def test_get_marker_history_skips_null_values(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    catalog = await _seed_catalog(async_db, "hemoglobin", "Hemoglobin")
    await _add_lab_with_marker(
        async_db,
        catalog.id,
        lab_date=datetime.date(2026, 1, 1),
        canonical="hemoglobin",
        value=14.0,
    )
    await _add_lab_with_marker(
        async_db,
        catalog.id,
        lab_date=datetime.date(2026, 2, 1),
        canonical="hemoglobin",
        value=None,
    )
    await _add_lab_with_marker(
        async_db,
        catalog.id,
        lab_date=datetime.date(2026, 3, 1),
        canonical="hemoglobin",
        value=15.0,
    )

    history = await service.get_marker_history("hemoglobin")
    assert len(history) == 2
    assert [p.value for p in history] == [14.0, 15.0]


async def test_get_marker_history_unknown_canonical_returns_empty(
    service: LabMarkerCatalogService,
) -> None:
    assert await service.get_marker_history("nonexistent") == []


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


async def test_search_no_query_returns_all(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    await _seed_catalog(async_db, "hemoglobin", "Hemoglobin")
    await _seed_catalog(async_db, "ferritin", "Ferritin")
    assert len(await service.search(None)) == 2


async def test_search_by_canonical(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    await _seed_catalog(async_db, "hemoglobin", "Hemoglobin")
    await _seed_catalog(async_db, "ferritin", "Ferritin")
    results = await service.search("hemo")
    assert len(results) == 1
    assert results[0].canonical_name == "hemoglobin"


async def test_search_by_alias(
    async_db: AsyncSession, service: LabMarkerCatalogService
) -> None:
    await _seed_catalog(async_db, "hemoglobin", "Hemoglobin", aliases=["hemoglobina"])
    await _seed_catalog(async_db, "ferritin", "Ferritin")
    results = await service.search("hemoglobina")
    assert len(results) == 1
    assert results[0].canonical_name == "hemoglobin"
