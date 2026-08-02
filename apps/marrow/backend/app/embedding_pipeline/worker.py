from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from typing import Any, Optional

import asyncpg
from sqlalchemy import delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_maker
from app.embedding_pipeline.chunking import chunk_text
from app.embedding_pipeline.serialization import SERIALIZERS
from app.models.embedding import Embedding
from app.models.embedding_queue import EmbeddingQueue
from app.services.llm.base import EmbeddingClient
from app.services.llm.factory import (
    build_embedding_client,
    resolve_embedding_credentials,
)
from f0rge_db.tenant import apply_service_role, apply_session_user_id

logger = logging.getLogger(__name__)

_LISTEN_CHANNEL = "embedding_queue"


async def _claim_batch(db: AsyncSession) -> list[Any]:
    """Claim up to batch_size pending queue rows using SKIP LOCKED.

    Skips rows still in their exponential backoff window.
    """
    stmt = text(
        """
        SELECT id, user_id, source_table, source_id, action
        FROM embedding_queue
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
            "max_attempts": settings.embedding_worker_max_attempts,
            "batch_size": settings.embedding_worker_batch_size,
        },
    )
    return result.fetchall()


async def _delete_queue_row(db: AsyncSession, row_id: int) -> None:
    await db.execute(delete(EmbeddingQueue).where(EmbeddingQueue.id == row_id))


async def _process_row(
    db: AsyncSession,
    row: Any,
    client: EmbeddingClient,
    model: str,
) -> None:
    """Process a single queue row. Raises on error — caller's savepoint rolls back."""
    await apply_session_user_id(db, row.user_id)
    if row.action == "DELETE":
        await db.execute(
            delete(Embedding).where(
                Embedding.user_id == row.user_id,
                Embedding.source_table == row.source_table,
                Embedding.source_id == row.source_id,
            )
        )
        await _delete_queue_row(db, row.id)
        return

    serializer = SERIALIZERS.get(row.source_table)
    if serializer is None:
        logger.warning({"event": "unknown_source_table", "source_table": row.source_table})
        await _delete_queue_row(db, row.id)
        return

    content: Optional[str] = await serializer(db, row.source_id)  # type: ignore[assignment]
    if content is None:
        # Row was deleted between trigger fire and worker pickup.
        await _delete_queue_row(db, row.id)
        return

    chunks = chunk_text(content)
    if not chunks:
        await _delete_queue_row(db, row.id)
        return

    vectors = await client.embed_batch(chunks, model=model)

    for chunk_index, (chunk, vector) in enumerate(zip(chunks, vectors)):
        stmt = pg_insert(Embedding).values(
            user_id=row.user_id,
            source_table=row.source_table,
            source_id=row.source_id,
            chunk_index=chunk_index,
            chunk_text=chunk,
            embedding=vector,
            embedding_model=model,
            embedding_dim=len(vector),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_embedding_user_source_chunk_model",
            set_={
                "chunk_text": stmt.excluded.chunk_text,
                "embedding": stmt.excluded.embedding,
                "embedding_dim": stmt.excluded.embedding_dim,
                "created_at": datetime.datetime.utcnow(),
            },
        )
        await db.execute(stmt)

    await _delete_queue_row(db, row.id)


async def _mark_failed(row_id: int, error: str) -> None:
    """In a separate transaction, increment attempts and store last_error."""
    async with async_session_maker() as db:
        async with db.begin():
            await apply_service_role(db, "worker")
            await db.execute(
                text(
                    """
                    UPDATE embedding_queue
                    SET attempts = attempts + 1,
                        last_attempt_at = :now,
                        last_error = :error
                    WHERE id = :id
                    """
                ),
                {
                    "id": row_id,
                    "now": datetime.datetime.utcnow(),
                    "error": error[:2000],
                },
            )


async def _process_pending() -> None:
    """Claim and process one batch of pending queue rows."""
    async with async_session_maker() as db:
        async with db.begin():
            await apply_service_role(db, "worker")
            client = await _build_client_or_none(db)

    if client is None:
        return

    _, model = await _credentials_for_model()

    async with async_session_maker() as db:
        async with db.begin():
            await apply_service_role(db, "worker")
            rows = await _claim_batch(db)
            if not rows:
                return

            for row in rows:
                # Per-row SAVEPOINT so a failure rolls back only that row's
                # partial work; sibling rows in the batch still commit.
                savepoint = await db.begin_nested()
                try:
                    await _process_row(db, row, client, model)
                except Exception as exc:
                    await savepoint.rollback()
                    logger.error(
                        {
                            "event": "row_processing_failed",
                            "row_id": row.id,
                            "error": str(exc)[:500],
                        }
                    )
                    await _mark_failed(row.id, str(exc))
                else:
                    await savepoint.commit()


async def _reference_user_id() -> uuid.UUID:
    """Platform reference tenant used for worker BYOK when no request user exists."""
    return uuid.UUID(settings.default_storage_user_id)


async def _build_client_or_none(db: AsyncSession) -> Optional[EmbeddingClient]:
    """Build an embedding client for the worker.

    The worker has no HTTP user context. ``apply_service_role`` stamps a nil
    ``app.user_id``, so BYOK in ``user_settings`` is invisible under FORCE RLS
    unless we switch to the reference tenant first. Env ``OPENROUTER_API_KEY``
    remains the final fallback inside ``resolve_embedding_credentials``.
    """
    try:
        ref = await _reference_user_id()
        await apply_session_user_id(db, ref)
        return await build_embedding_client(db)
    except Exception as exc:
        logger.warning(
            {
                "event": "embedding_not_configured",
                "error": str(exc)[:200],
            }
        )
        return None


async def _credentials_for_model() -> tuple[Optional[str], str]:
    async with async_session_maker() as db:
        async with db.begin():
            ref = await _reference_user_id()
            await apply_session_user_id(db, ref)
            return await resolve_embedding_credentials(db, user_id=ref)


async def run() -> None:
    """Main worker loop. LISTEN on the embedding_queue channel; fall back to polling
    every poll_interval seconds."""
    poll_interval = settings.embedding_worker_poll_interval_seconds
    logger.info({"event": "worker_start", "poll_interval": poll_interval})

    raw_conn: Optional[asyncpg.Connection] = None
    try:
        url = make_url(settings.database_url)
        asyncpg_dsn = (
            f"postgresql://{url.username}:{url.password}"
            f"@{url.host}:{url.port or 5432}/{url.database}"
        )
        raw_conn = await asyncpg.connect(asyncpg_dsn)
        await raw_conn.execute(f"LISTEN {_LISTEN_CHANNEL}")
        logger.info({"event": "listen_registered", "channel": _LISTEN_CHANNEL})
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
        await raw_conn.add_listener(_LISTEN_CHANNEL, _on_notify)

    try:
        while True:
            await _process_pending()

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
                raw_conn.remove_listener(_LISTEN_CHANNEL, _on_notify)
            except Exception:
                pass
            await raw_conn.close()
