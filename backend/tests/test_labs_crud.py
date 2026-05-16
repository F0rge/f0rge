from __future__ import annotations

import datetime
from typing import Optional

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.models.lab_marker_catalog import LabMarkerCatalog
from app.schemas.lab import LabCreate, LabMarkerCreate, LabUpdate
from app.services.labs import LabsService


@pytest_asyncio.fixture
async def service(async_db: AsyncSession) -> LabsService:
    return LabsService(async_db)


async def _make_catalog(
    db: AsyncSession, canonical: str = "hemoglobin"
) -> LabMarkerCatalog:
    item = LabMarkerCatalog(
        canonical_name=canonical,
        display_name=canonical.replace("_", " ").title(),
        common_units=["g/dL"],
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


def _marker_create(
    catalog_id: int,
    canonical: str = "hemoglobin",
    *,
    display_name: Optional[str] = None,
    value: Optional[float] = 15.5,
    value_text: Optional[str] = None,
    unit: Optional[str] = "g/dL",
    ref_low: Optional[float] = 13.7,
    ref_high: Optional[float] = 17.2,
    ref_text: Optional[str] = None,
) -> LabMarkerCreate:
    return LabMarkerCreate(
        catalog_id=catalog_id,
        canonical_name=canonical,
        display_name=display_name or canonical.title(),
        value=value,
        value_text=value_text,
        unit=unit,
        ref_low=ref_low,
        ref_high=ref_high,
        ref_text=ref_text,
    )


# ---------------------------------------------------------------------------
# compute_flag — full parameter matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "value_text", "ref_low", "ref_high", "ref_text", "expected"),
    [
        # value is None
        (None, None, 13.7, 17.2, None, "unknown"),
        (None, "Negative", None, None, "Negative", "unknown"),
        # both refs present
        (10.0, None, 13.7, 17.2, None, "low"),
        (15.0, None, 13.7, 17.2, None, "normal"),
        (20.0, None, 13.7, 17.2, None, "high"),
        (13.7, None, 13.7, 17.2, None, "normal"),  # equals lower bound
        (17.2, None, 13.7, 17.2, None, "normal"),  # equals upper bound
        # only ref_high present
        (200.0, None, None, 190.0, None, "high"),
        (180.0, None, None, 190.0, None, "normal"),
        # only ref_low present
        (30.0, None, 40.0, None, None, "low"),
        (50.0, None, 40.0, None, None, "normal"),
        # no refs at all, only numeric value
        (1.0, None, None, None, None, "unknown"),
        # no refs, no value, but value_text + abnormal-like ref_text
        (None, "POSITIVE", None, None, "Negative", "abnormal"),
        (None, "REACTIVE", None, None, None, "unknown"),  # ref_text is None
    ],
)
def test_compute_flag_matrix(
    value: Optional[float],
    value_text: Optional[str],
    ref_low: Optional[float],
    ref_high: Optional[float],
    ref_text: Optional[str],
    expected: str,
) -> None:
    flag = LabsService.compute_flag(
        value=value,
        value_text=value_text,
        ref_low=ref_low,
        ref_high=ref_high,
        ref_text=ref_text,
    )
    assert flag == expected


def test_compute_flag_abnormal_ref_text_with_matching_value_text() -> None:
    # ref_text is itself "abnormal-like" — the regex matches the ref_text branch
    flag = LabsService.compute_flag(
        value=None,
        value_text="REACTIVE",
        ref_low=None,
        ref_high=None,
        ref_text="Class >= 4",
    )
    assert flag == "abnormal"


# ---------------------------------------------------------------------------
# Unidirectional ref_text parsing — labs often report ranges as "<5.18", ">60"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "ref_text", "expected"),
    [
        # "<X" — value above X is high, below is normal
        (4.5, "<5.18", "normal"),
        (5.18, "<5.18", "normal"),
        (6.0, "<5.18", "high"),
        # "<= X" with spaces and comma decimal separator
        (28.9, "<= 29,0", "normal"),
        (29.5, "<=29,0", "high"),
        # ">X" — value below X is low, above is normal
        (75.0, ">60", "normal"),
        (60.0, ">60", "normal"),  # equals threshold
        (45.0, ">60", "low"),
        # ">=X"
        (0.30, ">=0.27", "normal"),
        (0.20, ">=0.27", "low"),
        # Unicode comparison operators (Gemini sometimes emits these)
        (5.0, "≤4.1", "high"),
        (10.0, "≥8.0", "normal"),
        # Non-parseable ref_text — falls through to "unknown"
        (50.0, "Negative", "unknown"),
        (50.0, "Normal", "unknown"),
        (50.0, "see method", "unknown"),
    ],
)
def test_compute_flag_parses_unidirectional_ref_text(
    value: float, ref_text: str, expected: str
) -> None:
    """The LLM frequently emits ref_low/ref_high as null and stuffs the bound
    into ref_text when the source uses inequality notation. compute_flag must
    extract the numeric bound rather than collapse to 'unknown'."""
    flag = LabsService.compute_flag(
        value=value,
        value_text=None,
        ref_low=None,
        ref_high=None,
        ref_text=ref_text,
    )
    assert flag == expected, (
        f"value={value} ref_text={ref_text!r} → {flag}, expected {expected}"
    )


