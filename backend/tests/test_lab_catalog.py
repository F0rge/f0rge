from __future__ import annotations

import datetime
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.exceptions import ConflictError, NotFoundError
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.models.lab_marker_alias import LabMarkerAlias
from app.models.lab_marker_catalog import LabMarkerCatalog
from app.schemas.lab_marker import LabMarkerCatalogCreate
from app.services.lab_catalog import LabMarkerCatalogService


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


@pytest.fixture
def service(db: Session) -> LabMarkerCatalogService:
    return LabMarkerCatalogService(db)


def _seed_catalog(
    db: Session, canonical: str, display: str = "X", aliases: list[str] | None = None
) -> LabMarkerCatalog:
    item = LabMarkerCatalog(
        canonical_name=canonical,
        display_name=display,
        common_units=[],
    )
    db.add(item)
    db.flush()
    for a in aliases or []:
        db.add(LabMarkerAlias(catalog_id=item.id, alias=a.lower(), language=None))
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# resolve_or_create — lookup chain
# ---------------------------------------------------------------------------


def test_resolve_or_create_exact_canonical_hit(
    db: Session, service: LabMarkerCatalogService
) -> None:
    existing = _seed_catalog(db, "hemoglobin", "Hemoglobin")
    result = service.resolve_or_create("hemoglobin", "Hemoglobin")
    assert result.id == existing.id
    # No new alias should be created — input matches canonical exactly.
    assert db.query(LabMarkerAlias).count() == 0


def test_resolve_or_create_alias_hit_case_insensitive(
    db: Session, service: LabMarkerCatalogService
) -> None:
    existing = _seed_catalog(
        db, "hemoglobin", "Hemoglobin", aliases=["hemoglobina", "hb"]
    )
    # Input is upper-case alias.
    result = service.resolve_or_create("HEMOGLOBINA", "Hemoglobina")
    assert result.id == existing.id
    # Should not create a new catalog item.
    assert db.query(LabMarkerCatalog).count() == 1


def test_resolve_or_create_ilike_canonical_hit(
    db: Session, service: LabMarkerCatalogService
) -> None:
    """If exact lookup misses but ilike matches, return the existing item."""
    # Seed canonical "hemoglobin" — ilike will match a more decorated input
    # that normalizes back to the same string.
    existing = _seed_catalog(db, "hemoglobin", "Hemoglobin")
    # Different casing — normalized form equals canonical, so ilike fires.
    result = service.resolve_or_create("Hemoglobin", "Hemoglobin")
    assert result.id == existing.id


def test_resolve_or_create_creates_new_when_no_match(
    db: Session, service: LabMarkerCatalogService
) -> None:
    result = service.resolve_or_create("brand_new_marker", "Brand New Marker")
    assert result.id is not None
    assert result.canonical_name == "brand_new_marker"
    assert result.display_name == "Brand New Marker"
    # When input == canonical, no alias is created.
    assert db.query(LabMarkerAlias).count() == 0


def test_resolve_or_create_registers_alias_when_input_differs(
    db: Session, service: LabMarkerCatalogService
) -> None:
    """If we have to create a new entry AND input differs from canonical,
    register the input as an alias."""
    # Input "Vitamin D-25 OH" normalizes to "vitamin_d_25_oh"; the raw input
    # (lowered) is different from the canonical → registered as alias.
    result = service.resolve_or_create("Vitamin D-25 OH", "Vitamin D")
    assert result.canonical_name == "vitamin_d_25_oh"

    aliases = (
        db.query(LabMarkerAlias).filter(LabMarkerAlias.catalog_id == result.id).all()
    )
    assert len(aliases) == 1
    assert aliases[0].alias == "vitamin d-25 oh"


# ---------------------------------------------------------------------------
# add_alias
# ---------------------------------------------------------------------------


def test_add_alias_happy_path(db: Session, service: LabMarkerCatalogService) -> None:
    item = _seed_catalog(db, "hemoglobin", "Hemoglobin")
    alias = service.add_alias(item.id, "Hb", language="en")
    db.commit()
    assert alias.alias == "hb"  # stored lowercased
    assert alias.language == "en"


def test_add_alias_conflict_on_duplicate(
    db: Session, service: LabMarkerCatalogService
) -> None:
    item = _seed_catalog(db, "hemoglobin", "Hemoglobin", aliases=["hb"])
    with pytest.raises(ConflictError):
        service.add_alias(item.id, "HB", language=None)


