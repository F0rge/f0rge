"""The hide-from-shop flag defaults off, bumps the feed revision when toggled and round-trips."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.sku import Sku
from tests.test_fractional_inventory_migration import migrate, seed_old_records

pytestmark = pytest.mark.no_db
PREVIOUS = "109_document_template"
HIDDEN = "110_sku_storefront_hidden"


async def test_storefront_hidden_defaults_off_bumps_updated_at_and_round_trips(
    second_postgres_url,
):
    url = second_postgres_url
    migrate(url, PREVIOUS)
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        _, sku_id, _, _ = await seed_old_records(engine)
        migrate(url, HIDDEN)
        async with engine.connect() as conn:
            column = (
                await conn.execute(
                    sa.text("""SELECT is_nullable, column_default FROM information_schema.columns
                        WHERE table_name='skus' AND column_name='storefront_hidden'""")
                )
            ).one()
            assert column.is_nullable == "NO" and column.column_default == "false"

        # The current ORM includes newer columns. Check the update behavior at its schema head.
        migrate(url, "head")
        # The ops-commerce revision is greatest(Sku.updated_at, ...): a toggle must move it.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            sku = await session.get(Sku, sku_id)
            assert sku is not None and sku.storefront_hidden is False
            before = sku.updated_at
            sku.storefront_hidden = True
            await session.commit()
            assert sku.updated_at > before

        migrate(url, PREVIOUS, command="downgrade")
        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    sa.text("""SELECT count(*) FROM information_schema.columns
                        WHERE table_name='skus' AND column_name='storefront_hidden'""")
                )
                == 0
            )
            assert await conn.scalar(
                sa.text("SELECT count(*) FROM skus WHERE id=:id"), {"id": sku_id}
            )
        migrate(url, HIDDEN)
        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    sa.text("SELECT storefront_hidden FROM skus WHERE id=:id"), {"id": sku_id}
                )
                is False
            )
    finally:
        await engine.dispose()