def test_compute_flag_numeric_refs_take_precedence_over_ref_text() -> None:
    flag = LabsService.compute_flag(
        value=15.0,
        value_text=None,
        ref_low=10.0,
        ref_high=20.0,
        ref_text="<5.0",  # contradictory; numeric wins
    )
    assert flag == "normal"


# ---------------------------------------------------------------------------
# create_lab
# ---------------------------------------------------------------------------


async def test_create_lab_happy_path(
    async_db: AsyncSession, service: LabsService
) -> None:
    catalog = await _make_catalog(async_db)
    body = LabCreate(
        lab_date=datetime.date(2026, 5, 1),
        name="Test Blood Panel",
        type="blood",
        markers=[
            _marker_create(catalog.id, value=15.5),
            _marker_create(
                catalog.id,
                canonical="hemoglobin",
                display_name="Hb",
                value=10.0,
            ),
        ],
    )
    lab = await service.create_lab(body)

    assert lab.id is not None
    assert lab.name == "Test Blood Panel"
    assert lab.type == "blood"
    assert lab.lab_date == datetime.date(2026, 5, 1)
    assert lab.review_status == "confirmed"  # default
    assert len(lab.markers) == 2
    # Flags computed for each marker
    flags = sorted(m.flag for m in lab.markers)
    assert flags == ["low", "normal"]


async def test_create_lab_with_extraction_meta_sets_review_status(
    async_db: AsyncSession, service: LabsService
) -> None:
    catalog = await _make_catalog(async_db)
    body = LabCreate(
        lab_date=datetime.date(2026, 5, 1),
        name="Auto-Extracted Lab",
        type="blood",
        markers=[_marker_create(catalog.id)],
    )
    lab = await service.create_lab(
        body,
        extraction_meta={
            "extraction_model": "google/gemini-3-flash-preview",
            "extraction_confidence": 0.85,
            "review_status": "needs_review",
            "source_kind": "pdf",
            "attachment_path": "/tmp/test.pdf",
        },
    )
    assert lab.extraction_model == "google/gemini-3-flash-preview"
    assert lab.extraction_confidence == 0.85
    assert lab.review_status == "needs_review"
    assert lab.source_kind == "pdf"
    assert lab.attachment_path == "/tmp/test.pdf"


# ---------------------------------------------------------------------------
# list_labs — filters
# ---------------------------------------------------------------------------


async def _seed_labs(db: AsyncSession, service: LabsService) -> None:
    catalog = await _make_catalog(db)
    for date_, type_, name in [
        (datetime.date(2026, 1, 1), "blood", "Lab A"),
        (datetime.date(2026, 3, 15), "blood", "Lab B"),
        (datetime.date(2026, 5, 30), "imaging", "Lab C"),
        (datetime.date(2026, 6, 30), "breath", "Lab D"),
    ]:
        await service.create_lab(
            LabCreate(
                lab_date=date_,
                name=name,
                type=type_,
                markers=[_marker_create(catalog.id)],
            )
        )


async def test_list_labs_no_filters_returns_all_desc(
    async_db: AsyncSession, service: LabsService
) -> None:
    await _seed_labs(async_db, service)
    labs = await service.list_labs()
    # Newest first
    assert [lab.name for lab in labs] == ["Lab D", "Lab C", "Lab B", "Lab A"]


async def test_list_labs_date_range(
    async_db: AsyncSession, service: LabsService
) -> None:
    await _seed_labs(async_db, service)
    labs = await service.list_labs(
        start_date=datetime.date(2026, 2, 1),
        end_date=datetime.date(2026, 6, 1),
    )
    assert {lab.name for lab in labs} == {"Lab B", "Lab C"}


