from __future__ import annotations

import datetime
from collections.abc import Generator

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.entry import Entry
from app.models.symptom_catalog import SymptomCatalogItem
from app.schemas.entry import EntryCreate, EntryResponse
from app.services import symptom_catalog as symptom_catalog_service


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


def _make_entry(
    db: Session,
    date: datetime.date,
    symptoms_json: dict | None = None,
) -> Entry:
    """Helper: create an Entry directly via ORM (bypasses router)."""
    entry = Entry(
        date=date,
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
    db.commit()
    db.refresh(entry)
    return entry


_DATE = datetime.date(2026, 5, 15)


# ---------------------------------------------------------------------------
# Schema validation — Pydantic layer
# ---------------------------------------------------------------------------


def test_schema_valid_symptoms_json() -> None:
    data = EntryCreate(
        date=_DATE,
        overall=2,
        bloating=0,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        symptoms_json={"vss": 7, "tinnitus": 6},
    )
    assert data.symptoms_json == {"vss": 7, "tinnitus": 6}


def test_schema_severity_out_of_range_raises() -> None:
    with pytest.raises(PydanticValidationError, match="severity must be integer 0-10"):
        EntryCreate(
            date=_DATE,
            overall=2,
            bloating=0,
            joint_pain=0,
            neuro=0,
            sleep_quality=2,
            stress=1,
            diet_risk="normal",
            supplements="",
            sick=False,
            symptoms_json={"vss": 11},
        )


def test_schema_uppercase_key_raises() -> None:
    with pytest.raises(PydanticValidationError, match=r"\^.a-z0-9_"):
        EntryCreate(
            date=_DATE,
            overall=2,
            bloating=0,
            joint_pain=0,
            neuro=0,
            sleep_quality=2,
            stress=1,
            diet_risk="normal",
            supplements="",
            sick=False,
            symptoms_json={"VSS": 7},
        )


def test_schema_non_int_value_raises() -> None:
    with pytest.raises(PydanticValidationError, match="severity must be integer 0-10"):
        EntryCreate(
            date=_DATE,
            overall=2,
            bloating=0,
            joint_pain=0,
            neuro=0,
            sleep_quality=2,
            stress=1,
            diet_risk="normal",
            supplements="",
            sick=False,
            symptoms_json={"vss": "high"},  # type: ignore[dict-item]
        )


def test_schema_omitted_symptoms_json_defaults_to_none() -> None:
    data = EntryCreate(
        date=_DATE,
        overall=2,
        bloating=0,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
    )
    assert data.symptoms_json is None


# ---------------------------------------------------------------------------
# ORM / service layer
# ---------------------------------------------------------------------------


def test_entry_stores_and_retrieves_symptoms_json(db: Session) -> None:
    _make_entry(db, _DATE, {"vss": 7, "tinnitus": 6})
    # Re-fetch from DB to verify persistence
    fetched = db.query(Entry).filter(Entry.date == _DATE).one()
    assert fetched.symptoms_json == {"vss": 7, "tinnitus": 6}


def test_entry_omitted_symptoms_defaults_to_empty_dict(db: Session) -> None:
    entry = _make_entry(db, _DATE)
    assert entry.symptoms_json == {}

    response = EntryResponse.model_validate(entry)
    assert response.symptoms_json == {}


def test_touch_sets_catalog_timestamps_after_create(db: Session) -> None:
    """After creating an entry that references 'vss', the catalog row should
    have first_used_at and last_used_at populated."""
    symptom_catalog_service.create_item(db, "vss", "Visual Snow")

    entry = _make_entry(db, _DATE, {"vss": 7})
    # Simulate what the router does after add/before commit
    symptom_catalog_service.touch(db, list(entry.symptoms_json.keys()))
    db.commit()

    item = db.query(SymptomCatalogItem).filter(SymptomCatalogItem.key == "vss").one()
    assert item.first_used_at is not None
    assert item.last_used_at is not None


def test_touch_on_update_sets_first_used_at_for_new_symptom(db: Session) -> None:
    """Adding a new symptom during an update should set first_used_at."""
    symptom_catalog_service.create_item(db, "tinnitus", "Tinnitus")
    entry = _make_entry(db, _DATE, {})

    # Simulate update adding tinnitus
    entry.symptoms_json = {"tinnitus": 5}
    db.add(entry)
    symptom_catalog_service.touch(db, list(entry.symptoms_json.keys()))
    db.commit()
    db.refresh(entry)

    item = (
        db.query(SymptomCatalogItem).filter(SymptomCatalogItem.key == "tinnitus").one()
    )
    assert item.first_used_at is not None


def test_touch_silently_ignores_unknown_keys(db: Session) -> None:
    """touch() must not raise when a key is not in the catalog."""
    entry = _make_entry(db, _DATE, {"unknown_xyz": 5})
    # Should not raise
    symptom_catalog_service.touch(db, list(entry.symptoms_json.keys()))
    db.commit()
