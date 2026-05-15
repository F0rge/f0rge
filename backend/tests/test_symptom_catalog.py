from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.main import DEFAULT_SYMPTOMS, _seed_symptom_catalog
from app.models.symptom_catalog import SymptomCatalogItem
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


# ---------------------------------------------------------------------------
# create_item
# ---------------------------------------------------------------------------


def test_create_normalizes_key(db: Session) -> None:
    item = symptom_catalog_service.create_item(db, "VSS", "Visual Snow")
    assert item.id is not None
    assert item.key == "vss"
    assert item.label == "Visual Snow"


def test_create_returns_201_equivalent(db: Session) -> None:
    """create_item returns the persisted item with an id."""
    item = symptom_catalog_service.create_item(db, "tinnitus", "Tinnitus")
    assert item.id is not None


def test_create_bad_key_raises_validation_error(db: Session) -> None:
    with pytest.raises(ValidationError):
        symptom_catalog_service.create_item(db, "!!!", "Bad Key")


def test_create_duplicate_active_raises_conflict(db: Session) -> None:
    symptom_catalog_service.create_item(db, "vss", "Visual Snow")
    with pytest.raises(ConflictError):
        symptom_catalog_service.create_item(db, "vss", "Visual Snow 2")


def test_create_duplicate_archived_unarchives_and_updates_label(db: Session) -> None:
    """POST on an archived key un-archives it and updates the label (not 409)."""
    item = symptom_catalog_service.create_item(db, "vss", "Visual Snow")
    symptom_catalog_service.update_item(db, "vss", {"archived": True})

    restored = symptom_catalog_service.create_item(db, "vss", "VSS Updated")
    assert restored.id == item.id
    assert restored.archived is False
    assert restored.label == "VSS Updated"


# ---------------------------------------------------------------------------
# update_item
# ---------------------------------------------------------------------------


def test_update_archive_then_restore(db: Session) -> None:
    symptom_catalog_service.create_item(db, "vss", "Visual Snow")

    archived = symptom_catalog_service.update_item(db, "vss", {"archived": True})
    assert archived.archived is True

    restored = symptom_catalog_service.update_item(db, "vss", {"archived": False})
    assert restored.archived is False


def test_update_not_found_raises(db: Session) -> None:
    with pytest.raises(NotFoundError):
        symptom_catalog_service.update_item(db, "nonexistent", {"archived": True})


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------


def test_list_defaults_to_active_only(db: Session) -> None:
    symptom_catalog_service.create_item(db, "vss", "Visual Snow")
    symptom_catalog_service.create_item(db, "tinnitus", "Tinnitus")
    symptom_catalog_service.update_item(db, "tinnitus", {"archived": True})

    active = symptom_catalog_service.list_items(db)
    keys = [i.key for i in active]
    assert "vss" in keys
    assert "tinnitus" not in keys


def test_list_include_archived(db: Session) -> None:
    symptom_catalog_service.create_item(db, "vss", "Visual Snow")
    symptom_catalog_service.create_item(db, "tinnitus", "Tinnitus")
    symptom_catalog_service.update_item(db, "tinnitus", {"archived": True})

    all_items = symptom_catalog_service.list_items(db, include_archived=True)
    keys = [i.key for i in all_items]
    assert "vss" in keys
    assert "tinnitus" in keys


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------


def test_seed_idempotent(db: Session) -> None:
    """Calling the seed function twice must produce exactly 7 rows."""
    import app.main as main_module

    # Patch engine so _seed_symptom_catalog uses the test in-memory DB.
    original_engine = main_module.engine
    main_module.engine = db.get_bind()
    try:
        _seed_symptom_catalog()
        _seed_symptom_catalog()
    finally:
        main_module.engine = original_engine

    count = db.query(SymptomCatalogItem).count()
    assert count == len(DEFAULT_SYMPTOMS)
    assert count == 7
