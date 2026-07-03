"""Integration tests for ``PhotoService.upload`` exercising the real seams.

These tests intentionally do **not** monkeypatch ``save_photo``,
``delete_photo``, or ``render_and_write_daily_file``. The whole point of
this file is to exercise the full filesystem + DB + vault rendering path
end-to-end against a real temporary photo dir and vault dir, because a
prior mock-heavy suite ("test_photos_meal_time.py") was unable to catch
the 2026-05-16 ``FileExistsError`` regression on a stale orphan file.

Coverage map:
- A: happy path, sequential uploads write distinct files + DB rows + vault.
- B: orphan file on disk (no DB row) does NOT collide with the next upload.
- C: commit failure cleans up the just-written file (no orphan left behind).
- D: background-analysis failure writes a short ``error_message`` (no traceback).
"""

from __future__ import annotations

import datetime
import io
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks, UploadFile
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.services.photos import PhotoService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _png_bytes() -> bytes:
    img = Image.new("RGB", (10, 10), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _make_entry(db: AsyncSession, day: datetime.date) -> Entry:
    entry = Entry(
        date=day,
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
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def _upload(
    service: PhotoService,
    day: datetime.date,
) -> Photo:
    upload = UploadFile(filename="test.png", file=io.BytesIO(_png_bytes()))
    return await service.upload(
        entry_date=day,
        file=upload,
        label=None,
        meal_time=None,
        background_tasks=BackgroundTasks(),
    )


# ---------------------------------------------------------------------------
# Fixture: real on-disk storage, no monkeypatched collaborators
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def real_storage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Redirect ``photo_dir`` and ``vault_path`` to tmp directories.

    Critically, this fixture does NOT monkeypatch ``render_and_write_daily_file``,
    ``save_photo``, ``delete_photo``, or ``write_daily_file``. Those are the
    seams under test — mocking them is the bug this test file exists to
    prevent (see ``feedback_no_mocks_at_seam_under_test.md``).
    """
    photo_dir = tmp_path / "photos"
    vault_dir = tmp_path / "vault"
    photo_dir.mkdir()
    vault_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "vault_path", str(vault_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    yield


# ---------------------------------------------------------------------------
# Test A — happy path: three sequential uploads
# ---------------------------------------------------------------------------


async def test_sequential_uploads_write_files_db_rows_and_vault(
    async_db: AsyncSession, real_storage: None
) -> None:
    day = datetime.date(2026, 5, 16)
    await _make_entry(async_db, day)
    service = PhotoService(async_db)

    photos = [await _upload(service, day) for _ in range(3)]

    # Expected filename progression.
    expected = [f"{day.isoformat()}_photo-{n}.jpg" for n in (1, 2, 3)]
    assert [p.filename for p in photos] == expected

    # Each file exists on disk under settings.photo_dir.
    for name in expected:
        path = os.path.join(settings.photo_dir, name)
        assert os.path.exists(path), f"Photo file missing on disk: {path}"

    # Each row exists in the photos table.
    rows = (
        await async_db.execute(select(Photo.filename).where(Photo.entry_id == photos[0].entry_id))
    ).all()
    db_filenames = sorted(r[0] for r in rows)
    assert db_filenames == sorted(expected)

    # Vault file includes the three embeds. The vault is the real rendering,
    # not a no-op stub, so this assertion guards both photos.py and the
    # obsidian renderer.
    vault_file = os.path.join(settings.vault_path, "Daily", "Health-Logs", f"{day.isoformat()}.md")
    assert os.path.exists(vault_file)
    content = open(vault_file, encoding="utf-8").read()
    for name in expected:
        assert f"![[attachments/{name}]]" in content, f"Vault file missing embed for {name}"


# ---------------------------------------------------------------------------
# Test B — orphan file regression
# ---------------------------------------------------------------------------


async def test_orphan_file_on_disk_does_not_collide_with_next_upload(
    async_db: AsyncSession, real_storage: None
) -> None:
    """Regression for the 2026-05-16 production outage.

    A stale ``_photo-2.jpg`` exists on disk with no matching DB row. The
    next upload must skip that number, not raise FileExistsError.
    """
    day = datetime.date(2026, 5, 16)
    await _make_entry(async_db, day)

    orphan_name = f"{day.isoformat()}_photo-2.jpg"
    orphan_path = os.path.join(settings.photo_dir, orphan_name)
    with open(orphan_path, "wb") as f:
        f.write(b"orphan-bytes-not-a-real-image")

    service = PhotoService(async_db)

    # Pre-bug behaviour: this would raise FileExistsError because the
    # filename generator picked _photo-1, then a real upload for _photo-2
    # collided with the orphan. Post-fix: scan disk + DB and pick _photo-3.
    photo = await _upload(service, day)
    assert photo.filename == f"{day.isoformat()}_photo-3.jpg"

    # Orphan untouched.
    assert os.path.exists(orphan_path)
    with open(orphan_path, "rb") as f:
        assert f.read() == b"orphan-bytes-not-a-real-image"

    # And a follow-up upload jumps to _photo-4 (orphan still counted).
    photo2 = await _upload(service, day)
    assert photo2.filename == f"{day.isoformat()}_photo-4.jpg"


# ---------------------------------------------------------------------------
# Test C — commit failure cleans up the just-written file
# ---------------------------------------------------------------------------


async def test_commit_failure_removes_file_from_disk(
    async_db: AsyncSession, real_storage: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the post-write DB commit fails, the file must not remain orphaned.

    Invariant under test: ``a file on disk implies a DB row exists``.
    """
    day = datetime.date(2026, 5, 16)
    await _make_entry(async_db, day)

    # Patch ``commit`` only AFTER setup so _make_entry's own commit succeeds.
    # Use a one-shot failure so post-exception cleanup (delete_photo) and
    # the SAVEPOINT teardown still work normally.
    original_commit = async_db.commit
    state = {"raised": False}

    async def _fail_once(*args, **kwargs):
        if not state["raised"]:
            state["raised"] = True
            raise RuntimeError("simulated commit failure")
        return await original_commit(*args, **kwargs)

    monkeypatch.setattr(async_db, "commit", _fail_once)

    service = PhotoService(async_db)

    # Snapshot disk state before — we want to assert no NEW file was orphaned.
    files_before = set(os.listdir(settings.photo_dir))

    with pytest.raises(RuntimeError, match="simulated commit failure"):
        await _upload(service, day)

    # No new files appeared. The just-written file was cleaned up.
    # This is the load-bearing invariant for the bug: a failed commit must
    # not leave an orphan file that the next upload would collide with.
    files_after = set(os.listdir(settings.photo_dir))
    assert files_after == files_before, (
        f"Orphan files left behind after commit failure: {files_after - files_before}"
    )
    # Note: we don't assert on the photos table state here. The session is
    # SAVEPOINT-bound — ``db.add()`` is staged in the identity map regardless
    # of whether the (mocked) commit raised. In production with a real engine
    # the failed commit means no INSERT lands; that's a separate property and
    # not what this regression test is guarding.


# ---------------------------------------------------------------------------
# Test D — background analysis fallback writes a short error_message
# ---------------------------------------------------------------------------


async def test_analysis_fallback_error_message_is_short_no_traceback(
    async_db: AsyncSession,
    async_engine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """The analysis fallback must record a single-line error, not a traceback.

    Covers two surfaces of ``food_analysis.py``:

    1. The guard path (empty API key) — already short and well-formed.
    2. The except-block path — where ``error_message = traceback.format_exc()``
       used to leak multi-line stack traces to the frontend. After the fix it
       must be ``f"{type(e).__name__}: {str(e)[:200]}"``.

    Both branches are exercised here so any regression in either is caught.

    ``trigger_analysis_background`` opens its own session via
    ``async_session_maker``. The SAVEPOINT fixture's connection isn't visible
    to that maker, so we COMMIT onto the real container DB (entry + photo + a
    real on-disk image) and clean up at the end.
    """
    photo_dir = tmp_path / "photos"
    vault_dir = tmp_path / "vault"
    photo_dir.mkdir()
    vault_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "vault_path", str(vault_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", True)

    # Use a session-maker bound to the same container engine the test uses,
    # because the trigger calls async_session_maker() internally.
    real_maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr("app.services.food_analysis.async_session_maker", real_maker)

    day = datetime.date(2026, 5, 16)
    filename = f"{day.isoformat()}_photo-1.jpg"

    # Seed entry + photo committed to the real engine so the trigger can find
    # them when it opens its own session.
    async with real_maker() as setup:
        entry = Entry(
            date=day,
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
        setup.add(entry)
        await setup.commit()
        await setup.refresh(entry)

        photo = Photo(
            entry_id=entry.id,
            filename=filename,
            original_filename="test.png",
            created_at=datetime.datetime.utcnow(),
        )
        setup.add(photo)
        await setup.commit()
        await setup.refresh(photo)
        photo_id = photo.id
        entry_id = entry.id

    # Also drop a real JPEG file on disk in case the trigger reads it before
    # the exception path is reached.
    with open(os.path.join(str(photo_dir), filename), "wb") as f:
        f.write(_png_bytes())

    from app.services import food_analysis as fa

    try:
        # ---- Branch 1: guard path (empty key) ----
        monkeypatch.setattr(settings, "openrouter_api_key", "")
        await fa.trigger_analysis_background(photo_id)

        async with real_maker() as verify:
            analysis = (
                await verify.execute(
                    select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id)
                )
            ).scalar_one_or_none()
        assert analysis is not None
        assert analysis.status == "failed"
        assert analysis.error_message is not None
        assert len(analysis.error_message) < 250, (
            f"Guard error_message too long ({len(analysis.error_message)} chars): "
            f"{analysis.error_message!r}"
        )
        assert "Traceback (most recent call last)" not in analysis.error_message

        # ---- Branch 2: exception in the analysis pipeline ----
        # Provide a non-empty key so the guard is bypassed, then force the
        # OpenRouter call to raise so we hit the except block at
        # food_analysis.py:341.
        monkeypatch.setattr(settings, "openrouter_api_key", "test-key-not-real")

        class _BoomClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def complete_with_image(self, *args, **kwargs) -> str:
                raise RuntimeError("simulated upstream failure: " + ("x" * 500))

        monkeypatch.setattr("app.services.llm.openrouter.OpenRouterClient", _BoomClient)

        await fa.trigger_analysis_background(photo_id)

        async with real_maker() as verify:
            analysis = (
                await verify.execute(
                    select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id)
                )
            ).scalar_one_or_none()
        assert analysis is not None
        assert analysis.status == "failed"
        assert analysis.error_message is not None
        assert len(analysis.error_message) < 250, (
            f"Exception-path error_message too long "
            f"({len(analysis.error_message)} chars): {analysis.error_message!r}"
        )
        assert "Traceback (most recent call last)" not in analysis.error_message
        # And the type name should be carried through (sanity check that the
        # sanitization keeps something useful in the message).
        assert "RuntimeError" in analysis.error_message

    finally:
        # Clean up the rows we COMMITted onto the real engine.
        async with real_maker() as cleanup:
            await cleanup.execute(
                PhotoAnalysis.__table__.delete().where(PhotoAnalysis.photo_id == photo_id)
            )
            await cleanup.execute(Photo.__table__.delete().where(Photo.id == photo_id))
            await cleanup.execute(Entry.__table__.delete().where(Entry.id == entry_id))
            await cleanup.commit()
