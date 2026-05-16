from __future__ import annotations

import datetime
from typing import Optional

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError, ValidationError
from app.models.treatment import Treatment
from app.schemas.treatment import TreatmentCreate, TreatmentUpdate
from app.services.treatments import TreatmentService


@pytest_asyncio.fixture
async def service(async_db: AsyncSession) -> TreatmentService:
    return TreatmentService(async_db)


@pytest.fixture(autouse=True)
def no_vault_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Suppress vault re-rendering so tests don't need a vault on disk."""

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.treatments.render_and_write_daily_file",
        _noop,
        raising=False,
    )


# ---------------------------------------------------------------------------
# _normalize_name (private helper on the service)
# ---------------------------------------------------------------------------


def test_normalize_lowercase() -> None:
    assert TreatmentService._normalize_name("Rifaximin") == "rifaximin"


def test_normalize_spaces_to_underscore() -> None:
    assert TreatmentService._normalize_name("Fish Oil") == "fish_oil"


def test_normalize_special_chars_stripped() -> None:
    # '+' is not in [a-z0-9_] so it is stripped; spaces → underscores first
    assert TreatmentService._normalize_name("D3 + K2") == "d3__k2"


def test_normalize_trims_whitespace() -> None:
    assert TreatmentService._normalize_name("  spaces  ") == "spaces"


def test_normalize_dashes_to_underscore() -> None:
    assert TreatmentService._normalize_name("dashes-here") == "dashes_here"


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


async def test_create_happy_path(service: TreatmentService) -> None:
    body = TreatmentCreate(
        name="Allicin",
        type="antimicrobial",
        start_date=datetime.date(2026, 1, 1),
    )
    result = await service.create(body)

    assert result.id is not None
    assert result.name == "Allicin"
    assert result.normalized_name == "allicin"
    assert result.type == "antimicrobial"
    assert result.start_date == datetime.date(2026, 1, 1)
    assert result.end_date is None
    assert result.created_at is not None
    assert result.updated_at is not None


async def test_create_end_date_before_start_raises_validation(
    service: TreatmentService,
) -> None:
    body = TreatmentCreate(
        name="Rifaximin",
        type="antibiotic",
        start_date=datetime.date(2026, 2, 10),
        end_date=datetime.date(2026, 2, 5),
    )
    with pytest.raises(ValidationError):
        await service.create(body)


async def test_create_duplicate_names_allowed(service: TreatmentService) -> None:
    """Treatments are not unique by name — two with the same name is valid."""
    body = TreatmentCreate(
        name="Allicin",
        type="antimicrobial",
        start_date=datetime.date(2026, 1, 1),
    )
    t1 = await service.create(body)
    t2 = await service.create(body)
    assert t1.id != t2.id


async def test_create_optional_fields_null(service: TreatmentService) -> None:
    body = TreatmentCreate(
        name="Berberine",
        type="other",
        start_date=datetime.date(2026, 3, 1),
        dose=None,
        notes=None,
        end_date=None,
    )
    result = await service.create(body)
    assert result.dose is None
    assert result.notes is None
    assert result.end_date is None


async def test_create_with_end_date_equal_to_start_date_ok(
    service: TreatmentService,
) -> None:
    body = TreatmentCreate(
        name="Oregano",
        type="antimicrobial",
        start_date=datetime.date(2026, 5, 1),
        end_date=datetime.date(2026, 5, 1),
    )
    result = await service.create(body)
    assert result.start_date == result.end_date


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


