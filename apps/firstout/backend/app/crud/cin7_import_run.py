from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cin7_import_run import Cin7ImportRun

# Stable key so every Cin7 import takes the same transaction-scoped lock.
ADVISORY_LOCK_KEY = 872014


class Cin7ImportRunCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, row: Cin7ImportRun) -> None:
        self.db.add(row)

    async def get(self, run_id: uuid.UUID) -> Optional[Cin7ImportRun]:
        return await self.db.get(Cin7ImportRun, run_id)

    async def list_recent(self, limit: int) -> list[Cin7ImportRun]:
        result = await self.db.scalars(
            select(Cin7ImportRun).order_by(Cin7ImportRun.created_at.desc()).limit(limit)
        )
        return list(result.all())

    async def acquire_lock(self) -> None:
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
        )

    async def try_lock(self) -> bool:
        """Take the import lock without waiting. False means another transaction holds it."""
        locked = await self.db.scalar(
            text("SELECT pg_try_advisory_xact_lock(:key)"),
            {"key": ADVISORY_LOCK_KEY},
        )
        return bool(locked)

    async def interrupt_in_flight(self, now: datetime.datetime) -> int:
        result = await self.db.execute(
            update(Cin7ImportRun)
            .where(Cin7ImportRun.status.in_(("queued", "running")))
            .values(
                status="failed",
                active_lock=None,
                finished_at=now,
                error_count=1,
                errors=[{"message": "interrupted by restart"}],
                updated_at=now,
            )
        )
        return int(result.rowcount or 0)

    async def active_id(self) -> Optional[uuid.UUID]:
        return await self.db.scalar(
            select(Cin7ImportRun.id).where(Cin7ImportRun.active_lock.is_(True)).limit(1)
        )

    async def latest_commit_finished_at(self) -> Optional[datetime.datetime]:
        return await self.db.scalar(
            select(Cin7ImportRun.finished_at)
            .where(
                Cin7ImportRun.mode == "commit",
                Cin7ImportRun.status == "completed",
            )
            .order_by(Cin7ImportRun.finished_at.desc())
            .limit(1)
        )

    async def stored_uploads(self) -> list[Cin7ImportRun]:
        result = await self.db.scalars(
            select(Cin7ImportRun).where(Cin7ImportRun.storage_key.is_not(None))
        )
        return list(result.all())

    async def fail_stale(self, cutoff: datetime.datetime) -> None:
        await self.db.execute(
            update(Cin7ImportRun)
            .where(
                Cin7ImportRun.active_lock.is_(True),
                Cin7ImportRun.updated_at < cutoff,
            )
            .values(
                status="failed",
                active_lock=None,
                finished_at=cutoff,
                error_count=1,
                errors=[{"message": "Import timed out before it finished"}],
                updated_at=cutoff,
            )
        )

    async def mark(self, run_id: uuid.UUID, values: dict[str, object]) -> None:
        payload = dict(values)
        payload["updated_at"] = datetime.datetime.utcnow()
        payload["active_lock"] = None
        await self.db.execute(
            update(Cin7ImportRun).where(Cin7ImportRun.id == run_id).values(**payload)
        )

    async def clear_storage(self, storage_key: str) -> None:
        await self.db.execute(
            update(Cin7ImportRun)
            .where(Cin7ImportRun.storage_key == storage_key)
            .values(storage_key=None, updated_at=datetime.datetime.utcnow())
        )
