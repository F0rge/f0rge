from __future__ import annotations

# python -m app.embedding_pipeline.backfill [--dry-run]

import argparse
import asyncio

from sqlalchemy import text

from app.database import async_session_maker
from app.services.llm.factory import (
    DEFAULT_EMBEDDING_MODEL,
    resolve_embedding_credentials,
)

# Tables embedded by the pipeline. Order matches the triggers in migration 005.
_EMBEDABLE_TABLES: tuple[str, ...] = (
    "entries",
    "labs",
    "treatments",
    "photo_analyses",
)


async def _enqueue_missing(table_name: str, model: str, dry_run: bool) -> int:
    """Enqueue source rows that have no embedding for the current model.

    Set-based: one INSERT ... SELECT per table. The LEFT JOIN against `embedding`
    and the NOT EXISTS against `embedding_queue` mean re-running this is idempotent.
    """
    # `:model` is the only bound param; table names come from the curated tuple above
    # and are interpolated directly to avoid asyncpg's "same param used in multiple
    # contexts" type-inference quirk.
    count_sql = text(
        f"""
        SELECT count(*) FROM {table_name} src
        LEFT JOIN embedding emb
          ON emb.source_table = '{table_name}'
         AND emb.source_id = src.id
         AND emb.embedding_model = :model
        WHERE emb.id IS NULL
          AND NOT EXISTS (
            SELECT 1 FROM embedding_queue q
            WHERE q.source_table = '{table_name}' AND q.source_id = src.id
          )
        """
    )
    insert_sql = text(
        f"""
        INSERT INTO embedding_queue (source_table, source_id, action)
        SELECT '{table_name}', src.id, 'INSERT'
        FROM {table_name} src
        LEFT JOIN embedding emb
          ON emb.source_table = '{table_name}'
         AND emb.source_id = src.id
         AND emb.embedding_model = :model
        WHERE emb.id IS NULL
          AND NOT EXISTS (
            SELECT 1 FROM embedding_queue q
            WHERE q.source_table = '{table_name}' AND q.source_id = src.id
          )
        """
    )

    async with async_session_maker() as db:
        if dry_run:
            result = await db.execute(count_sql, {"model": model})
            return int(result.scalar_one())
        result = await db.execute(insert_sql, {"model": model})
        await db.commit()
        return result.rowcount or 0


async def _run(dry_run: bool) -> None:
    async with async_session_maker() as db:
        _, model = await resolve_embedding_credentials(db)
    if not model:
        model = DEFAULT_EMBEDDING_MODEL

    print(f"Backfill mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Embedding model: {model}\n")

    for table_name in _EMBEDABLE_TABLES:
        count = await _enqueue_missing(table_name, model, dry_run)
        verb = "would enqueue" if dry_run else "enqueued"
        print(f"  {table_name}: {verb} {count} rows")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill embedding queue for all unembedded rows"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only; do not insert into embedding_queue",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.dry_run))


if __name__ == "__main__":
    main()