async def test_list_labs_filter_by_type(
    async_db: AsyncSession, service: LabsService
) -> None:
    await _seed_labs(async_db, service)
    labs = await service.list_labs(lab_type="blood")
    assert {lab.name for lab in labs} == {"Lab A", "Lab B"}


async def test_list_labs_filter_by_type_and_date(
    async_db: AsyncSession, service: LabsService
) -> None:
    await _seed_labs(async_db, service)
    labs = await service.list_labs(
        start_date=datetime.date(2026, 3, 1),
        lab_type="blood",
    )
    assert [lab.name for lab in labs] == ["Lab B"]


async def test_list_labs_empty(service: LabsService) -> None:
    assert await service.list_labs() == []


# ---------------------------------------------------------------------------
# get_lab
# ---------------------------------------------------------------------------


async def test_get_lab_existing(
    async_db: AsyncSession, service: LabsService
) -> None:
    catalog = await _make_catalog(async_db)
    body = LabCreate(
        lab_date=datetime.date(2026, 5, 1),
        name="Specific Lab",
        type="blood",
        markers=[_marker_create(catalog.id)],
    )
    created = await service.create_lab(body)
    fetched = await service.get_lab(created.id)
    assert fetched.id == created.id
    assert fetched.name == "Specific Lab"


async def test_get_lab_nonexistent_raises_not_found(service: LabsService) -> None:
    with pytest.raises(NotFoundError):
        await service.get_lab(99999)


# ---------------------------------------------------------------------------
# update_lab — wholesale marker replacement
# ---------------------------------------------------------------------------


async def test_update_lab_replaces_markers_wholesale(
    async_db: AsyncSession, service: LabsService
) -> None:
    catalog = await _make_catalog(async_db)
    body = LabCreate(
        lab_date=datetime.date(2026, 5, 1),
        name="Before",
        type="blood",
        markers=[
            _marker_create(catalog.id, value=15.5),
            _marker_create(catalog.id, value=10.0),
        ],
    )
    lab = await service.create_lab(body)
    original_marker_ids = {m.id for m in lab.markers}
    assert len(original_marker_ids) == 2

    new_markers = [_marker_create(catalog.id, value=14.0)]
    updated = await service.update_lab(
        lab.id, LabUpdate(name="After", markers=new_markers)
    )

    assert updated.name == "After"
    assert len(updated.markers) == 1
    # Only one marker exists on this lab now — replacement deleted the originals.
    assert updated.markers[0].value == 14.0
    db_markers = (
        (
            await async_db.execute(
                select(LabMarker).where(LabMarker.lab_id == lab.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(db_markers) == 1


async def test_update_lab_without_markers_leaves_them_alone(
    async_db: AsyncSession, service: LabsService
) -> None:
    catalog = await _make_catalog(async_db)
    body = LabCreate(
        lab_date=datetime.date(2026, 5, 1),
        name="Keep Markers",
        type="blood",
        markers=[_marker_create(catalog.id, value=15.5)],
    )
    lab = await service.create_lab(body)
    pre_ids = {m.id for m in lab.markers}

    updated = await service.update_lab(lab.id, LabUpdate(notes="add a note"))
    assert updated.notes == "add a note"
    assert {m.id for m in updated.markers} == pre_ids


async def test_update_lab_nonexistent_raises_not_found(service: LabsService) -> None:
    with pytest.raises(NotFoundError):
        await service.update_lab(99999, LabUpdate(name="nope"))


# ---------------------------------------------------------------------------
# delete_lab — cascades to markers
# ---------------------------------------------------------------------------


async def test_delete_lab_cascades_to_markers(
    async_db: AsyncSession, service: LabsService
) -> None:
    catalog = await _make_catalog(async_db)
    body = LabCreate(
        lab_date=datetime.date(2026, 5, 1),
        name="Delete Me",
        type="blood",
        markers=[
            _marker_create(catalog.id, value=15.5),
            _marker_create(catalog.id, value=14.0),
        ],
    )
    lab = await service.create_lab(body)
    lab_id = lab.id
    marker_ids = [m.id for m in lab.markers]

    await service.delete_lab(lab_id)

    assert (
        await async_db.execute(select(Lab).where(Lab.id == lab_id))
    ).scalar_one_or_none() is None
    for mid in marker_ids:
        assert (
            await async_db.execute(
                select(LabMarker).where(LabMarker.id == mid)
            )
        ).scalar_one_or_none() is None


async def test_delete_lab_nonexistent_raises_not_found(
    service: LabsService,
) -> None:
    with pytest.raises(NotFoundError):
        await service.delete_lab(99999)
