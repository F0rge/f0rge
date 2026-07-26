from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Optional

import asyncpg
from sqlalchemy import delete, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_maker
from app.models.meal_analysis_queue import MealAnalysisQueue
from app.services.food_analysis_orchestrator import run_staged_pipeline
from app.services.meal_analysis_enqueue import LISTEN_CHANNEL
from f0rge_db.tenant import apply_service_role

logger = logging.getLogger(__name__)


async def _claim_batch(db: AsyncSession) -> list[Any]:
    """Claim up to batch_size pending queue rows using SKIP LOCKED."""
    stmt = text(
        """
        SELECT id, user_id, meal_id, photo_id, attempts
        FROM meal_analysis_queue
        WHERE attempts < :max_attempts
          AND (
            last_attempt_at IS NULL
            OR last_attempt_at + (INTERVAL '1 second' * POWER(2, attempts)) < NOW()
          )
        ORDER BY enqueued_at
        LIMIT :batch_size
        FOR UPDATE SKIP LOCKED
        """
    )
    result = await db.execute(
        stmt,
        {
            "max_attempts": settings.meal_analysis_worker_max_attempts,
            "batch_size": settings.meal_analysis_worker_batch_size,
        },
    )
    return result.fetchall()


async def process_pending_once() -> int:
    """Claim and process one batch while holding SKIP LOCKED row locks.

    Returns number of rows attempted. Used by the long-running worker loop and by
    ``meal_analysis_inline`` after enqueue.
    """
    async with async_session_maker() as db:
        async with db.begin():
            await apply_service_role(db, "worker")
            rows = await _claim_batch(db)
            if not rows:
                return 0

            for row in rows:
                try:
                    # Pipeline opens its own sessions; queue row stays locked here.
                    await run_staged_pipeline(row.photo_id, row.user_id)
                    await db.execute(
                        delete(MealAnalysisQueue).where(MealAnalysisQueue.id == row.id)
                    )
                    logger.info(
                        {
                            "event": "meal_analysis_queue_done",
                            "row_id": row.id,
                            "photo_id": row.photo_id,
                            "meal_id": row.meal_id,
                        }
                    )
                except Exception as exc:
                    logger.error(
                        {
                            "event": "meal_analysis_queue_failed",
                            "row_id": row.id,
                            "photo_id": row.photo_id,
                            "error": str(exc)[:500],
                        }
                    )
                    await db.execute(
                        text(
                            """
                            UPDATE meal_analysis_queue
                            SET attempts = attempts + 1,
                                last_attempt_at = :now,
                                last_error = :error
                            WHERE id = :id
                            """
                        ),
                        {
                            "id": row.id,
                            "now": datetime.datetime.utcnow(),
                            "error": str(exc)[:2000],
                        },
                    )
            return len(rows)


async def run() -> None:
    """LISTEN on meal_analysis_queue; poll as fallback."""
    poll_interval = settings.meal_analysis_worker_poll_interval_seconds
    logger.info({"event": "meal_analysis_worker_start", "poll_interval": poll_interval})

    raw_conn: Optional[asyncpg.Connection] = None
    try:
        url = make_url(settings.database_url)
        asyncpg_dsn = (
            f"postgresql://{url.username}:{url.password}"
            f"@{url.host}:{url.port or 5432}/{url.database}"
        )
        raw_conn = await asyncpg.connect(asyncpg_dsn)
        await raw_conn.execute(f"LISTEN {LISTEN_CHANNEL}")
        logger.info({"event": "listen_registered", "channel": LISTEN_CHANNEL})
    except Exception as exc:
        logger.warning({"event": "listen_failed", "error": str(exc), "fallback": "poll-only"})
        raw_conn = None

    notify_queue: asyncio.Queue[bool] = asyncio.Queue()

    def _on_notify(
        conn: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        notify_queue.put_nowait(True)

    if raw_conn is not None:
        await raw_conn.add_listener(LISTEN_CHANNEL, _on_notify)

    try:
        while True:
            await process_pending_once()

            try:
                await asyncio.wait_for(notify_queue.get(), timeout=poll_interval)
                while not notify_queue.empty():
                    notify_queue.get_nowait()
            except asyncio.TimeoutError:
                pass
            except Exception as exc:
                logger.error({"event": "listen_error", "error": str(exc)})
                await asyncio.sleep(poll_interval)
    finally:
        if raw_conn is not None:
            try:
                raw_conn.remove_listener(LISTEN_CHANNEL, _on_notify)
            except Exception:
                pass
            await raw_conn.close()
