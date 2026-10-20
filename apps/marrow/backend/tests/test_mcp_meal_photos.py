"""MCP meal photos: decode, resize, dedupe, copy, attach, commit-failure cleanup.

Uses a temp photo dir and Pillow-made images only. HEIC bytes come from the
existing upload fixture.
"""

from __future__ import annotations

import base64
import datetime
import io
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from mcp.server.fastmcp import FastMCP
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mcp import tools as t_mod
from app.mcp.meal_photos import photo_hash_tag
from app.mcp.resources.meal_guide import MEAL_PHOTO_RECIPE
from app.models.entry import Entry
from app.models.meal import Meal
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.models.user import User
from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
from app.services.meal_tags import MealTagService
from app.services.photo_storage import read_photo, thumb_filename
from app.services.photos import PhotoService
from f0rge_core.exceptions import NotFoundError, ValidationError
from tests.test_mcp_surface import _mock_main_session, _mock_ro_session, _tool_fn
from tests.test_photos_heic_upload import _heic_bytes


@pytest_asyncio.fixture
async def photo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Real local storage. Bucket settings cleared so nothing leaves the tmp dir."""
    directory = tmp_path / "photos"
    directory.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(directory))
    monkeypatch.setattr(settings, "bucket_name", "")
    monkeypatch.setattr(settings, "aws_access_key_id", "")
    monkeypatch.setattr(settings, "aws_secret_access_key", "")
    monkeypatch.setattr(settings, "aws_endpoint_url_s3", "")
    monkeypatch.setattr(settings, "food_analysis_enabled", False)
    # CI and laptops must not inherit a Railway env and trip the shared-bucket guard.
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    return directory


def _jpeg(width: int, height: int, color: str = "blue") -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _server() -> FastMCP:
    server = FastMCP("test")
    t_mod.register_tools(server)
    return server


async def _log(async_db: AsyncSession, **kwargs: object) -> dict:
    with _mock_main_session(async_db):
        return await _tool_fn(_server(), "log_meal")(**kwargs)


async def _attach(async_db: AsyncSession, **kwargs: object) -> dict:
    with _mock_main_session(async_db):
        return await _tool_fn(_server(), "attach_meal_photo")(**kwargs)


async def _photo_count(async_db: AsyncSession, label: str) -> int:
    count = await async_db.scalar(
        select(func.count()).select_from(Photo).where(Photo.label == label)
    )
    return int(count or 0)


def _size(path: Path) -> tuple[str | None, tuple[int, int]]:
    with Image.open(path) as img:
        return img.format, img.size


def test_meal_photo_recipe_is_in_the_guide() -> None:
    assert "attach_meal_photo" in MEAL_PHOTO_RECIPE
    assert 'photo_base64="$file:/workspace/tmp/meal-<sha>.b64"' in MEAL_PHOTO_RECIPE
    assert "source_photo_id=790" in MEAL_PHOTO_RECIPE
    assert "{{" not in MEAL_PHOTO_RECIPE


async def test_jpeg_b64_stores_full_and_thumb(async_db: AsyncSession, photo_dir: Path) -> None:
    raw = _jpeg(2400, 1600, "navy")
    logged = await _log(
        async_db,
        date="2026-07-01",
        name="jpeg bowl",
        photo_base64=_b64(raw),
    )
    assert logged["has_photo"] is True
    assert logged["deduplicated"] is False
    assert logged["photo_sha256"] == photo_hash_tag(raw)

    photo = (
        await async_db.execute(select(Photo).where(Photo.id == logged["photo_id"]))
    ).scalar_one()
    meal = (await async_db.execute(select(Meal).where(Meal.id == logged["meal_id"]))).scalar_one()
    assert photo.filename is not None
    assert photo.filename == meal.filename
    assert photo.original_filename == meal.original_filename == logged["photo_sha256"]

    full_fmt, full_size = _size(photo_dir / photo.filename)
    thumb_fmt, thumb_size = _size(photo_dir / thumb_filename(photo.filename))
    assert full_fmt == "JPEG" and thumb_fmt == "JPEG"
    assert max(full_size) == 2048
    assert max(thumb_size) == 480

    with _mock_ro_session(async_db):
        meal_view = await _tool_fn(_server(), "get_meal")(photo_id=photo.id)
    assert meal_view is not None
    assert meal_view["photo_sha256"] == logged["photo_sha256"]
    assert meal_view["photo_created_at"]


async def test_heic_becomes_jpeg(async_db: AsyncSession, photo_dir: Path) -> None:
    logged = await _log(
        async_db,
        date="2026-07-02",
        name="heic bowl",
        photo_base64=_b64(_heic_bytes()),
    )
    photo = (
        await async_db.execute(select(Photo).where(Photo.id == logged["photo_id"]))
    ).scalar_one()
    assert photo.filename is not None
    fmt, _size_px = _size(photo_dir / photo.filename)
    assert fmt == "JPEG"
    assert logged["has_photo"] is True


async def test_data_url_newlines_ok_garbage_and_oversize_create_nothing(
    async_db: AsyncSession, photo_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _jpeg(32, 24, "green")
    encoded = _b64(raw)
    wrapped = "data:image/jpeg;base64," + "\n".join(
        encoded[i : i + 40] for i in range(0, len(encoded), 40)
    )
    logged = await _log(
        async_db,
        date="2026-07-03",
        name="wrapped bowl",
        photo_base64=wrapped,
    )
    assert logged["has_photo"] is True
    assert logged["photo_sha256"] == photo_hash_tag(raw)
    assert await _photo_count(async_db, "wrapped bowl") == 1

    with pytest.raises(ValidationError, match="unsupported image"):
        await _log(
            async_db,
            date="2026-07-03",
            name="garbage bowl",
            photo_base64=_b64(b"this is not an image, not even close"),
        )
    with pytest.raises(ValidationError, match="invalid base64"):
        await _log(
            async_db,
            date="2026-07-03",
            name="garbage bowl",
            photo_base64="!!!!",
        )
    monkeypatch.setattr("app.mcp.meal_photos.MAX_PHOTO_BYTES", 8)
    with pytest.raises(ValidationError, match="exceeds"):
        await _log(
            async_db,
            date="2026-07-03",
            name="huge bowl",
            photo_base64=_b64(raw),
        )
    with pytest.raises(ValidationError, match="not both"):
        await _log(
            async_db,
            date="2026-07-03",
            name="both bowl",
            photo_base64=_b64(raw),
            source_photo_id=1,
        )
    assert await _photo_count(async_db, "garbage bowl") == 0
    assert await _photo_count(async_db, "huge bowl") == 0
    assert await _photo_count(async_db, "both bowl") == 0


async def test_same_day_retry_dedupes_unless_allowed(
    async_db: AsyncSession, photo_dir: Path
) -> None:
    payload = _b64(_jpeg(40, 40, "red"))
    first = await _log(
        async_db,
        date="2026-07-04",
        name="dedupe bowl",
        ingredients=["oats"],
        photo_base64=payload,
    )
    second = await _log(
        async_db,
        date="2026-07-04",
        name="dedupe bowl again",
        ingredients=["rice"],
        photo_base64=payload,
    )
    assert second["deduplicated"] is True
    assert second["photo_id"] == first["photo_id"]
    assert second["photo_sha256"] == first["photo_sha256"]
    assert await _photo_count(async_db, "dedupe bowl") == 1
    assert await _photo_count(async_db, "dedupe bowl again") == 0

    third = await _log(
        async_db,
        date="2026-07-04",
        name="dedupe bowl copy",
        photo_base64=payload,
        allow_duplicate=True,
    )
    assert third["deduplicated"] is False
    assert third["photo_id"] != first["photo_id"]
    assert await _photo_count(async_db, "dedupe bowl copy") == 1
    first_row = (
        await async_db.execute(select(Photo).where(Photo.id == first["photo_id"]))
    ).scalar_one()
    third_row = (
        await async_db.execute(select(Photo).where(Photo.id == third["photo_id"]))
    ).scalar_one()
    assert first_row.filename != third_row.filename
    assert (photo_dir / first_row.filename).is_file()
    assert (photo_dir / third_row.filename).is_file()


async def test_source_photo_id_copies_bytes_and_survives_source_delete(
    async_db: AsyncSession, photo_dir: Path
) -> None:
    original = _jpeg(48, 48, "purple")
    source = await _log(
        async_db,
        date="2026-07-05",
        name="source bowl",
        ingredients=["oats"],
        photo_base64=_b64(original),
    )
    copied = await _log(
        async_db,
        date="2026-07-06",
        name="copied bowl",
        ingredients=["rice"],
        source_photo_id=source["photo_id"],
    )
    assert copied["deduplicated"] is False
    assert copied["photo_id"] != source["photo_id"]
    assert copied["has_photo"] is True

    src = (await async_db.execute(select(Photo).where(Photo.id == source["photo_id"]))).scalar_one()
    dst = (await async_db.execute(select(Photo).where(Photo.id == copied["photo_id"]))).scalar_one()
    assert src.filename is not None and dst.filename is not None
    assert src.filename != dst.filename
    src_path = photo_dir / src.filename
    dst_path = photo_dir / dst.filename
    assert src_path.is_file() and dst_path.is_file()
    assert src_path.resolve() != dst_path.resolve()
    dst_bytes = read_photo(dst.filename, user_id=str(dst.user_id))
    # Own file, not a shared filename. A second JPEG encode of a flat swatch
    # can match the source bytes; deleting the source is what proves the copy.
    assert dst_bytes[:2] == b"\xff\xd8"

    # Ingredients come from the call, not a clone of the source meal.
    assert [item["name"] for item in copied["ingredients"]] == ["rice"]
    stored_names = (
        (
            await async_db.execute(
                select(PhotoIngredient.name)
                .join(PhotoAnalysis, PhotoIngredient.analysis_id == PhotoAnalysis.id)
                .where(PhotoAnalysis.meal_id == dst.meal_id)
            )
        )
        .scalars()
        .all()
    )
    assert list(stored_names) == ["rice"]

    await PhotoService(async_db, FoodAnalysisOrchestrator(), MealTagService(async_db)).delete(
        source["photo_id"]
    )
    assert read_photo(dst.filename, user_id=str(dst.user_id)) == dst_bytes
    with pytest.raises(FileNotFoundError):
        read_photo(src.filename, user_id=str(src.user_id))


async def test_attach_meal_photo_replace_self_and_other_user(
    async_db: AsyncSession, photo_dir: Path
) -> None:
    bare = await _log(async_db, date="2026-07-07", name="bare bowl")
    assert bare["has_photo"] is False
    assert bare["photo_sha256"] is None

    first_bytes = _jpeg(80, 60, "orange")
    attached = await _attach(async_db, photo_id=bare["photo_id"], photo_base64=_b64(first_bytes))
    assert attached["has_photo"] is True
    assert attached["replaced"] is False
    assert attached["photo_sha256"] == photo_hash_tag(first_bytes)
    assert attached["meal_id"] == bare["meal_id"]

    row = (await async_db.execute(select(Photo).where(Photo.id == bare["photo_id"]))).scalar_one()
    meal = (await async_db.execute(select(Meal).where(Meal.id == bare["meal_id"]))).scalar_one()
    assert row.filename is not None
    assert row.filename == meal.filename
    old_name = row.filename
    assert (photo_dir / old_name).is_file()
    assert (photo_dir / thumb_filename(old_name)).is_file()

    same = await _attach(async_db, photo_id=bare["photo_id"], photo_base64=_b64(first_bytes))
    assert same["replaced"] is False
    assert same["photo_sha256"] == attached["photo_sha256"]
    again = (await async_db.execute(select(Photo).where(Photo.id == bare["photo_id"]))).scalar_one()
    assert again.filename == old_name

    with pytest.raises(ValidationError, match="replace"):
        await _attach(
            async_db,
            photo_id=bare["photo_id"],
            photo_base64=_b64(_jpeg(70, 50, "yellow")),
        )
    assert (photo_dir / old_name).is_file()

    replaced = await _attach(
        async_db,
        photo_id=bare["photo_id"],
        photo_base64=_b64(_jpeg(90, 40, "yellow")),
        replace=True,
    )
    assert replaced["replaced"] is True
    refreshed = (
        await async_db.execute(select(Photo).where(Photo.id == bare["photo_id"]))
    ).scalar_one()
    assert refreshed.filename is not None
    assert refreshed.filename != old_name
    assert not (photo_dir / old_name).exists()
    assert not (photo_dir / thumb_filename(old_name)).exists()
    assert (photo_dir / refreshed.filename).is_file()
    assert (photo_dir / thumb_filename(refreshed.filename)).is_file()

    with pytest.raises(ValidationError, match="different photo"):
        await _attach(
            async_db,
            photo_id=bare["photo_id"],
            source_photo_id=bare["photo_id"],
        )

    other = User(
        email=f"mealphoto-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        handle=f"mp_{uuid.uuid4().hex[:8]}",
        avatar_default_index=0,
    )
    async_db.add(other)
    await async_db.flush()
    entry = Entry(
        user_id=other.id,
        date=datetime.date(2026, 7, 8),
        bloating=0,
        joint_pain=0,
        neuro=0,
        diet_risk="",
        supplements="",
        sick=False,
        hot_shower=False,
    )
    async_db.add(entry)
    await async_db.flush()
    other_meal = Meal(
        owner_user_id=other.id,
        label="theirs",
        created_at=datetime.datetime.utcnow(),
    )
    async_db.add(other_meal)
    await async_db.flush()
    other_photo = Photo(
        user_id=other.id,
        entry_id=entry.id,
        meal_id=other_meal.id,
        label="theirs",
        created_at=datetime.datetime.utcnow(),
    )
    async_db.add(other_photo)
    await async_db.flush()

    with pytest.raises(NotFoundError):
        await _attach(
            async_db,
            photo_id=other_photo.id,
            photo_base64=_b64(_jpeg(16, 16, "black")),
        )
    with pytest.raises(NotFoundError):
        await _attach(
            async_db,
            photo_id=bare["photo_id"],
            source_photo_id=other_photo.id,
            replace=True,
        )


async def test_commit_failure_leaves_no_orphan_files(
    async_db: AsyncSession, photo_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom() -> None:
        raise RuntimeError("forced commit failure")

    monkeypatch.setattr(async_db, "commit", _boom)
    with pytest.raises(RuntimeError, match="forced commit failure"):
        await _log(
            async_db,
            date="2026-07-09",
            name="orphan bowl",
            photo_base64=_b64(_jpeg(64, 64, "teal")),
        )
    leftovers = [path for path in photo_dir.rglob("*") if path.is_file()]
    assert leftovers == []
    assert await _photo_count(async_db, "orphan bowl") == 0


@pytest.mark.usefixtures("memory_redis")
async def test_mcp_photo_shows_on_cached_day_and_log_again_thumb(
    async_db: AsyncSession, photo_dir: Path, memory_redis: dict
) -> None:
    """Check-in reads the Redis day. MCP must drop that cache and leave a thumb the API can serve.

    ``times_logged`` is distinct calendar days for the dish name, so a second
    photo of the same dish on the same day does not increment it.
    """
    from app.cache.keys import entry_key
    from app.services.entries import EntryService, get_or_create_entry
    from app.services.meals import MealService
    from f0rge_db.tenant import current_user_id

    day = datetime.date(2026, 7, 11)
    await get_or_create_entry(async_db, day)
    svc = EntryService(async_db)
    before = await svc.get_entry(day)
    assert before.photos == []
    cache_key = entry_key(current_user_id(), day)
    assert cache_key in memory_redis["store"]

    logged = await _log(
        async_db,
        date=day.isoformat(),
        name="cache bowl",
        photo_base64=_b64(_jpeg(64, 48, "navy")),
    )
    assert logged["has_photo"] is True
    assert logged["deduplicated"] is False
    assert cache_key not in memory_redis["store"]

    async_db.expire_all()
    after = await svc.get_entry(day)
    photo = next(item for item in after.photos if item.id == logged["photo_id"])
    assert photo.has_image is True
    assert photo.filename

    recent = await MealService(async_db).list_recent()
    hit = next(item for item in recent if item.dish_name == "cache bowl")
    assert hit.has_image is True
    assert hit.source_photo_id == logged["photo_id"]
    assert hit.times_logged == 1
    assert hit.last_logged == day

    same_day = await _log(
        async_db,
        date=day.isoformat(),
        name="cache bowl",
        photo_base64=_b64(_jpeg(32, 32, "teal")),
        allow_duplicate=True,
    )
    assert same_day["photo_id"] != logged["photo_id"]
    again = await MealService(async_db).list_recent()
    still = next(item for item in again if item.dish_name == "cache bowl")
    assert still.times_logged == 1
    assert still.has_image is True

    thumb = await PhotoService(
        async_db, FoodAnalysisOrchestrator(), MealTagService(async_db)
    ).serve_photo_thumb(logged["photo_id"])
    assert thumb.body[:2] == b"\xff\xd8"

    other_day = datetime.date(2026, 7, 12)
    await _log(
        async_db,
        date=other_day.isoformat(),
        name="cache bowl",
        photo_base64=_b64(_jpeg(40, 40, "olive")),
    )
    spanned = await MealService(async_db).list_recent()
    counted = next(item for item in spanned if item.dish_name == "cache bowl")
    assert counted.times_logged == 2
    assert counted.last_logged == other_day


@pytest.mark.usefixtures("memory_redis")
async def test_attach_meal_photo_busts_entry_cache(
    async_db: AsyncSession, photo_dir: Path, memory_redis: dict
) -> None:
    from app.cache.keys import entry_key
    from app.services.entries import EntryService
    from f0rge_db.tenant import current_user_id

    day = datetime.date(2026, 7, 13)
    bare = await _log(async_db, date=day.isoformat(), name="attach bowl")
    assert bare["has_photo"] is False

    svc = EntryService(async_db)
    cached = await svc.get_entry(day)
    assert cached.photos[0].has_image is False
    cache_key = entry_key(current_user_id(), day)
    assert cache_key in memory_redis["store"]

    attached = await _attach(
        async_db,
        photo_id=bare["photo_id"],
        photo_base64=_b64(_jpeg(48, 36, "orange")),
    )
    assert attached["has_photo"] is True
    assert cache_key not in memory_redis["store"]

    async_db.expire_all()
    refreshed = await svc.get_entry(day)
    photo = next(item for item in refreshed.photos if item.id == bare["photo_id"])
    assert photo.has_image is True

    thumb = await PhotoService(
        async_db, FoodAnalysisOrchestrator(), MealTagService(async_db)
    ).serve_photo_thumb(bare["photo_id"])
    assert thumb.body[:2] == b"\xff\xd8"


async def test_railway_without_bucket_does_not_store_a_local_only_photo(
    async_db: AsyncSession, photo_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    with pytest.raises(ValidationError, match="shared photo bucket"):
        await _log(
            async_db,
            date="2026-07-14",
            name="unservable bowl",
            photo_base64=_b64(_jpeg(24, 24, "black")),
        )
    assert await _photo_count(async_db, "unservable bowl") == 0
    assert [path for path in photo_dir.rglob("*") if path.is_file()] == []
