"""Tests for the OPENROUTER_API_KEY misconfiguration guards.

Regression coverage for the production failure where the Coolify
deployment had FOOD_ANALYSIS_ENABLED=true but no OPENROUTER_API_KEY,
causing every photo upload to crash with:
    httpx.LocalProtocolError: Illegal header value b'Bearer '
"""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis


@pytest_asyncio.fixture
async def db_with_photo(
    async_db: AsyncSession, async_engine, monkeypatch: pytest.MonkeyPatch
) -> tuple[AsyncSession, int]:
    """Persist a single photo + entry, so the trigger has something to look up.

    The trigger opens its own session via ``async_session_maker``. The
    SAVEPOINT fixture's connection isn't visible to that maker, so we COMMIT
    onto the real container DB here and the test cleans up by relying on the
    fact that the suite tears down the container at the end.

    Returns the session (still bound to the SAVEPOINT) and the new photo id.
    """
    # Use a fresh session-maker bound to the real engine so commits persist
    # past the SAVEPOINT rollback. This keeps the row visible to the trigger.
    real_maker = async_sessionmaker(
        async_engine, expire_on_commit=False, class_=AsyncSession
    )

    async with real_maker() as setup_session:
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
        setup_session.add(entry)
        await setup_session.commit()
        await setup_session.refresh(entry)

        photo = Photo(
            entry_id=entry.id,
            filename="test.jpg",
            original_filename="test.jpg",
            created_at=datetime.datetime.utcnow(),
        )
        setup_session.add(photo)
        await setup_session.commit()
        await setup_session.refresh(photo)
        photo_id = photo.id
        entry_id = entry.id

    # Patch the trigger's session maker to point at the same engine.
    monkeypatch.setattr(
        "app.services.food_analysis.async_session_maker", real_maker
    )

    try:
        yield async_db, photo_id
    finally:
        # Clean up rows we COMMITted so they don't leak between tests.
        async with real_maker() as cleanup:
            await cleanup.execute(
                PhotoAnalysis.__table__.delete().where(
                    PhotoAnalysis.photo_id == photo_id
                )
            )
            await cleanup.execute(
                Photo.__table__.delete().where(Photo.id == photo_id)
            )
            await cleanup.execute(
                Entry.__table__.delete().where(Entry.id == entry_id)
            )
            await cleanup.commit()


async def test_trigger_with_empty_api_key_marks_failed(
    db_with_photo: tuple[AsyncSession, int],
) -> None:
    """Production regression: with FOOD_ANALYSIS_ENABLED but no API key,
    the trigger must NOT call httpx (which would crash on Bearer ''),
    and must mark the analysis as failed with a clear error."""
    session, photo_id = db_with_photo

    with (
        patch("app.services.food_analysis.settings") as mock_settings,
        patch("app.services.food_analysis.httpx") as mock_httpx,
    ):
        mock_settings.openrouter_api_key = ""
        mock_settings.openrouter_model = "google/gemini-3-flash-preview"
        mock_settings.food_analysis_enabled = True

        from app.services import food_analysis

        await food_analysis.trigger_analysis_background(photo_id)

        # httpx must never have been invoked
        assert not mock_httpx.AsyncClient.called

    # An analysis row exists with status=failed and a clear error message
    analysis = (
        await session.execute(
            select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id)
        )
    ).scalar_one_or_none()
    # The trigger committed onto the real engine, but our async_db is bound to
    # a SAVEPOINT on a different connection — open a separate session.
    from app.services import food_analysis as fa

    async with fa.async_session_maker() as verify:
        analysis = (
            await verify.execute(
                select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id)
            )
        ).scalar_one_or_none()
    assert analysis is not None
    assert analysis.status == "failed"
    assert analysis.error_message is not None
    assert "OPENROUTER_API_KEY" in analysis.error_message


async def test_trigger_with_empty_key_updates_existing_pending(
    db_with_photo: tuple[AsyncSession, int],
) -> None:
    """If a pending record already exists (e.g. created by the retry
    endpoint), the guard should flip it to failed rather than skipping."""
    session, photo_id = db_with_photo

    # Pre-seed a pending record via a separate session bound to the real engine.
    from app.services import food_analysis as fa

    async with fa.async_session_maker() as seed:
        seed.add(
            PhotoAnalysis(
                photo_id=photo_id,
                status="pending",
                model_id="google/gemini-3-flash-preview",
            )
        )
        await seed.commit()

    with (
        patch("app.services.food_analysis.settings") as mock_settings,
        patch("app.services.food_analysis.httpx") as mock_httpx,
    ):
        mock_settings.openrouter_api_key = ""
        mock_settings.openrouter_model = "google/gemini-3-flash-preview"
        await fa.trigger_analysis_background(photo_id)
        assert not mock_httpx.AsyncClient.called

    async with fa.async_session_maker() as verify:
        analysis = (
            await verify.execute(
                select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id)
            )
        ).scalar_one_or_none()
    assert analysis is not None
    assert analysis.status == "failed"
    assert "OPENROUTER_API_KEY" in (analysis.error_message or "")
