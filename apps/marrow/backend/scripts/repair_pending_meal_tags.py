"""One-off repair: transition meal tags stuck in pending_analysis."""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.services.tag_delivery import TagDeliveryService


async def main() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url)
    delivery = TagDeliveryService()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT DISTINCT source_photo_id, tagger_id "
                    "FROM meal_tags WHERE status = 'pending_analysis'"
                )
            )
        ).fetchall()
    await engine.dispose()
    for source_photo_id, tagger_id in rows:
        print("repairing", source_photo_id, tagger_id)
        await delivery.process_photo_only_source(source_photo_id, tagger_id)
    print("done", len(rows))


if __name__ == "__main__":
    asyncio.run(main())
