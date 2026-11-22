from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.test_fractional_inventory_migration import migrate, seed_old_records


pytestmark = pytest.mark.no_db
PREVIOUS = "110_sku_storefront_hidden"
CURATED = "111_sku_curated_catalogue"


async def test_existing_catalogue_survives_curated_schema_upgrade_and_downgrade(
    second_postgres_url: str,
) -> None:
    migrate(second_postgres_url, PREVIOUS)
    engine = create_async_engine(second_postgres_url, poolclass=NullPool)
    try:
        team_id, sku_id, _, _ = await seed_old_records(engine)
        migrate(second_postgres_url, CURATED)
        async with engine.connect() as conn:
            team = await conn.scalar(
                sa.text("SELECT storefront_curated_catalogue FROM teams WHERE id = :id"),
                {"id": team_id},
            )
            sku = (
                await conn.execute(
                    sa.text(
                        "SELECT storefront_catalogue_selected, width_cm, notes, piece_count, "
                        "gallery_photo_keys FROM skus WHERE id = :id"
                    ),
                    {"id": sku_id},
                )
            ).one()
            assert team is False
            assert tuple(sku) == (False, None, None, None, None)
        for field in ("width_cm", "depth_cm", "height_cm", "diameter_cm", "piece_count"):
            with pytest.raises(IntegrityError):
                async with engine.begin() as conn:
                    await conn.execute(
                        sa.text(f"UPDATE skus SET {field} = 0 WHERE id = :id"), {"id": sku_id}
                    )
        migrate(second_postgres_url, PREVIOUS, command="downgrade")
        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    sa.text("SELECT COUNT(*) FROM skus WHERE id = :id"), {"id": sku_id}
                )
                == 1
            )
    finally:
        await engine.dispose()
