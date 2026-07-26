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
from app.crud.meal_analysis_queue import LISTEN_CHANNEL
from app.models.meal_analysis_queue import STAGE_RUNNING, MealAnalysisQueue
from app.services.food_analysis_orchestrator import run_staged_pipeline
from f0rge_db.tenant import apply_service_role

logger = logging.getLogger(__name__)


def _is_non_retryable(exc: BaseException) -> bool:
    """Auth / missing-resource failures will not succeed on retry."""
    from f0rge_core.exceptions import ExternalServiceError, NotFoundError

    if isinstance(exc, NotFoundError):
        return True
    if isinstance(exc, ExternalServiceError):
        msg = str(exc)
        # OpenRouterClient: "Upstream LLM error: {status} {body}"
        return "error: 401" in msg or "error: 403" in msg
    return False


async def _claim_and_lease_batch(db: AsyncSession) -> list[Any]:
    """Claim rows with SKIP LOCKED, set a short lease, then caller commits.

    Lease uses ``STAGE_RUNNING`` + ``last_attempt_at`` so the FOR UPDATE lock
    is not held across the LLM call. Stale leases older than
    ``meal_analysis_stale_analyzing_minutes`` are reclaimable.
    """
    lease_minutes = settings.meal_analysis_stale_analyzing_minutes
    stmt = text(
        """
        SELECT id, user_id, meal_id, photo_id, attempts
        FROM meal_analysis_queue
        WHERE attempts < :max_attempts
          AND (
            stage IS DISTINCT FROM :stage_running
            OR last_attempt_at IS NULL
            OR last_attempt_at < NOW() - make_interval(mins => :lease_minutes)
          )
          AND (
            stage = :stage_running
            OR last_attempt_at IS NULL
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
            "lease_minutes": lease_minutes,
            "stage_running": STAGE_RUNNING,
        },
    )
    rows = result.fetchall()
    if not rows:
        return []

    now = datetime.datetime.utcnow()
    for row in rows:
        await db.execute(
            text(
                """
                UPDATE meal_analysis_queue
                SET stage = :stage_running,
                    last_attempt_at = :now
                WHERE id = :id
                """
            ),
            {"id": row.id, "now": now, "stage_running": STAGE_RUNNING},
        )
    return rows


# Backward-compatible name for tests that import _claim_batch.
async def _claim_batch(db: AsyncSession) -> list[Any]:
    return await _claim_and_lease_batch(db)


async def _delete_queue_row(row_id: int) -> None:
    async with async_session_maker() as db:
        async with db.begin():
            await apply_service_role(db, "worker")
            await db.execute(delete(MealAnalysisQueue).where(MealAnalysisQueue.id == row_id))


async def _mark_failed(row_id: int, error: str) -> None:
    async with async_session_maker() as db:
        async with db.begin():
            await apply_service_role(db, "worker")
            await db.execute(
                text(
                    """
                    UPDATE meal_analysis_queue
                    SET attempts = attempts + 1,
                        last_attempt_at = :now,
                        last_error = :error,
                        stage = NULL
                    WHERE id = :id
                    """
                ),
                {
                    "id": row_id,
                    "now": datetime.datetime.utcnow(),
                    "error": error[:2000],
                },
            )


async def process_pending_once() -> int:
    """Lease a batch, commit, then process each row without holding row locks.

    Returns number of rows attempted.
    """
    async with async_session_maker() as db:
        async with db.begin():
            await apply_service_role(db, "worker")
            rows = await _claim_and_lease_batch(db)

    if not rows:
        return 0

    for row in rows:
        try:
            await run_staged_pipeline(row.photo_id, row.user_id)
            await _delete_queue_row(row.id)
            logger.info(
                {
                    "event": "meal_analysis_queue_done",
                    "row_id": row.id,
                    "photo_id": row.photo_id,
                    "meal_id": row.meal_id,
                }
            )
        except Exception as exc:
            if _is_non_retryable(exc):
                logger.error(
                    {
                        "event": "meal_analysis_queue_non_retryable",
                        "row_id": row.id,
                        "photo_id": row.photo_id,
                        "error": str(exc)[:500],
                    }
                )
                await _delete_queue_row(row.id)
            else:
                logger.error(
                    {
                        "event": "meal_analysis_queue_failed",
                        "row_id": row.id,
                        "photo_id": row.photo_id,
                        "error": str(exc)[:500],
                    }
                )
                await _mark_failed(row.id, str(exc))
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
