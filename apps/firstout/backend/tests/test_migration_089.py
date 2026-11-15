"""Both deployed migration branches reach one head without losing their data."""

from __future__ import annotations

import ipaddress
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.test_fractional_inventory_migration import migrate, seed_old_records

pytestmark = pytest.mark.no_db
HEAD = "089_merge_record_workspaces"


def test_migration_graph_has_one_merge_head_with_both_existing_parents():
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == [HEAD]
    assert scripts.get_revision(HEAD).down_revision == (
        "088_archive_sales_precision",
        "085_record_workspaces",
    )


@pytest.mark.parametrize(
    "starting_revision",
    ["083_portal_clerk_identity", "088_archive_sales_precision", "085_record_workspaces"],
)
async def test_existing_branches_merge_without_data_or_isolation_loss(
    second_postgres_url, starting_revision
):
    migrate(second_postgres_url, starting_revision)
    engine = create_async_engine(second_postgres_url, poolclass=NullPool)
    try:
        team, sku, stock, line = await seed_old_records(engine)
        async with engine.begin() as conn:
            # Existing enforced installations must inherit RLS for the new
            # workspace receipt table whichever branch Alembic applies first.
            await conn.execute(sa.text("ALTER TABLE roles ENABLE ROW LEVEL SECURITY"))
            await conn.execute(sa.text("ALTER TABLE roles FORCE ROW LEVEL SECURITY"))
            if starting_revision == "085_record_workspaces":
                await conn.execute(
                    sa.text("UPDATE price_lists SET is_archived=true WHERE team_id=:team"),
                    {"team": team},
                )
            if starting_revision == "088_archive_sales_precision":
                await conn.execute(
                    sa.text("UPDATE location_stock SET on_hand=0.1250 WHERE id=:id"),
                    {"id": stock},
                )
        migrate(second_postgres_url, "head")
        async with engine.connect() as conn:
            assert list(await conn.scalars(sa.text("SELECT version_num FROM alembic_version"))) == [
                HEAD
            ]
            assert (
                await conn.scalar(
                    sa.text("SELECT count(*) FROM skus WHERE id=:id AND team_id=:team"),
                    {"id": sku, "team": team},
                )
                == 1
            )
            assert await conn.scalar(
                sa.text("SELECT on_hand FROM location_stock WHERE id=:id"), {"id": stock}
            ) == (Decimal("0.1250") if starting_revision == "088_archive_sales_precision" else 2)
            assert (
                await conn.scalar(sa.text("SELECT qty FROM bill_lines WHERE id=:id"), {"id": line})
                == 2
            )
            for table in ("proformas", "price_lists"):
                assert (
                    await conn.scalar(
                        sa.text("""SELECT is_nullable FROM information_schema.columns
                    WHERE table_name=:table AND column_name='is_archived'"""),
                        {"table": table},
                    )
                    == "NO"
                )
            assert await conn.scalar(sa.text("SELECT to_regclass('record_workspace_batches')"))
            flags = (
                await conn.execute(
                    sa.text("""SELECT relrowsecurity,relforcerowsecurity
                FROM pg_class WHERE oid='record_workspace_batches'::regclass""")
                )
            ).one()
            # The workspace branch was already applied before the test enabled
            # roles RLS in this case; the merge must not change its prior stage.
            assert tuple(flags) == (
                (False, False) if starting_revision == "085_record_workspaces" else (True, True)
            )
            for table, column, scale in (
                ("location_stock", "on_hand", 4),
                ("invoice_lines", "vat_amount", 4),
            ):
                assert (
                    await conn.scalar(
                        sa.text("""SELECT numeric_scale FROM information_schema.columns
                    WHERE table_name=:table AND column_name=:column"""),
                        {"table": table, "column": column},
                    )
                    == scale
                )
            # Read real PostgreSQL's inet representation. The release probe
            # needs host(inet) for both IPv4 and IPv6; strict IP parsing remains.
            address = await conn.scalar(sa.text("SELECT host(inet_server_addr())"))
            assert ipaddress.ip_address(address)
        migrate(second_postgres_url, "head")
    finally:
        await engine.dispose()
