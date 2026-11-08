"""Read-only scan of meal photos whose image or thumbnail is missing.

Run inside the marrow-api container (working directory
``/app/apps/marrow/backend``), which already has ``DATABASE_URL`` and the
photo bucket settings:

    uv run python -m scripts.scan_missing_photos

Prints TSV to stdout: photo id, meal id, meal name, date, user id, and which
file is missing (``image``, ``thumbnail``, or ``image,thumbnail``). Library
meals have no filename and are skipped. A final ``# N photo(s)...`` line is a
count, not a row.

The scan sets ``app.user_id`` per user so FORCE RLS still returns every
tenant, inside ``SET TRANSACTION READ ONLY``. It never writes, deletes, or
updates rows or objects.
"""

from __future__ import annotations

import asyncio
import datetime
import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.models.meal import Meal
from app.models.photo import Photo
from app.services.photo_storage import missing_photo_objects

HEADER = "photo_id\tmeal_id\tmeal_name\tdate\tuser_id\tmissing"


@dataclass(frozen=True)
class MissingPhoto:
    photo_id: int
    meal_id: int
    meal_name: str
    entry_date: datetime.date
    user_id: uuid.UUID
    missing: str


def _cell(value: str) -> str:
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def format_missing_photo(row: MissingPhoto) -> str:
    return "\t".join(
        [
            str(row.photo_id),
            str(row.meal_id),
            _cell(row.meal_name),
            row.entry_date.isoformat(),
            str(row.user_id),
            row.missing,
        ]
    )


async def missing_photo_rows(session: AsyncSession) -> list[MissingPhoto]:
    """Photos with a filename whose full image and/or thumbnail is absent."""
    previous = await session.scalar(sa.text("SELECT current_setting('app.user_id', true)"))
    user_ids = list(
        (await session.execute(sa.text("SELECT id FROM users ORDER BY id"))).scalars().all()
    )
    found: list[MissingPhoto] = []
    try:
        for user_id in user_ids:
            await session.execute(
                sa.text("SELECT set_config('app.user_id', :user_id, true)"),
                {"user_id": str(user_id)},
            )
            stmt = (
                sa.select(
                    Photo.id,
                    Photo.meal_id,
                    Photo.filename,
                    Photo.user_id,
                    Photo.label,
                    Meal.label,
                    Entry.date,
                )
                .join(Entry, Entry.id == Photo.entry_id)
                .outerjoin(Meal, Meal.id == Photo.meal_id)
                .where(Photo.filename.is_not(None))
                .order_by(Photo.id)
            )
            rows = (await session.execute(stmt)).all()
            for (
                photo_id,
                meal_id,
                filename,
                owner_id,
                photo_label,
                meal_label,
                entry_date,
            ) in rows:
                if not filename:
                    continue
                missing = await asyncio.to_thread(
                    missing_photo_objects, filename, user_id=str(owner_id)
                )
                if not missing:
                    continue
                found.append(
                    MissingPhoto(
                        photo_id=photo_id,
                        meal_id=meal_id,
                        meal_name=meal_label or photo_label or "",
                        entry_date=entry_date,
                        user_id=owner_id,
                        missing=",".join(missing),
                    )
                )
    finally:
        if previous:
            await session.execute(
                sa.text("SELECT set_config('app.user_id', :user_id, true)"),
                {"user_id": previous},
            )
    return found


async def _main() -> None:
    from app.database import async_session_maker

    async with async_session_maker() as session:
        # First statement on a fresh process: no tenant GUC query has run yet,
        # so Postgres still accepts SET TRANSACTION.
        await session.execute(sa.text("SET TRANSACTION READ ONLY"))
        rows = await missing_photo_rows(session)
        print(HEADER)
        for row in rows:
            print(format_missing_photo(row))
        print(f"# {len(rows)} photo(s) with missing files", flush=True)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
