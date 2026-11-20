"""Check stock_reservations is tenant-isolated and constrained under a non-owner runtime role."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import TenantSession
from f0rge_db.organisation import organisation_session
from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db


async def test_migrated_reservations_respect_rls_and_constraints(second_postgres_url):
    url = second_postgres_url
    migrate(url, "098_till_baskets")
    owner = create_async_engine(url)
    runtime = None
    role = "reservations_runtime_" + uuid.uuid4().hex[:10]
    password = "synthetic-" + uuid.uuid4().hex
    a, b, showroom_a, sku_a, holder = (uuid.uuid4() for _ in range(5))
    try:
        async with owner.begin() as conn:
            await conn.execute(sa.text("ALTER TABLE roles ENABLE ROW LEVEL SECURITY"))
            await conn.execute(sa.text("ALTER TABLE roles FORCE ROW LEVEL SECURITY"))
        migrate(url, "099_stock_reservations")
        async with owner.begin() as conn:
            assert (
                await conn.execute(
                    sa.text("""SELECT c.relrowsecurity, c.relforcerowsecurity, p.polname
                        FROM pg_class c JOIN pg_policy p ON p.polrelid = c.oid
                        WHERE c.relname = 'stock_reservations'""")
                )
            ).all() == [(True, True, "organisation_isolation")]
            await conn.execute(
                sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))
            await conn.execute(
                sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON stock_reservations TO {role}")
            )
            for team in (a, b):
                await conn.execute(
                    sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                        VALUES (:id,'Synthetic reservation team',:slug,'active',now(),now())"""),
                    {"id": team, "slug": f"reservations-{team.hex}"},
                )
            await conn.execute(
                sa.text("""INSERT INTO locations(id,team_id,name,type,is_archived,created_at,updated_at)
                    VALUES (:id,:team,'Synthetic showroom','showroom',false,now(),now())"""),
                {"id": showroom_a, "team": a},
            )
            await conn.execute(
                sa.text("""INSERT INTO skus(id,team_id,our_ref,our_barcode,name,design,fabric,created_at,updated_at)
                    VALUES (:id,:team,'RES-1','RES-1','Synthetic','d','f',now(),now())"""),
                {"id": sku_a, "team": a},
            )

        runtime = create_async_engine(make_url(url).set(username=role, password=password))
        maker = async_sessionmaker(
            runtime, expire_on_commit=False, sync_session_class=TenantSession
        )
        insert = sa.text("""INSERT INTO stock_reservations
            (id,team_id,sku_id,qty,holder_kind,holder_id,location_id,expires_at)
            VALUES (gen_random_uuid(), :team, :sku, :qty, :kind, :holder, :location, NULL)""")
        params = {
            "team": a,
            "sku": sku_a,
            "qty": 1,
            "kind": "basket",
            "holder": holder,
            "location": showroom_a,
        }
        async with organisation_session(maker, a) as session:
            await session.execute(insert, params)
            for bad in (
                params,  # one row per SKU per holder
                {**params, "holder": uuid.uuid4(), "qty": 0},
                {**params, "holder": uuid.uuid4(), "kind": "cart"},
            ):
                with pytest.raises(IntegrityError):
                    async with session.begin_nested():
                        await session.execute(insert, bad)
        async with organisation_session(maker, b) as other:
            assert await other.scalar(sa.text("SELECT count(*) FROM stock_reservations")) == 0
            with pytest.raises(sa.exc.DBAPIError):  # cannot write into another tenant
                async with other.begin_nested():
                    await other.execute(insert, {**params, "holder": uuid.uuid4()})
    finally:
        if runtime is not None:
            await runtime.dispose()
        await owner.dispose()
