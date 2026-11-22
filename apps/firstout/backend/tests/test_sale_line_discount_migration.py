"""112 adds nullable line discounts and grants till.discount to every team's built-in warehouse
role, under forced RLS on a non-superuser owner, leaving custom roles alone."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db
PREVIOUS = "112_sale_line_unit_cost"
DISCOUNT = "113_sale_line_discount"
COLUMNS = sa.text("""SELECT table_name, is_nullable, numeric_precision, numeric_scale
    FROM information_schema.columns WHERE column_name = 'discount_percent'
    AND table_name IN ('invoice_lines', 'sales_order_lines') ORDER BY table_name""")
GRANTS = sa.text("""SELECT r.team_id, r.slug FROM role_permissions p JOIN roles r ON r.id = p.role_id
    WHERE p.key = 'till.discount' ORDER BY r.slug, r.team_id""")


async def test_columns_and_warehouse_grant_under_forced_rls(second_postgres_url):
    url = second_postgres_url
    migrate(url, PREVIOUS)
    admin = create_async_engine(url)
    owner = "discount_migration_owner_" + uuid.uuid4().hex[:8]
    password = "synthetic-" + uuid.uuid4().hex
    teams = sorted([uuid.uuid4(), uuid.uuid4()])
    try:
        async with admin.begin() as conn:
            for team in teams:
                await conn.execute(
                    sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                        VALUES (:id,'Synthetic discount team',:slug,'active',now(),now())"""),
                    {"id": team, "slug": f"discount-{team.hex}"},
                )
                for slug, system in (("warehouse", True), ("warehouse-desk", False)):
                    await conn.execute(
                        sa.text("""INSERT INTO roles(id,team_id,slug,name,is_system,
                            is_owner_preset,created_at,updated_at)
                            VALUES (:id,:team,:slug,:slug,:system,false,now(),now())"""),
                        {"id": uuid.uuid4(), "team": team, "slug": slug, "system": system},
                    )
            # Already granted in one team: the migration must not duplicate it.
            await conn.execute(
                sa.text("""INSERT INTO role_permissions(team_id, role_id, key)
                    SELECT team_id, id, 'till.discount' FROM roles
                    WHERE team_id = :team AND slug = 'warehouse'"""),
                {"team": teams[0]},
            )
        async with admin.begin() as conn:
            await conn.execute(
                sa.text(f"CREATE ROLE {owner} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT CREATE, USAGE ON SCHEMA public TO {owner}"))
            await conn.execute(sa.text(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {owner}"))
            for table in (
                "roles",
                "role_permissions",
                "invoice_lines",
                "sales_order_lines",
                "alembic_version",
            ):
                await conn.execute(sa.text(f"ALTER TABLE {table} OWNER TO {owner}"))
            for table in ("roles", "role_permissions"):
                await conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
                await conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

        migrate(
            make_url(url).set(username=owner, password=password).render_as_string(False),
            DISCOUNT,
        )
        async with admin.connect() as conn:
            assert (await conn.execute(COLUMNS)).all() == [
                ("invoice_lines", "YES", 5, 2),
                ("sales_order_lines", "YES", 5, 2),
            ]
            granted = (await conn.execute(GRANTS)).all()
        # Each synthetic team's built-in warehouse role, once; never the custom role.
        assert [(team, "warehouse") for team in teams] == [
            row for row in granted if row[0] in teams
        ]

        migrate(url, PREVIOUS, command="downgrade")
        async with admin.connect() as conn:
            assert (await conn.execute(COLUMNS)).all() == []
            assert [row for row in (await conn.execute(GRANTS)).all() if row[0] in teams] == []
    finally:
        await admin.dispose()
