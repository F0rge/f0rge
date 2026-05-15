from __future__ import annotations

import datetime
from collections.abc import Generator
from typing import Optional

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.treatment import Treatment
from app.routers.treatments import (
    _normalize_name,
    create_treatment,
    delete_treatment,
    get_treatment,
    list_treatments,
    update_treatment,
)
from app.schemas.treatment import TreatmentCreate, TreatmentUpdate


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


@pytest.fixture(autouse=True)
def no_vault_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Suppress vault re-rendering so tests don't need a vault on disk."""
    monkeypatch.setattr(
        "app.routers.treatments.write_daily_file",
        lambda *args, **kwargs: None,
    )


# ---------------------------------------------------------------------------
# _normalize_name
# ---------------------------------------------------------------------------


def test_normalize_lowercase() -> None:
    assert _normalize_name("Rifaximin") == "rifaximin"


def test_normalize_spaces_to_underscore() -> None:
    assert _normalize_name("Fish Oil") == "fish_oil"


def test_normalize_special_chars_stripped() -> None:
    # '+' is not in [a-z0-9_] so it is stripped; spaces → underscores first
    assert _normalize_name("D3 + K2") == "d3__k2"


def test_normalize_trims_whitespace() -> None:
    assert _normalize_name("  spaces  ") == "spaces"


def test_normalize_dashes_to_underscore() -> None:
    assert _normalize_name("dashes-here") == "dashes_here"


# ---------------------------------------------------------------------------
# create_treatment
# ---------------------------------------------------------------------------


def test_create_happy_path(db: Session) -> None:
    body = TreatmentCreate(
        name="Allicin",
        type="antimicrobial",
        start_date=datetime.date(2026, 1, 1),
    )
    result = create_treatment(body, db=db)

    assert result.id is not None
    assert result.name == "Allicin"
    assert result.normalized_name == "allicin"
    assert result.type == "antimicrobial"
    assert result.start_date == datetime.date(2026, 1, 1)
    assert result.end_date is None
    assert result.created_at is not None
    assert result.updated_at is not None


def test_create_end_date_before_start_raises_400(db: Session) -> None:
    body = TreatmentCreate(
        name="Rifaximin",
        type="antibiotic",
        start_date=datetime.date(2026, 2, 10),
        end_date=datetime.date(2026, 2, 5),
    )
    with pytest.raises(HTTPException) as exc_info:
        create_treatment(body, db=db)
    assert exc_info.value.status_code == 400


def test_create_duplicate_names_allowed(db: Session) -> None:
    """Treatments are not unique by name — two with the same name is valid."""
    body = TreatmentCreate(
        name="Allicin",
        type="antimicrobial",
        start_date=datetime.date(2026, 1, 1),
    )
    t1 = create_treatment(body, db=db)
    t2 = create_treatment(body, db=db)
    assert t1.id != t2.id


def test_create_optional_fields_null(db: Session) -> None:
    body = TreatmentCreate(
        name="Berberine",
        type="other",
        start_date=datetime.date(2026, 3, 1),
        dose=None,
        notes=None,
        end_date=None,
    )
    result = create_treatment(body, db=db)
    assert result.dose is None
    assert result.notes is None
    assert result.end_date is None


def test_create_with_end_date_equal_to_start_date_ok(db: Session) -> None:
    body = TreatmentCreate(
        name="Oregano",
        type="antimicrobial",
        start_date=datetime.date(2026, 5, 1),
        end_date=datetime.date(2026, 5, 1),
    )
    result = create_treatment(body, db=db)
    assert result.start_date == result.end_date


# ---------------------------------------------------------------------------
# list_treatments
# ---------------------------------------------------------------------------


