from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.embedding import Embedding
from app.models.entry import Entry


async def _insert_entry(db: AsyncSession, notes: str = "Feeling fine") -> Entry:
    entry = Entry(
        date=datetime.date.today(),
        overall=6,
        bloating=2,
        joint_pain=1,
        neuro=3,
        sleep_quality=7,
        stress=4,
        diet_risk="low",
        supplements="",
        sick=False,
        hot_shower=False,
        notes=notes,
        symptoms_json={},
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


class _FakeEmbeddingClient:
    """Stand-in for OpenRouterEmbeddingClient.embed_batch with deterministic 1024-d vecs."""

    async def embed_batch(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        return [[0.1] * 1024 for _ in texts]

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        return [0.1] * 1024


def _queue_row(queue_id: int, source_table: str, source_id: int, action: str) -> Any:
    return SimpleNamespace(
        id=queue_id,
        user_id=uuid.UUID(settings.default_storage_user_id),
        source_table=source_table,
        source_id=source_id,
        action=action,
    )


async def test_process_row_insert_creates_embedding(async_db: AsyncSession) -> None:
    """_process_row creates embedding rows for an INSERT action."""
    entry = await _insert_entry(async_db)
    from app.embedding_pipeline.worker import _process_row

    async with async_db.begin_nested():
        await _process_row(
            async_db,
            _queue_row(999, "entries", entry.id, "INSERT"),
            _FakeEmbeddingClient(),
            "openai/text-embedding-3-small",
        )

    count = (
        await async_db.execute(
            select(func.count())
            .select_from(Embedding)
            .where(
                Embedding.source_table == "entries",
                Embedding.source_id == entry.id,
            )
        )
    ).scalar_one()
    assert count >= 1


async def test_process_row_delete_removes_embedding(async_db: AsyncSession) -> None:
    """_process_row with DELETE action removes all embedding rows for that source."""
    entry = await _insert_entry(async_db)

    emb = Embedding(
        source_table="entries",
        source_id=entry.id,
        chunk_index=0,
        chunk_text="some chunk",
        embedding=[0.1] * 1024,
        embedding_model="openai/text-embedding-3-small",
        embedding_dim=1024,
    )
    async_db.add(emb)
    await async_db.flush()

    from app.embedding_pipeline.worker import _process_row

    async with async_db.begin_nested():
        await _process_row(
            async_db,
            _queue_row(999, "entries", entry.id, "DELETE"),
            _FakeEmbeddingClient(),
            "openai/text-embedding-3-small",
        )

    count = (
        await async_db.execute(
            select(func.count())
            .select_from(Embedding)
            .where(
                Embedding.source_table == "entries",
                Embedding.source_id == entry.id,
            )
        )
    ).scalar_one()
    assert count == 0


async def test_process_row_upserts_on_update(async_db: AsyncSession) -> None:
    """Second INSERT/UPDATE for same source+chunk UPSERTS, not duplicates."""
    entry = await _insert_entry(async_db)
    client = _FakeEmbeddingClient()
    from app.embedding_pipeline.worker import _process_row

    async with async_db.begin_nested():
        await _process_row(
            async_db,
            _queue_row(998, "entries", entry.id, "INSERT"),
            client,
            "openai/text-embedding-3-small",
        )

    count_after_insert = (
        await async_db.execute(
            select(func.count())
            .select_from(Embedding)
            .where(
                Embedding.source_table == "entries",
                Embedding.source_id == entry.id,
            )
        )
    ).scalar_one()

    await async_db.execute(
        text(
            "INSERT INTO embedding_queue (user_id, source_table, source_id, action)"
            " SELECT user_id, 'entries', :sid, 'UPDATE' FROM entries WHERE id = :sid"
        ),
        {"sid": entry.id},
    )
    await async_db.flush()
    queue_id = (
        await async_db.execute(
            text(
                "SELECT id FROM embedding_queue WHERE source_table='entries'"
                " AND source_id=:sid ORDER BY id DESC LIMIT 1"
            ),
            {"sid": entry.id},
        )
    ).scalar_one()

    async with async_db.begin_nested():
        await _process_row(
            async_db,
            _queue_row(queue_id, "entries", entry.id, "UPDATE"),
            client,
            "openai/text-embedding-3-small",
        )

    count_after_update = (
        await async_db.execute(
            select(func.count())
            .select_from(Embedding)
            .where(
                Embedding.source_table == "entries",
                Embedding.source_id == entry.id,
            )
        )
    ).scalar_one()
    assert count_after_update == count_after_insert


async def test_claim_batch_returns_pending_rows(async_db: AsyncSession) -> None:
    """_claim_batch returns rows available within the current savepoint."""
    entry = await _insert_entry(async_db, notes="Claim batch test")

    await async_db.execute(
        text(
            "INSERT INTO embedding_queue (user_id, source_table, source_id, action)"
            " SELECT user_id, 'entries', :sid, 'INSERT' FROM entries WHERE id = :sid"
        ),
        {"sid": entry.id},
    )
    await async_db.flush()

    from app.embedding_pipeline.worker import _claim_batch

    rows = await _claim_batch(async_db)
    assert len(rows) >= 1
    assert any(r.source_table == "entries" and r.source_id == entry.id for r in rows)
