from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.models.entry import Entry


# ---------------------------------------------------------------------------
# Helpers — these tests bypass the SAVEPOINT fixture because backfill needs
# to commit rows to the real connection to see them across sessions.
# ---------------------------------------------------------------------------


async def _seed_entry_and_commit(sm: async_sessionmaker, date: datetime.date) -> int:
    """Insert an entry using the provided session maker and commit it."""
    async with sm() as db:
        async with db.begin():
            e = Entry(
                date=date,
                overall=5,
                bloating=2,
                joint_pain=1,
                neuro=2,
                sleep_quality=6,
                stress=3,
                diet_risk="low",
                supplements="",
                sick=False,
                hot_shower=False,
                notes=f"Entry for {date}",
                symptoms_json={},
            )
            db.add(e)
        await db.refresh(e)
        return e.id


async def _count_queue(sm: async_sessionmaker, source_table: str = "entries") -> int:
    async with sm() as db:
        result = await db.execute(
            text("SELECT COUNT(*) FROM embedding_queue WHERE source_table = :t"),
            {"t": source_table},
        )
        return result.scalar_one()


async def _cleanup(sm: async_sessionmaker, entry_ids: list[int]) -> None:
    """Remove test rows created outside the SAVEPOINT rollback."""
    async with sm() as db:
        async with db.begin():
            for eid in entry_ids:
                await db.execute(
                    text(
                        "DELETE FROM embedding_queue WHERE source_table='entries' AND source_id=:id"
                    ),
                    {"id": eid},
                )
                await db.execute(
                    text(
                        "DELETE FROM embedding WHERE source_table='entries' AND source_id=:id"
                    ),
                    {"id": eid},
                )
                await db.execute(text("DELETE FROM entries WHERE id=:id"), {"id": eid})


@pytest.fixture
def backfill_patches():
    """Shared patches for backfill tests: suppress engine creation."""
    return {}  # patches applied inline so we can inject the sm


async def test_backfill_enqueues_missing_entries(async_engine: AsyncEngine) -> None:
    sm = async_sessionmaker(async_engine, expire_on_commit=False)
    id1 = await _seed_entry_and_commit(sm, datetime.date(2025, 4, 1))
    id2 = await _seed_entry_and_commit(sm, datetime.date(2025, 4, 2))

    try:
        from app.embedding_pipeline.backfill import _run

        with (
            patch(
                "app.embedding_pipeline.backfill.resolve_embedding_credentials",
                return_value=("fake-key", "openai/text-embedding-3-small"),
            ),
            patch("app.embedding_pipeline.backfill.async_session_maker", sm),
        ):
            await _run(dry_run=False)
    except Exception:
        await _cleanup(sm, [id1, id2])
        raise

    try:
        count = await _count_queue(sm)
        assert count >= 2
    finally:
        await _cleanup(sm, [id1, id2])


async def test_backfill_dry_run_does_not_insert(async_engine: AsyncEngine) -> None:
    sm = async_sessionmaker(async_engine, expire_on_commit=False)
    eid = await _seed_entry_and_commit(sm, datetime.date(2025, 5, 10))

    try:
        from app.embedding_pipeline.backfill import _run

        with (
            patch(
                "app.embedding_pipeline.backfill.resolve_embedding_credentials",
                return_value=("fake-key", "openai/text-embedding-3-small"),
            ),
            patch("app.embedding_pipeline.backfill.async_session_maker", sm),
        ):
            await _run(dry_run=True)

        count = await _count_queue(sm)
        assert count == 0
    finally:
        await _cleanup(sm, [eid])


async def test_backfill_skips_already_embedded_rows(async_engine: AsyncEngine) -> None:
    sm = async_sessionmaker(async_engine, expire_on_commit=False)
    eid = await _seed_entry_and_commit(sm, datetime.date(2025, 6, 20))

    from app.models.embedding import Embedding

    async with sm() as db:
        async with db.begin():
            emb = Embedding(
                source_table="entries",
                source_id=eid,
                chunk_index=0,
                chunk_text="pre-existing",
                embedding=[0.0] * 1024,
                embedding_model="openai/text-embedding-3-small",
                embedding_dim=1024,
            )
            db.add(emb)

    try:
        from app.embedding_pipeline.backfill import _run

        with (
            patch(
                "app.embedding_pipeline.backfill.resolve_embedding_credentials",
                return_value=("fake-key", "openai/text-embedding-3-small"),
            ),
            patch("app.embedding_pipeline.backfill.async_session_maker", sm),
        ):
            await _run(dry_run=False)

        count = await _count_queue(sm)
        assert count == 0
    finally:
        await _cleanup(sm, [eid])


async def test_backfill_idempotent_on_second_run(async_engine: AsyncEngine) -> None:
    """Running backfill twice should not enqueue the same rows twice."""
    sm = async_sessionmaker(async_engine, expire_on_commit=False)
    eid = await _seed_entry_and_commit(sm, datetime.date(2025, 7, 15))

    try:
        from app.embedding_pipeline.backfill import _run

        with (
            patch(
                "app.embedding_pipeline.backfill.resolve_embedding_credentials",
                return_value=("fake-key", "openai/text-embedding-3-small"),
            ),
            patch("app.embedding_pipeline.backfill.async_session_maker", sm),
        ):
            await _run(dry_run=False)
            count_first = await _count_queue(sm)

            # Second run — ON CONFLICT DO NOTHING prevents duplicates.
            await _run(dry_run=False)
            count_second = await _count_queue(sm)

        assert count_second == count_first
    finally:
        await _cleanup(sm, [eid])
