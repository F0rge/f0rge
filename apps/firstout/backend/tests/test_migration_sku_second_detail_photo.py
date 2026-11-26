from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.test_fractional_inventory_migration import migrate, seed_old_records

pytestmark = pytest.mark.no_db
PREVIOUS = "118_sku_retail_precision"
SECOND_DETAIL = "119_sku_second_detail_photo"


async def test_second_close_up_migration_preserves_existing_gallery(second_postgres_url: str):
    migrate(second_postgres_url, PREVIOUS)
    engine = create_async_engine(second_postgres_url, poolclass=NullPool)
    studio = ["studio/1.jpg", "studio/2.jpg", "studio/3.jpg"]
    setting = "setting/room.jpg"
    first_detail = "detail/original.jpg"
    legacy_gallery = sa.text(
        "SELECT gallery_photo_keys, setting_photo_storage_key, detail_photo_storage_key "
        "FROM skus WHERE id = :id"
    )
    second_detail = sa.text("SELECT second_detail_photo_storage_key FROM skus WHERE id = :id")
    try:
        _, sku_id, _, _ = await seed_old_records(engine)
        sku = {"id": sku_id}
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    "UPDATE skus SET gallery_photo_keys = :studio, "
                    "setting_photo_storage_key = :setting, detail_photo_storage_key = :detail "
                    "WHERE id = :id"
                ),
                {**sku, "studio": studio, "setting": setting, "detail": first_detail},
            )

        migrate(second_postgres_url, SECOND_DETAIL)
        async with engine.begin() as conn:
            assert tuple((await conn.execute(legacy_gallery, sku)).one()) == (
                studio,
                setting,
                first_detail,
            )
            assert (await conn.execute(second_detail, sku)).scalar_one() is None
            await conn.execute(
                sa.text("UPDATE skus SET second_detail_photo_storage_key = :detail WHERE id = :id"),
                {**sku, "detail": "detail/second-angle.jpg"},
            )
            # A previous release can still update its original detail slot.
            await conn.execute(
                sa.text("UPDATE skus SET detail_photo_storage_key = :detail WHERE id = :id"),
                {**sku, "detail": "detail/replacement.jpg"},
            )
            assert (
                await conn.execute(second_detail, sku)
            ).scalar_one() == "detail/second-angle.jpg"

        migrate(second_postgres_url, PREVIOUS, command="downgrade")
        async with engine.connect() as conn:
            assert tuple((await conn.execute(legacy_gallery, sku)).one()) == (
                studio,
                setting,
                "detail/replacement.jpg",
            )
    finally:
        await engine.dispose()
