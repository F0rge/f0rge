"""Regression tests for issue #9 -- photo filename collision after deletion.

Before this fix, `upload_photo` used `existing_count + 1` to pick the photo
number. After a photo was deleted, the count dropped but surviving photos
kept their original numbers, so the next upload reused a number that was
still on disk. `save_photo` then silently overwrote the existing file, and
two DB rows ended up pointing at the same filename.

The fix is to derive the next number from `max(existing_photo_numbers) + 1`
parsed out of filenames, so deleted numbers stay permanently retired.

These tests also pin down a defense-in-depth guard: `save_photo` must
refuse to overwrite an existing file, so any future numbering bug fails
loudly instead of corrupting data.
"""

from __future__ import annotations

import datetime
import io
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks, UploadFile
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entry import Entry
from app.models.photo import Photo
from app.services.photo_storage import save_photo
from app.services.photos import PhotoService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def real_storage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Point photo_dir + vault_path at tmp_path; exercise real PhotoService seams.

    Does not monkeypatch ``render_and_write_daily_file``, ``save_photo``, or
    ``delete_photo`` — same contract as ``test_photos_upload_integration.py``.
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
# Helpers
# ---------------------------------------------------------------------------


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


def _png_bytes() -> bytes:
    """A tiny valid PNG that Pillow can open + resize_image can re-encode."""
    img = Image.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _upload(db: AsyncSession, day: datetime.date, name: str = "x.png") -> Photo:
    upload = UploadFile(filename=name, file=io.BytesIO(_png_bytes()))
    service = PhotoService(db)
    return await service.upload(
        entry_date=day,
        file=upload,
        label=None,
        meal_time=None,
        background_tasks=BackgroundTasks(),
    )


async def _delete(db: AsyncSession, photo_id: int) -> None:
    await PhotoService(db).delete(photo_id)


# ---------------------------------------------------------------------------
# Filename-selection tests (the actual bug)
# ---------------------------------------------------------------------------


async def test_first_upload_gets_photo_1(async_db: AsyncSession, real_storage: None) -> None:
    day = datetime.date(2026, 5, 15)
    await _make_entry(async_db, day)

    photo = await _upload(async_db, day)

    assert photo.filename == "2026-05-15_photo-1.jpg"


async def test_second_upload_gets_photo_2(async_db: AsyncSession, real_storage: None) -> None:
    day = datetime.date(2026, 5, 15)
    await _make_entry(async_db, day)

    await _upload(async_db, day)
    second = await _upload(async_db, day)

    assert second.filename == "2026-05-15_photo-2.jpg"


async def test_delete_photo_1_then_upload_gets_photo_3(
    async_db: AsyncSession, real_storage: None
) -> None:
    """The regression case from issue #9: deleting photo-1 must NOT cause
    the next upload to be numbered 2 (which would collide with the existing
    photo-2 on disk)."""
    day = datetime.date(2026, 5, 15)
    await _make_entry(async_db, day)

    first = await _upload(async_db, day)
    second = await _upload(async_db, day)
    assert first.filename == "2026-05-15_photo-1.jpg"
    assert second.filename == "2026-05-15_photo-2.jpg"

    await _delete(async_db, first.id)

    third = await _upload(async_db, day)
    assert third.filename == "2026-05-15_photo-3.jpg", (
        "After deleting photo-1, the third upload must skip to photo-3. "
        "Reusing photo-2 would silently overwrite the existing file."
    )


async def test_delete_photo_2_then_upload_gets_photo_4(
    async_db: AsyncSession, real_storage: None
) -> None:
    """Same principle, deleting from the middle of the sequence."""
    day = datetime.date(2026, 5, 15)
    await _make_entry(async_db, day)

    await _upload(async_db, day)
    second = await _upload(async_db, day)
    third = await _upload(async_db, day)
    assert third.filename == "2026-05-15_photo-3.jpg"

    await _delete(async_db, second.id)

    fourth = await _upload(async_db, day)
    assert fourth.filename == "2026-05-15_photo-4.jpg"


async def test_gaps_in_numbering_are_preserved(async_db: AsyncSession, real_storage: None) -> None:
    """Deleted numbers must stay retired forever -- the next upload always
    picks max(existing)+1, never fills holes."""
    day = datetime.date(2026, 5, 15)
    await _make_entry(async_db, day)

    p1 = await _upload(async_db, day)
    await _upload(async_db, day)
    p3 = await _upload(async_db, day)
    await _upload(async_db, day)
    await _upload(async_db, day)  # photo-5

    await _delete(async_db, p1.id)
    await _delete(async_db, p3.id)

    # Three uploads in a row -- they must be 6, 7, 8 (not 1, 3, 6).
    sixth = await _upload(async_db, day)
    seventh = await _upload(async_db, day)
    eighth = await _upload(async_db, day)

    assert sixth.filename == "2026-05-15_photo-6.jpg"
    assert seventh.filename == "2026-05-15_photo-7.jpg"
    assert eighth.filename == "2026-05-15_photo-8.jpg"


async def test_numbering_is_per_date(async_db: AsyncSession, real_storage: None) -> None:
    """Sanity check: each date has its own independent numbering sequence."""
    day_a = datetime.date(2026, 5, 15)
    day_b = datetime.date(2026, 5, 16)
    await _make_entry(async_db, day_a)
    await _make_entry(async_db, day_b)

    await _upload(async_db, day_a)
    await _upload(async_db, day_a)
    first_b = await _upload(async_db, day_b)

    assert first_b.filename == "2026-05-16_photo-1.jpg"


# ---------------------------------------------------------------------------
# Defense-in-depth: save_photo must refuse to overwrite
# ---------------------------------------------------------------------------


def test_save_photo_raises_if_target_exists(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If a future bug ever passes a colliding filename to save_photo, we
    want a loud failure rather than silent data loss."""
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))

    filename = "2026-05-15_photo-1.jpg"
    # Pre-create the target file with known contents.
    target = photo_dir / filename
    target.write_bytes(b"original-content")

    with pytest.raises(FileExistsError):
        save_photo(b"new-content", filename, vault_path="")

    # Original file is untouched -- proves no overwrite happened.
    assert target.read_bytes() == b"original-content"


def test_save_photo_writes_when_target_does_not_exist(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy-path sanity check for the guard: a fresh filename still works."""
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))

    save_photo(b"hello", "fresh.jpg", vault_path="")

    assert (photo_dir / "fresh.jpg").read_bytes() == b"hello"