def _add_treatment(
    db: Session,
    name: str,
    start_date: datetime.date,
    end_date: Optional[datetime.date] = None,
) -> Treatment:
    t = Treatment(
        name=name,
        normalized_name=_normalize_name(name),
        type="other",
        start_date=start_date,
        end_date=end_date,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def test_list_empty(db: Session) -> None:
    # active_on must be passed explicitly as None; calling with no args
    # leaves it as the FastAPI Query sentinel, not None
    results = list_treatments(active_on=None, db=db)
    assert results == []


def test_list_ongoing_first(db: Session) -> None:
    """Ongoing treatments (end_date=None) sort before finished ones."""
    _add_treatment(
        db, "Finished", datetime.date(2026, 1, 1), datetime.date(2026, 1, 31)
    )
    _add_treatment(db, "Ongoing", datetime.date(2026, 2, 1))

    results = list_treatments(active_on=None, db=db)
    assert results[0].name == "Ongoing"
    assert results[1].name == "Finished"


def test_list_active_on_includes_ongoing(db: Session) -> None:
    _add_treatment(db, "Ongoing", datetime.date(2026, 1, 1))
    results = list_treatments(active_on="2026-06-01", db=db)
    assert len(results) == 1
    assert results[0].name == "Ongoing"


def test_list_active_on_boundary_end_date_included(db: Session) -> None:
    """active_on == end_date should still be considered active (inclusive)."""
    _add_treatment(
        db,
        "Short",
        datetime.date(2026, 5, 1),
        datetime.date(2026, 5, 15),
    )
    results = list_treatments(active_on="2026-05-15", db=db)
    assert len(results) == 1


def test_list_active_on_excludes_expired(db: Session) -> None:
    _add_treatment(
        db,
        "Expired",
        datetime.date(2026, 1, 1),
        datetime.date(2026, 1, 31),
    )
    results = list_treatments(active_on="2026-02-01", db=db)
    assert results == []


def test_list_active_on_excludes_not_yet_started(db: Session) -> None:
    _add_treatment(db, "Future", datetime.date(2026, 12, 1))
    results = list_treatments(active_on="2026-05-15", db=db)
    assert results == []


def test_list_active_on_mixed(db: Session) -> None:
    _add_treatment(db, "Active", datetime.date(2026, 1, 1), datetime.date(2026, 6, 30))
    _add_treatment(
        db, "Expired", datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)
    )
    _add_treatment(db, "Ongoing", datetime.date(2026, 3, 1))

    results = list_treatments(active_on="2026-05-15", db=db)
    names = {r.name for r in results}
    assert names == {"Active", "Ongoing"}


# ---------------------------------------------------------------------------
# get_treatment
# ---------------------------------------------------------------------------


def test_get_existing(db: Session) -> None:
    t = _add_treatment(db, "Allicin", datetime.date(2026, 1, 1))
    result = get_treatment(t.id, db=db)
    assert result.id == t.id
    assert result.name == "Allicin"


def test_get_nonexistent_raises_404(db: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_treatment(999, db=db)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# update_treatment
# ---------------------------------------------------------------------------


def test_update_partial_name_only(db: Session) -> None:
    t = _add_treatment(db, "Old Name", datetime.date(2026, 1, 1))
    body = TreatmentUpdate(name="New Name")
    result = update_treatment(t.id, body, db=db)

    assert result.name == "New Name"
    assert result.normalized_name == "new_name"
    # Other fields unchanged
    assert result.start_date == datetime.date(2026, 1, 1)
    assert result.end_date is None


def test_update_name_recomputes_normalized_name(db: Session) -> None:
    t = _add_treatment(db, "Fish Oil", datetime.date(2026, 1, 1))
    body = TreatmentUpdate(name="Cod Liver Oil")
    result = update_treatment(t.id, body, db=db)
    assert result.normalized_name == "cod_liver_oil"


def test_update_end_date_before_start_raises_400(db: Session) -> None:
    t = _add_treatment(
        db,
        "Rifaximin",
        datetime.date(2026, 3, 1),
        datetime.date(2026, 3, 31),
    )
    body = TreatmentUpdate(end_date=datetime.date(2026, 2, 1))
    with pytest.raises(HTTPException) as exc_info:
        update_treatment(t.id, body, db=db)
    assert exc_info.value.status_code == 400


def test_update_nonexistent_raises_404(db: Session) -> None:
    body = TreatmentUpdate(name="Whatever")
    with pytest.raises(HTTPException) as exc_info:
        update_treatment(999, body, db=db)
    assert exc_info.value.status_code == 404


def test_update_unset_fields_are_not_touched(db: Session) -> None:
    """model_dump(exclude_unset=True) must leave unchanged fields alone."""
    t = _add_treatment(db, "Allicin", datetime.date(2026, 1, 1))
    # Give it a dose first
    t.dose = "450 mg"
    db.commit()

    body = TreatmentUpdate(notes="Updated note")
    result = update_treatment(t.id, body, db=db)
    assert result.dose == "450 mg"
    assert result.notes == "Updated note"


# ---------------------------------------------------------------------------
# delete_treatment
# ---------------------------------------------------------------------------


def test_delete_returns_none(db: Session) -> None:
    t = _add_treatment(db, "Allicin", datetime.date(2026, 1, 1))
    result = delete_treatment(t.id, db=db)
    assert result is None


def test_delete_nonexistent_raises_404(db: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        delete_treatment(999, db=db)
    assert exc_info.value.status_code == 404


def test_delete_removes_from_db(db: Session) -> None:
    t = _add_treatment(db, "Allicin", datetime.date(2026, 1, 1))
    tid = t.id
    delete_treatment(tid, db=db)
    assert db.query(Treatment).filter(Treatment.id == tid).first() is None
