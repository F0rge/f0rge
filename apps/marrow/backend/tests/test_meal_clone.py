"""Tests for the "Log Again" meal-clone feature (MealService + meals router).

Exercises the real seams end-to-end: a temporary on-disk photo dir, the real
``save_photo``/``delete_photo`` collaborators, and a real PIN-login round-trip
for the HTTP endpoints. Nothing under test is mocked — the only monkeypatch at a
trust boundary is the OpenRouter vision client, and only to *prove it is never
constructed* during a clone (per feedback_no_mocks_at_seam_under_test.md).
"""

from __future__ import annotations

import datetime
import io
import os
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from f0rge_core.exceptions import NotFoundError, ValidationError
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.models.user import LEO_PLACEHOLDER_PASSWORD_HASH, User
from app.services.diet_flags import compute_photo_signal
from app.services.meals import MealService
from app.services.photo_storage import delete_photo, save_photo
from f0rge_db.tenant import apply_session_user_id
from tests.conftest import authed_user_id


@pytest_asyncio.fixture
async def storage(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Redirect photo_dir to tmp dir. Does NOT mock storage seams."""
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    return tmp_path


# ---------------------------------------------------------------------------
# Seeding helpers (inline ORM construction, no factory)
# ---------------------------------------------------------------------------


def _jpg_bytes(color: str = "blue") -> bytes:
    img = Image.new("RGB", (12, 12), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _ensure_entry(
    db: AsyncSession,
    day: datetime.date,
    *,
    user_id: uuid.UUID | None = None,
    diet_risk: str = "",
    overall: int = 0,
) -> Entry:
    uid = user_id or uuid.UUID(settings.default_storage_user_id)
    existing = (
        await db.execute(select(Entry).where(Entry.user_id == uid, Entry.date == day))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    entry = Entry(
        user_id=uid,
        date=day,
        overall=overall,
        bloating=0,
        stool_normal=True,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk=diet_risk,
        supplements="",
        sick=False,
        hot_shower=False,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def _add_meal(
    db: AsyncSession,
    entry: Entry,
    filename: str,
    *,
    dish_name: str | None = "Spinach omelette",
    status: str = "confirmed",
    gluten: bool = False,
    histamine: int | None = 3,
    write_file: bool = True,
    color: str = "blue",
) -> Photo:
    """Create a Photo + PhotoAnalysis + one PhotoIngredient, writing the file to disk."""
    if write_file:
        save_photo(_jpg_bytes(color), filename, user_id=str(entry.user_id))
    photo = Photo(
        user_id=entry.user_id,
        entry_id=entry.id,
        filename=filename,
        label="Lunch",
        original_filename="source.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    await db.flush()
    analysis = PhotoAnalysis(
        user_id=entry.user_id,
        photo_id=photo.id,
        status=status,
        dish_name=dish_name,
        cuisine="Mediterranean",
        dish_confidence=0.91,
        model_id="test/model",
        raw_response="{}",
    )
    db.add(analysis)
    await db.flush()
    db.add(
        PhotoIngredient(
            user_id=entry.user_id,
            analysis_id=analysis.id,
            name="Feta",
            canonical_name="feta cheese",
            visible=True,
            confidence=0.88,
            user_edited=False,
            histamine_score=histamine,
            fodmap_oligos=None,
            fodmap_fructose=None,
            fodmap_polyols=None,
            fodmap_lactose="high",
            contains_gluten=gluten,
            contains_dairy=True,
        )
    )
    await db.commit()
    await db.refresh(photo)
    return photo


async def _get_entry(db: AsyncSession, day: datetime.date) -> Entry | None:
    # populate_existing reloads the entry + its relationship chain fresh (so the
    # diet signal reflects committed clones) WITHOUT expire_all(), which would
    # expire unrelated objects like src/cloned and trip MissingGreenlet when a
    # test reads their attributes synchronously afterward.
    stmt = (
        select(Entry)
        .where(Entry.date == day)
        .options(
            selectinload(Entry.photos)
            .selectinload(Photo.analysis)
            .selectinload(PhotoAnalysis.ingredients)
        )
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _analysis_for(db: AsyncSession, photo_id: int) -> PhotoAnalysis:
    return (
        await db.execute(select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id))
    ).scalar_one()


SRC_DAY = datetime.date(2026, 6, 1)
TARGET_DAY = datetime.date(2026, 6, 10)


# ---------------------------------------------------------------------------
# clone() — shape & data
# ---------------------------------------------------------------------------


async def test_clone_returns_photo_on_target_day(async_db: AsyncSession, storage) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")

    cloned = await MealService(async_db).clone(TARGET_DAY, src.id)

    target = await _get_entry(async_db, TARGET_DAY)
    assert target is not None
    assert cloned.entry_id == target.id
    assert cloned.id != src.id


async def test_clone_shared_meal_copy_uses_recipient_placement(
    async_db: AsyncSession, storage
) -> None:
    """Tagged meal copies share meal_id; analysis.photo_id still points at tagger row."""
    tagger = User(
        email=f"tagger_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=LEO_PLACEHOLDER_PASSWORD_HASH,
        handle=f"t_{uuid.uuid4().hex[:8]}",
    )
    recipient = User(
        email=f"recipient_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=LEO_PLACEHOLDER_PASSWORD_HASH,
        handle=f"r_{uuid.uuid4().hex[:8]}",
    )
    async_db.add_all([tagger, recipient])
    await async_db.flush()
    tagger_id = tagger.id
    recipient_id = recipient.id
    tagger_entry = await _ensure_entry(async_db, SRC_DAY, user_id=tagger_id)
    recipient_entry = await _ensure_entry(async_db, SRC_DAY, user_id=recipient_id)
    tagger_photo = await _add_meal(async_db, tagger_entry, f"{SRC_DAY}_tagger.jpg")

    copy_filename = f"{SRC_DAY}_recipient-copy.jpg"
    save_photo(_jpg_bytes("green"), copy_filename, user_id=str(recipient_id))
    copy_photo = Photo(
        user_id=recipient_id,
        entry_id=recipient_entry.id,
        meal_id=tagger_photo.meal_id,
        filename=copy_filename,
        label=tagger_photo.label,
        original_filename="copy.jpg",
        source_photo_id=tagger_photo.id,
        tagged_by_user_id=tagger_id,
    )
    async_db.add(copy_photo)
    await async_db.commit()
    await async_db.refresh(copy_photo)

    await apply_session_user_id(async_db, recipient_id)
    cloned = await MealService(async_db).clone(TARGET_DAY, copy_photo.id)

    # clone returns a PhotoResponse (no user_id); assert ownership on the row.
    cloned_row = await async_db.get(Photo, cloned.id)
    assert cloned_row is not None and cloned_row.user_id == recipient_id
    assert cloned.id != copy_photo.id
    assert cloned.meal_id != copy_photo.meal_id


async def test_clone_analysis_confirmed_and_metadata_copied(
    async_db: AsyncSession, storage
) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg", dish_name="Grilled salmon")

    cloned = await MealService(async_db).clone(TARGET_DAY, src.id)

    src_analysis = await _analysis_for(async_db, src.id)
    cloned_analysis = await _analysis_for(async_db, cloned.id)
    assert cloned_analysis.status == "confirmed"
    assert cloned_analysis.dish_name == "Grilled salmon"
    assert cloned_analysis.cuisine == src_analysis.cuisine
    assert cloned_analysis.dish_confidence == src_analysis.dish_confidence
    assert cloned_analysis.id != src_analysis.id


async def test_clone_ingredients_copied_verbatim_as_new_rows(
    async_db: AsyncSession, storage
) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg", gluten=True, histamine=2)

    cloned = await MealService(async_db).clone(TARGET_DAY, src.id)

    src_analysis = await _analysis_for(async_db, src.id)
    cloned_analysis = await _analysis_for(async_db, cloned.id)
    src_ings = list(src_analysis.ingredients)
    new_ings = list(cloned_analysis.ingredients)
    assert len(new_ings) == len(src_ings) == 1
    a, b = src_ings[0], new_ings[0]
    assert b.id != a.id
    assert b.analysis_id == cloned_analysis.id
    for field in (
        "name",
        "canonical_name",
        "visible",
        "confidence",
        "user_edited",
        "histamine_score",
        "fodmap_oligos",
        "fodmap_fructose",
        "fodmap_polyols",
        "fodmap_lactose",
        "contains_gluten",
        "contains_dairy",
    ):
        assert getattr(b, field) == getattr(a, field), field


async def test_clone_meal_time_defaults_to_now(async_db: AsyncSession, storage) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")

    before = datetime.datetime.utcnow()
    cloned = await MealService(async_db).clone(TARGET_DAY, src.id)
    after = datetime.datetime.utcnow()

    assert cloned.meal_time is not None
    assert (
        before - datetime.timedelta(seconds=5)
        <= cloned.meal_time
        <= after + datetime.timedelta(seconds=5)
    )


# ---------------------------------------------------------------------------
# clone() — filesystem (copy-not-share)
# ---------------------------------------------------------------------------


async def test_clone_copies_file_to_new_name_source_untouched(
    async_db: AsyncSession, storage
) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")
    src_path = os.path.join(str(storage / "photos"), src.filename)
    src_bytes_before = open(src_path, "rb").read()

    cloned = await MealService(async_db).clone(TARGET_DAY, src.id)

    clone_path = os.path.join(str(storage / "photos"), cloned.filename)
    assert cloned.filename != src.filename
    assert os.path.exists(clone_path)
    # source file present and byte-identical
    assert open(src_path, "rb").read() == src_bytes_before


async def test_deleting_clone_file_leaves_source(async_db: AsyncSession, storage) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")
    src_path = os.path.join(str(storage / "photos"), src.filename)

    cloned = await MealService(async_db).clone(TARGET_DAY, src.id)
    clone_path = os.path.join(str(storage / "photos"), cloned.filename)

    # Deleting the clone's file (distinct filename) must not touch the source's.
    delete_photo(cloned.filename)
    assert not os.path.exists(clone_path)
    assert os.path.exists(src_path)


# ---------------------------------------------------------------------------
# clone() — target entry & diet signal
# ---------------------------------------------------------------------------


async def test_clone_creates_target_entry_when_absent(async_db: AsyncSession, storage) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")
    assert await _get_entry(async_db, TARGET_DAY) is None

    await MealService(async_db).clone(TARGET_DAY, src.id)

    target = await _get_entry(async_db, TARGET_DAY)
    assert target is not None
    # Unrated skeleton — core scales stay NULL until the user taps a level.
    assert target.overall is None
    assert target.sleep_quality is None
    assert target.stress is None
    assert target.diet_risk == ""


async def test_clone_reuses_existing_entry_without_overwriting(
    async_db: AsyncSession, storage
) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")
    await _ensure_entry(async_db, TARGET_DAY, diet_risk="high-histamine", overall=3)

    await MealService(async_db).clone(TARGET_DAY, src.id)

    rows = (await async_db.execute(select(Entry).where(Entry.date == TARGET_DAY))).scalars().all()
    assert len(rows) == 1
    assert rows[0].overall == 3
    assert rows[0].diet_risk == "high-histamine"


async def test_clone_flags_surface_in_target_signal(async_db: AsyncSession, storage) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(
        async_db, src_entry, f"{SRC_DAY}_photo-1.jpg", gluten=True, histamine=None
    )

    await MealService(async_db).clone(TARGET_DAY, src.id)

    target = await _get_entry(async_db, TARGET_DAY)
    signal = compute_photo_signal(target)
    assert "gluten" in signal.flags


async def test_clone_does_not_copy_source_entry_diet_risk(async_db: AsyncSession, storage) -> None:
    # Source *day* has a manual diet_risk CSV; cloning the meal must not carry it.
    src_entry = await _ensure_entry(async_db, SRC_DAY, diet_risk="high-histamine")
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")

    await MealService(async_db).clone(TARGET_DAY, src.id)

    target = await _get_entry(async_db, TARGET_DAY)
    assert target.diet_risk == ""


# ---------------------------------------------------------------------------
# clone() — errors
# ---------------------------------------------------------------------------


async def test_clone_missing_source_raises_not_found(async_db: AsyncSession, storage) -> None:
    with pytest.raises(NotFoundError):
        await MealService(async_db).clone(TARGET_DAY, 999999)


async def test_clone_unconfirmed_source_raises_validation(async_db: AsyncSession, storage) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg", status="complete")
    with pytest.raises(ValidationError):
        await MealService(async_db).clone(TARGET_DAY, src.id)


async def test_clone_source_file_missing_raises_not_found(async_db: AsyncSession, storage) -> None:
    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg", write_file=False)
    with pytest.raises(NotFoundError):
        await MealService(async_db).clone(TARGET_DAY, src.id)


async def test_clone_never_invokes_vision_client(
    async_db: AsyncSession, storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Even with analysis "enabled", clone must never construct or call the LLM client.
    monkeypatch.setattr(settings, "food_analysis_enabled", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")

    class _SpyLLM:
        constructed = False

        def __init__(self, *args, **kwargs) -> None:
            _SpyLLM.constructed = True

        async def complete_with_image(self, *args, **kwargs):
            raise AssertionError("vision API must not be called during clone")

        async def complete(self, *args, **kwargs):
            raise AssertionError("vision API must not be called during clone")

    monkeypatch.setattr("app.services.llm.openrouter.OpenRouterClient", _SpyLLM)

    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")
    await MealService(async_db).clone(TARGET_DAY, src.id)

    assert _SpyLLM.constructed is False


# ---------------------------------------------------------------------------
# clone endpoint (HTTP)
# ---------------------------------------------------------------------------


async def test_clone_endpoint_returns_201_photo_response(
    async_db: AsyncSession, storage, authed_client: AsyncClient
) -> None:
    user_id = await authed_user_id(authed_client)
    src_entry = await _ensure_entry(async_db, SRC_DAY, user_id=user_id)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")

    resp = await authed_client.post(
        f"/api/v1/entries/{TARGET_DAY}/meals/clone", json={"source_photo_id": src.id}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] != src.id
    assert body["filename"].startswith(f"{TARGET_DAY}_photo-")
    assert {"id", "entry_id", "filename", "meal_time", "created_at"} <= set(body)


async def test_clone_endpoint_strips_meal_time_tz(
    async_db: AsyncSession, storage, authed_client: AsyncClient
) -> None:
    user_id = await authed_user_id(authed_client)
    src_entry = await _ensure_entry(async_db, SRC_DAY, user_id=user_id)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")

    # 14:30 at +02:00 == 12:30 UTC; stored naive-UTC, no offset in the response.
    resp = await authed_client.post(
        f"/api/v1/entries/{TARGET_DAY}/meals/clone",
        json={"source_photo_id": src.id, "meal_time": "2026-06-10T14:30:00+02:00"},
    )

    assert resp.status_code == 201
    assert resp.json()["meal_time"] == "2026-06-10T12:30:00"


async def test_clone_endpoint_requires_auth(
    async_db: AsyncSession, async_client: AsyncClient
) -> None:
    resp = await async_client.post(
        f"/api/v1/entries/{TARGET_DAY}/meals/clone", json={"source_photo_id": 1}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# list_recent()
# ---------------------------------------------------------------------------


async def test_recent_dedupes_by_dish_and_counts_distinct_dates(
    async_db: AsyncSession, storage
) -> None:
    d1, d2, d3 = (
        datetime.date(2026, 6, 1),
        datetime.date(2026, 6, 3),
        datetime.date(2026, 6, 7),
    )
    for i, day in enumerate((d1, d2, d3), start=1):
        entry = await _ensure_entry(async_db, day)
        await _add_meal(async_db, entry, f"{day}_photo-1.jpg", dish_name="Oatmeal")
    # a second "Oatmeal" photo on the newest day — must not inflate times_logged
    newest_entry = await _get_entry(async_db, d3)
    second = await _add_meal(async_db, newest_entry, f"{d3}_photo-2.jpg", dish_name="Oatmeal")

    recent = await MealService(async_db).list_recent()

    oatmeal = [r for r in recent if r.dish_name == "Oatmeal"]
    assert len(oatmeal) == 1
    assert oatmeal[0].times_logged == 3
    assert oatmeal[0].last_logged == d3
    assert oatmeal[0].source_photo_id == second.id  # newest instance is representative


async def test_recent_confirmed_only_and_excludes_null_dish(
    async_db: AsyncSession, storage
) -> None:
    entry = await _ensure_entry(async_db, SRC_DAY)
    await _add_meal(async_db, entry, f"{SRC_DAY}_photo-1.jpg", dish_name="Confirmed dish")
    await _add_meal(
        async_db, entry, f"{SRC_DAY}_photo-2.jpg", dish_name="Pending dish", status="complete"
    )
    await _add_meal(async_db, entry, f"{SRC_DAY}_photo-3.jpg", dish_name=None)

    names = {r.dish_name for r in await MealService(async_db).list_recent()}
    assert names == {"Confirmed dish"}


async def test_recent_orders_newest_first_with_flags(async_db: AsyncSession, storage) -> None:
    older = datetime.date(2026, 6, 1)
    newer = datetime.date(2026, 6, 5)
    e_old = await _ensure_entry(async_db, older)
    await _add_meal(async_db, e_old, f"{older}_photo-1.jpg", dish_name="Rice bowl", histamine=None)
    e_new = await _ensure_entry(async_db, newer)
    await _add_meal(
        async_db, e_new, f"{newer}_photo-1.jpg", dish_name="Toast", gluten=True, histamine=None
    )

    recent = await MealService(async_db).list_recent()

    assert [r.dish_name for r in recent] == ["Toast", "Rice bowl"]
    toast = next(r for r in recent if r.dish_name == "Toast")
    assert "gluten" in toast.diet_flags


async def test_recent_empty_when_no_confirmed(async_db: AsyncSession, storage) -> None:
    entry = await _ensure_entry(async_db, SRC_DAY)
    await _add_meal(async_db, entry, f"{SRC_DAY}_photo-1.jpg", status="complete")
    assert await MealService(async_db).list_recent() == []


async def test_recent_endpoint_requires_auth(
    async_db: AsyncSession, async_client: AsyncClient
) -> None:
    resp = await async_client.get("/api/v1/meals/recent")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# clone() — Redis entry cache invalidation
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("memory_redis")
async def test_clone_busts_stale_entry_cache(
    async_db: AsyncSession,
    storage,
    memory_redis: dict,
) -> None:
    """Warm Redis with the target entry, then clone — GET must include the new photo.

    Reproduces the prod "Log again" bug: without invalidation, get_entry keeps
    serving the pre-clone cached payload until TTL or an unrelated write.
    """
    from app.cache.keys import entry_key
    from app.services.entries import EntryService
    from f0rge_db.tenant import current_user_id

    src_entry = await _ensure_entry(async_db, SRC_DAY)
    src = await _add_meal(async_db, src_entry, f"{SRC_DAY}_photo-1.jpg")
    await _ensure_entry(async_db, TARGET_DAY)

    svc = EntryService(async_db)
    before = await svc.get_entry(TARGET_DAY)
    assert before.photos == []
    cache_key = entry_key(current_user_id(), TARGET_DAY)
    assert cache_key in memory_redis["store"]

    # Poison the cache with the photo-less payload so a miss would look like a
    # hit if clone failed to invalidate.
    memory_redis["store"][cache_key] = before.model_dump_json()

    cloned = await MealService(async_db).clone(TARGET_DAY, src.id)

    assert cache_key not in memory_redis["store"]
    after = await svc.get_entry(TARGET_DAY)
    assert any(p.id == cloned.id for p in after.photos)
