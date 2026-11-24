from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.test_fractional_inventory_migration import migrate, seed_old_records


pytestmark = pytest.mark.no_db
PREVIOUS = "115_sku_setting_photo"
DETAIL_PHOTO = "116_sku_detail_photo"


async def test_detail_photo_migration_preserves_existing_gallery_and_legacy_writes(
    second_postgres_url: str,
) -> None:
    migrate(second_postgres_url, PREVIOUS)
    engine = create_async_engine(second_postgres_url, poolclass=NullPool)
    studio_keys = ["studio/1.jpg", "studio/2.jpg", "studio/3.jpg"]
    legacy_photos = sa.text(
        "SELECT gallery_photo_keys, setting_photo_storage_key FROM skus WHERE id = :id"
    )
    update_setting = sa.text("UPDATE skus SET setting_photo_storage_key = :setting WHERE id = :id")
    detail_photo = sa.text("SELECT detail_photo_storage_key FROM skus WHERE id = :id")
    try:
        _, sku_id, _, _ = await seed_old_records(engine)
        sku = {"id": sku_id}
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    "UPDATE skus SET gallery_photo_keys = :studio, "
                    "setting_photo_storage_key = :setting WHERE id = :id"
                ),
                {**sku, "studio": studio_keys, "setting": "setting/original.jpg"},
            )

        migrate(second_postgres_url, DETAIL_PHOTO)
        async with engine.begin() as conn:
            assert tuple((await conn.execute(legacy_photos, sku)).one()) == (
                studio_keys,
                "setting/original.jpg",
            )
            assert (await conn.execute(detail_photo, sku)).scalar_one() is None
            await conn.execute(
                sa.text("UPDATE skus SET detail_photo_storage_key = :detail WHERE id = :id"),
                {**sku, "detail": "detail/close-up.jpg"},
            )
            await conn.execute(update_setting, {**sku, "setting": "setting/replacement.jpg"})
            assert (await conn.execute(detail_photo, sku)).scalar_one() == "detail/close-up.jpg"

        migrate(second_postgres_url, PREVIOUS, command="downgrade")
        async with engine.connect() as conn:
            assert tuple((await conn.execute(legacy_photos, sku)).one()) == (
                studio_keys,
                "setting/replacement.jpg",
            )
    finally:
        await engine.dispose()
