"""Tests for the OPENROUTER_API_KEY misconfiguration guards.

Regression coverage for the production failure where the Coolify
deployment had FOOD_ANALYSIS_ENABLED=true but no OPENROUTER_API_KEY,
causing every photo upload to crash with:
    httpx.LocalProtocolError: Illegal header value b'Bearer '
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis


@pytest.fixture
def db_with_photo() -> Generator[tuple[Session, int], None, None]:
    """In-memory SQLite with a single photo + entry, so the trigger has
    something to look up."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    import datetime

    entry = Entry(
        date=datetime.date.today(),
        overall=2,
        bloating=0,
        stool_normal=True,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        hot_shower=False,
    )
    session.add(entry)
    session.commit()
    photo = Photo(
        entry_id=entry.id,
        filename="test.jpg",
        original_filename="test.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    session.add(photo)
    session.commit()
    photo_id = photo.id
    try:
        yield session, photo_id
    finally:
        session.close()
        # The background trigger creates its own SessionLocal — point it at
        # this in-memory engine for the test.


def test_trigger_with_empty_api_key_marks_failed(
    db_with_photo: tuple[Session, int],
) -> None:
    """Production regression: with FOOD_ANALYSIS_ENABLED but no API key,
    the trigger must NOT call httpx (which would crash on Bearer ''),
    and must mark the analysis as failed with a clear error."""
    session, photo_id = db_with_photo

    # Patch SessionLocal to return our in-memory session, settings to have
    # an empty key, and httpx to ensure it's never called.
    with (
        patch("app.services.food_analysis.SessionLocal", return_value=session),
        patch("app.services.food_analysis.settings") as mock_settings,
        patch("app.services.food_analysis.httpx") as mock_httpx,
    ):
        mock_settings.openrouter_api_key = ""
        mock_settings.openrouter_model = "google/gemini-3-flash-preview"
        mock_settings.food_analysis_enabled = True
        # SessionLocal() is called with no args; patch as a factory.
        from app.services import food_analysis

        food_analysis.SessionLocal = MagicMock(return_value=session)

        food_analysis.trigger_analysis_background(photo_id)

        # httpx must never have been invoked
        assert not mock_httpx.post.called

    # An analysis row exists with status=failed and a clear error message
    analysis = (
        session.query(PhotoAnalysis).filter(PhotoAnalysis.photo_id == photo_id).first()
    )
    assert analysis is not None
    assert analysis.status == "failed"
    assert analysis.error_message is not None
    assert "OPENROUTER_API_KEY" in analysis.error_message


def test_trigger_with_empty_key_updates_existing_pending(
    db_with_photo: tuple[Session, int],
) -> None:
    """If a pending record already exists (e.g. created by the retry
    endpoint), the guard should flip it to failed rather than skipping."""
    session, photo_id = db_with_photo

    # Pre-seed a pending record
    pending = PhotoAnalysis(
        photo_id=photo_id,
        status="pending",
        model_id="google/gemini-3-flash-preview",
    )
    session.add(pending)
    session.commit()

    with (
        patch("app.services.food_analysis.settings") as mock_settings,
        patch("app.services.food_analysis.httpx") as mock_httpx,
    ):
        mock_settings.openrouter_api_key = ""
        mock_settings.openrouter_model = "google/gemini-3-flash-preview"
        from app.services import food_analysis

        food_analysis.SessionLocal = MagicMock(return_value=session)
        food_analysis.trigger_analysis_background(photo_id)

        assert not mock_httpx.post.called

    session.expire_all()
    analysis = (
        session.query(PhotoAnalysis).filter(PhotoAnalysis.photo_id == photo_id).first()
    )
    assert analysis is not None
    assert analysis.status == "failed"
    assert "OPENROUTER_API_KEY" in (analysis.error_message or "")
