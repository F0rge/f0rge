"""Check the till_baskets table is tenant-isolated under a non-owner runtime role."""

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


async def test_migrated_till_baskets_respect_rls_and_one_basket_per_user(second_postgres_url):
    url = second_postgres_url
    migrate(url, "097_till_hold_hours")
    owner = create_async_engine(url)
    runtime = None
    role = "till_baskets_runtime_" + uuid.uuid4().hex[:10]
    password = "synthetic-" + uuid.uuid4().hex
    a, b, showroom_a, showroom_b, user_a = (uuid.uuid4() for _ in range(5))
    try:
        async with owner.begin() as conn:
            await conn.execute(sa.text("ALTER TABLE roles ENABLE ROW LEVEL SECURITY"))
            await conn.execute(sa.text("ALTER TABLE roles FORCE ROW LEVEL SECURITY"))
        migrate(url, "098_till_baskets")
        async with owner.begin() as conn:
            assert (
                await conn.execute(
                    sa.text("""SELECT c.relrowsecurity, c.relforcerowsecurity, p.polname
                        FROM pg_class c JOIN pg_policy p ON p.polrelid = c.oid
                        WHERE c.relname = 'till_baskets'""")
                )
            ).all() == [(True, True, "organisation_isolation")]
            await conn.execute(
                sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))
            await conn.execute(
                sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON till_baskets TO {role}")
            )
            for team, location in ((a, showroom_a), (b, showroom_b)):
                await conn.execute(
                    sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                        VALUES (:id,'Synthetic showroom team',:slug,'active',now(),now())"""),
                    {"id": team, "slug": f"till-baskets-{team.hex}"},
                )
                await conn.execute(
                    sa.text("""INSERT INTO locations(id,team_id,name,type,is_archived,created_at,updated_at)
                        VALUES (:id,:team,'Synthetic showroom','showroom',false,now(),now())"""),
                    {"id": location, "team": team},
                )
            await conn.execute(
                sa.text("""INSERT INTO users(id,team_id,email,password_hash,display_name,role,created_at,updated_at)
                    VALUES (:id,:team,'cashier@example.com','x','Cashier','till',now(),now())"""),
                {"id": user_a, "team": a},
            )

        runtime = create_async_engine(make_url(url).set(username=role, password=password))
        maker = async_sessionmaker(
            runtime, expire_on_commit=False, sync_session_class=TenantSession
        )
        insert = sa.text("""INSERT INTO till_baskets(id,team_id,location_id,user_id,linked_pick_ids,lines)
            VALUES (gen_random_uuid(), :team, :location, :user, '{}', '[]')""")
        params = {"team": a, "location": showroom_a, "user": user_a}
        async with organisation_session(maker, a) as session:
            await session.execute(insert, params)
            with pytest.raises(IntegrityError):  # one basket per user per showroom
                async with session.begin_nested():
                    await session.execute(insert, params)
        async with organisation_session(maker, b) as other:
            assert await other.scalar(sa.text("SELECT count(*) FROM till_baskets")) == 0
            with pytest.raises(sa.exc.DBAPIError):  # cannot write into another tenant
                async with other.begin_nested():
                    await other.execute(insert, params)
    finally:
        if runtime is not None:
            await runtime.dispose()
        await owner.dispose()