async def _add_treatment(
    db: AsyncSession,
    name: str,
    start_date: datetime.date,
    end_date: Optional[datetime.date] = None,
) -> Treatment:
    t = Treatment(
        name=name,
        normalized_name=TreatmentService._normalize_name(name),
        type="other",
        start_date=start_date,
        end_date=end_date,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def test_list_empty(service: TreatmentService) -> None:
    assert await service.list() == []


async def test_list_ongoing_first(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    """Ongoing treatments (end_date=None) sort before finished ones."""
    await _add_treatment(
        async_db, "Finished", datetime.date(2026, 1, 1), datetime.date(2026, 1, 31)
    )
    await _add_treatment(async_db, "Ongoing", datetime.date(2026, 2, 1))

    results = await service.list()
    assert results[0].name == "Ongoing"
    assert results[1].name == "Finished"


async def test_list_active_on_includes_ongoing(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    await _add_treatment(async_db, "Ongoing", datetime.date(2026, 1, 1))
    results = await service.list(active_on="2026-06-01")
    assert len(results) == 1
    assert results[0].name == "Ongoing"


async def test_list_active_on_boundary_end_date_included(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    """active_on == end_date should still be considered active (inclusive)."""
    await _add_treatment(
        async_db,
        "Short",
        datetime.date(2026, 5, 1),
        datetime.date(2026, 5, 15),
    )
    results = await service.list(active_on="2026-05-15")
    assert len(results) == 1


async def test_list_active_on_excludes_expired(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    await _add_treatment(
        async_db,
        "Expired",
        datetime.date(2026, 1, 1),
        datetime.date(2026, 1, 31),
    )
    results = await service.list(active_on="2026-02-01")
    assert results == []


async def test_list_active_on_excludes_not_yet_started(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    await _add_treatment(async_db, "Future", datetime.date(2026, 12, 1))
    results = await service.list(active_on="2026-05-15")
    assert results == []


async def test_list_active_on_mixed(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    await _add_treatment(
        async_db, "Active", datetime.date(2026, 1, 1), datetime.date(2026, 6, 30)
    )
    await _add_treatment(
        async_db, "Expired", datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)
    )
    await _add_treatment(async_db, "Ongoing", datetime.date(2026, 3, 1))

    results = await service.list(active_on="2026-05-15")
    names = {r.name for r in results}
    assert names == {"Active", "Ongoing"}


async def test_list_active_on_invalid_format_raises_validation(
    service: TreatmentService,
) -> None:
    with pytest.raises(ValidationError):
        await service.list(active_on="not-a-date")


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


async def test_get_existing(async_db: AsyncSession, service: TreatmentService) -> None:
    t = await _add_treatment(async_db, "Allicin", datetime.date(2026, 1, 1))
    result = await service.get(t.id)
    assert result.id == t.id
    assert result.name == "Allicin"


async def test_get_nonexistent_raises_not_found(service: TreatmentService) -> None:
    with pytest.raises(NotFoundError):
        await service.get(999)


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


async def test_update_partial_name_only(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    t = await _add_treatment(async_db, "Old Name", datetime.date(2026, 1, 1))
    body = TreatmentUpdate(name="New Name")
    result = await service.update(t.id, body)

    assert result.name == "New Name"
    assert result.normalized_name == "new_name"
    # Other fields unchanged
    assert result.start_date == datetime.date(2026, 1, 1)
    assert result.end_date is None


async def test_update_name_recomputes_normalized_name(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    t = await _add_treatment(async_db, "Fish Oil", datetime.date(2026, 1, 1))
    body = TreatmentUpdate(name="Cod Liver Oil")
    result = await service.update(t.id, body)
    assert result.normalized_name == "cod_liver_oil"


async def test_update_end_date_before_start_raises_validation(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    t = await _add_treatment(
        async_db,
        "Rifaximin",
        datetime.date(2026, 3, 1),
        datetime.date(2026, 3, 31),
    )
    body = TreatmentUpdate(end_date=datetime.date(2026, 2, 1))
    with pytest.raises(ValidationError):
        await service.update(t.id, body)


async def test_update_nonexistent_raises_not_found(service: TreatmentService) -> None:
    body = TreatmentUpdate(name="Whatever")
    with pytest.raises(NotFoundError):
        await service.update(999, body)


async def test_update_unset_fields_are_not_touched(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    """model_dump(exclude_unset=True) must leave unchanged fields alone."""
    t = await _add_treatment(async_db, "Allicin", datetime.date(2026, 1, 1))
    # Give it a dose first
    t.dose = "450 mg"
    await async_db.commit()

    body = TreatmentUpdate(notes="Updated note")
    result = await service.update(t.id, body)
    assert result.dose == "450 mg"
    assert result.notes == "Updated note"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_delete_returns_none(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    t = await _add_treatment(async_db, "Allicin", datetime.date(2026, 1, 1))
    assert await service.delete(t.id) is None


async def test_delete_nonexistent_raises_not_found(
    service: TreatmentService,
) -> None:
    with pytest.raises(NotFoundError):
        await service.delete(999)


async def test_delete_removes_from_db(
    async_db: AsyncSession, service: TreatmentService
) -> None:
    t = await _add_treatment(async_db, "Allicin", datetime.date(2026, 1, 1))
    tid = t.id
    await service.delete(tid)
    assert (
        await async_db.execute(select(Treatment).where(Treatment.id == tid))
    ).scalar_one_or_none() is None
