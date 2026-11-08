"""Read-only scan of photo rows whose objects are missing from storage."""

from __future__ import annotations

import datetime
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.meal import Meal
from app.models.photo import Photo
from app.services.entries import get_or_create_entry
from app.services.photo_storage import save_photo, thumb_filename
from f0rge_db.tenant import current_user_id
from scripts.scan_missing_photos import (
    HEADER,
    format_missing_photo,
    missing_photo_rows,
)


@pytest.fixture
def photo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "photos"
    directory.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(directory))
    monkeypatch.setattr(settings, "bucket_name", "")
    monkeypatch.setattr(settings, "aws_access_key_id", "")
    monkeypatch.setattr(settings, "aws_secret_access_key", "")
    monkeypatch.setattr(settings, "aws_endpoint_url_s3", "")
    return directory


def test_scan_module_does_not_reference_writers() -> None:
    source = Path(missing_photo_rows.__code__.co_filename).read_text()
    for banned in (
        "save_photo",
        "delete_photo",
        "save_bytes",
        "delete_relative",
        "INSERT ",
        "UPDATE ",
        "DELETE ",
    ):
        assert banned not in source


async def test_scan_lists_missing_image_and_thumb_only(
    async_db: AsyncSession, photo_dir: Path
) -> None:
    user_id = current_user_id()
    uid = str(user_id)
    day = datetime.date(2026, 10, 20)
    entry = await get_or_create_entry(async_db, day)
    now = datetime.datetime.utcnow()

    present_meal = Meal(
        owner_user_id=user_id,
        label="present bowl",
        filename="present.jpg",
        created_at=now,
    )
    missing_meal = Meal(
        owner_user_id=user_id,
        label="missing bowl",
        filename="missing.jpg",
        created_at=now,
    )
    thumb_meal = Meal(
        owner_user_id=user_id,
        label="thumb bowl",
        filename="thumbonly.jpg",
        created_at=now,
    )
    library_meal = Meal(
        owner_user_id=user_id,
        label="library bowl",
        filename=None,
        icon_key="salad",
        created_at=now,
    )
    async_db.add_all([present_meal, missing_meal, thumb_meal, library_meal])
    await async_db.flush()

    def _photo(meal: Meal, filename: str | None) -> Photo:
        return Photo(
            user_id=user_id,
            entry_id=entry.id,
            meal_id=meal.id,
            filename=filename,
            label=meal.label,
            created_at=now,
        )

    present = _photo(present_meal, "present.jpg")
    missing = _photo(missing_meal, "missing.jpg")
    thumb_only = _photo(thumb_meal, "thumbonly.jpg")
    library = _photo(library_meal, None)
    async_db.add_all([present, missing, thumb_only, library])
    await async_db.flush()

    save_photo(b"full-present", "present.jpg", user_id=uid)
    save_photo(b"thumb-present", thumb_filename("present.jpg"), user_id=uid)
    save_photo(b"full-thumbonly", "thumbonly.jpg", user_id=uid)

    before_files = sorted(path.name for path in photo_dir.iterdir())
    photo_count = await async_db.scalar(select(func.count()).select_from(Photo))

    found = await missing_photo_rows(async_db)

    assert await async_db.scalar(select(func.count()).select_from(Photo)) == photo_count
    assert sorted(path.name for path in photo_dir.iterdir()) == before_files

    by_id = {row.photo_id: row for row in found}
    assert present.id not in by_id
    assert library.id not in by_id
    assert by_id[missing.id].missing == "image,thumbnail"
    assert by_id[thumb_only.id].missing == "thumbnail"
    assert by_id[missing.id].meal_id == missing_meal.id
    assert by_id[missing.id].meal_name == "missing bowl"
    assert by_id[missing.id].entry_date == day
    assert by_id[missing.id].user_id == user_id

    line = format_missing_photo(by_id[missing.id])
    assert line.startswith(f"{missing.id}\t{missing_meal.id}\tmissing bowl\t2026-10-20\t")
    assert line.endswith("\timage,thumbnail")
    assert HEADER.split("\t") == [
        "photo_id",
        "meal_id",
        "meal_name",
        "date",
        "user_id",
        "missing",
    ]


async def test_scan_reports_a_filename_with_no_object(
    async_db: AsyncSession, photo_dir: Path
) -> None:
    """A row that points at storage, with nothing on disk, is the production case."""
    user_id = current_user_id()
    entry = await get_or_create_entry(async_db, datetime.date(2026, 10, 21))
    now = datetime.datetime.utcnow()
    meal = Meal(
        owner_user_id=user_id,
        label="gone bowl",
        filename="gone.jpg",
        created_at=now,
    )
    async_db.add(meal)
    await async_db.flush()
    photo = Photo(
        user_id=user_id,
        entry_id=entry.id,
        meal_id=meal.id,
        filename="gone.jpg",
        label="gone bowl",
        created_at=now,
    )
    async_db.add(photo)
    await async_db.flush()

    found = await missing_photo_rows(async_db)
    row = next(item for item in found if item.photo_id == photo.id)
    assert row.missing == "image,thumbnail"
    assert row.user_id == uuid.UUID(str(user_id))
    assert not (photo_dir / "gone.jpg").exists()