def test_add_alias_not_found(service: LabMarkerCatalogService) -> None:
    with pytest.raises(NotFoundError):
        service.add_alias(99999, "anything", language=None)


# ---------------------------------------------------------------------------
# create_catalog_item
# ---------------------------------------------------------------------------


def test_create_catalog_item_normalizes_canonical(
    db: Session, service: LabMarkerCatalogService
) -> None:
    body = LabMarkerCatalogCreate(
        canonical_name="Vitamin D",
        display_name="Vitamin D",
        common_units=["ng/mL"],
    )
    item = service.create_catalog_item(body)
    db.commit()
    assert item.canonical_name == "vitamin_d"


def test_create_catalog_item_conflict_on_duplicate_canonical(
    db: Session, service: LabMarkerCatalogService
) -> None:
    _seed_catalog(db, "hemoglobin", "Hemoglobin")
    body = LabMarkerCatalogCreate(canonical_name="Hemoglobin", display_name="Hb")
    with pytest.raises(ConflictError):
        service.create_catalog_item(body)


# ---------------------------------------------------------------------------
# get_marker_history — order + skip null-value rows
# ---------------------------------------------------------------------------


def _add_lab_with_marker(
    db: Session,
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
    db.flush()
    marker = LabMarker(
        lab_id=lab.id,
        catalog_id=catalog_id,
        canonical_name=canonical,
        display_name=canonical,
        value=value,
        flag="normal" if value is not None else "unknown",
    )
    db.add(marker)
    db.commit()


def test_get_marker_history_ascending_date(
    db: Session, service: LabMarkerCatalogService
) -> None:
    catalog = _seed_catalog(db, "hemoglobin", "Hemoglobin")
    _add_lab_with_marker(
        db,
        catalog.id,
        lab_date=datetime.date(2026, 3, 1),
        canonical="hemoglobin",
        value=15.0,
    )
    _add_lab_with_marker(
        db,
        catalog.id,
        lab_date=datetime.date(2026, 1, 1),
        canonical="hemoglobin",
        value=14.0,
    )
    _add_lab_with_marker(
        db,
        catalog.id,
        lab_date=datetime.date(2026, 5, 1),
        canonical="hemoglobin",
        value=13.0,
    )

    history = service.get_marker_history("hemoglobin")
    assert [p.lab_date for p in history] == [
        datetime.date(2026, 1, 1),
        datetime.date(2026, 3, 1),
        datetime.date(2026, 5, 1),
    ]
    assert [p.value for p in history] == [14.0, 15.0, 13.0]


def test_get_marker_history_skips_null_values(
    db: Session, service: LabMarkerCatalogService
) -> None:
    catalog = _seed_catalog(db, "hemoglobin", "Hemoglobin")
    _add_lab_with_marker(
        db,
        catalog.id,
        lab_date=datetime.date(2026, 1, 1),
        canonical="hemoglobin",
        value=14.0,
    )
    _add_lab_with_marker(
        db,
        catalog.id,
        lab_date=datetime.date(2026, 2, 1),
        canonical="hemoglobin",
        value=None,
    )
    _add_lab_with_marker(
        db,
        catalog.id,
        lab_date=datetime.date(2026, 3, 1),
        canonical="hemoglobin",
        value=15.0,
    )

    history = service.get_marker_history("hemoglobin")
    assert len(history) == 2
    assert [p.value for p in history] == [14.0, 15.0]


def test_get_marker_history_unknown_canonical_returns_empty(
    service: LabMarkerCatalogService,
) -> None:
    assert service.get_marker_history("nonexistent") == []


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_no_query_returns_all(
    db: Session, service: LabMarkerCatalogService
) -> None:
    _seed_catalog(db, "hemoglobin", "Hemoglobin")
    _seed_catalog(db, "ferritin", "Ferritin")
    assert len(service.search(None)) == 2


def test_search_by_canonical(db: Session, service: LabMarkerCatalogService) -> None:
    _seed_catalog(db, "hemoglobin", "Hemoglobin")
    _seed_catalog(db, "ferritin", "Ferritin")
    results = service.search("hemo")
    assert len(results) == 1
    assert results[0].canonical_name == "hemoglobin"


def test_search_by_alias(db: Session, service: LabMarkerCatalogService) -> None:
    _seed_catalog(db, "hemoglobin", "Hemoglobin", aliases=["hemoglobina"])
    _seed_catalog(db, "ferritin", "Ferritin")
    results = service.search("hemoglobina")
    assert len(results) == 1
    assert results[0].canonical_name == "hemoglobin"
