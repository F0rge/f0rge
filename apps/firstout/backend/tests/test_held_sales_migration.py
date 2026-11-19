"""Check held-basket schema and locking under a non-owner PostgreSQL runtime role."""

from __future__ import annotations

import asyncio
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.crud.held_sale import HeldSaleCRUD
from app.database import TenantSession
from app.models.held_sale import HeldSale
from app.models.held_sale_operation import HeldSaleOperation
from app.models.location import Location
from app.schemas.held_sale import HeldSaleResume
from app.services.held_sale import HeldSaleService
from f0rge_core.exceptions import ConflictError
from f0rge_db.organisation import organisation_session
from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db


async def test_migrated_held_sales_respect_rls_and_serialize_concurrent_consumption(
    second_postgres_url,
):
    url = second_postgres_url
    migrate(url, "094_personal_mcp_tokens")
    owner = create_async_engine(url)
    runtime = None
    role = "held_sales_runtime_" + uuid.uuid4().hex[:10]
    password = "synthetic-" + uuid.uuid4().hex
    a, b, showroom_a, showroom_b, sku, held_id = (uuid.uuid4() for _ in range(6))
    try:
        async with owner.begin() as conn:
            await conn.execute(sa.text("ALTER TABLE roles ENABLE ROW LEVEL SECURITY"))
            await conn.execute(sa.text("ALTER TABLE roles FORCE ROW LEVEL SECURITY"))
        migrate(url, "095_till_held_sales")
        async with owner.begin() as conn:
            protected = (
                await conn.execute(
                    sa.text("""
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, p.polname
                FROM pg_class c JOIN pg_policy p ON p.polrelid = c.oid
                WHERE c.relname IN ('held_sales', 'held_sale_operations')
                ORDER BY c.relname
            """)
                )
            ).all()
            assert protected == [
                ("held_sale_operations", True, True, "organisation_isolation"),
                ("held_sales", True, True, "organisation_isolation"),
            ]
            await conn.execute(
                sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))
            await conn.execute(
                sa.text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON held_sales, held_sale_operations TO {role}"
                )
            )
            await conn.execute(
                sa.text(f"GRANT SELECT, UPDATE ON locations, skus, customers TO {role}")
            )
            for team, location in ((a, showroom_a), (b, showroom_b)):
                await conn.execute(
                    sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                        VALUES (:id,'Synthetic showroom team',:slug,'active',now(),now())"""),
                    {"id": team, "slug": f"held-sales-{team.hex}"},
                )
                await conn.execute(
                    sa.text("""INSERT INTO locations(id,team_id,name,type,is_archived,created_at,updated_at)
                        VALUES (:id,:team,'Synthetic showroom','showroom',false,now(),now())"""),
                    {"id": location, "team": team},
                )
            await conn.execute(
                sa.text("""INSERT INTO skus(id,team_id,our_ref,our_barcode,name,design,fabric,created_at,updated_at)
                    VALUES (:id,:team,'LOCK-SKU','LOCK-SKU','Lock SKU','Lock','Demo',now(),now())"""),
                {"id": sku, "team": a},
            )
            row = {
                "id": held_id,
                "team_id": a,
                "location_id": showroom_a,
                "customer_name": "Walk-in customer",
                "held_by_name": "Synthetic cashier",
                "linked_pick_ids": {},
                "lines": [
                    {
                        "sku_id": str(sku),
                        "qty": 1,
                        "discount_percent": "0",
                        "sku_name": "Lock SKU",
                        "sku_code": "LOCK-SKU",
                    }
                ],
            }
            await conn.execute(sa.insert(HeldSale), row)
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await conn.execute(
                        sa.insert(HeldSale), {**row, "id": uuid.uuid4(), "location_id": showroom_b}
                    )

        runtime = create_async_engine(make_url(url).set(username=role, password=password))
        maker = async_sessionmaker(
            runtime, expire_on_commit=False, sync_session_class=TenantSession
        )
        async with organisation_session(maker, b) as other:
            # Raw SQL bypasses ORM tenant filters. The database must still hide the basket.
            assert await other.scalar(sa.text("SELECT count(*) FROM held_sales")) == 0
            assert await HeldSaleCRUD(other).showroom(showroom_a) is None

        async with organisation_session(maker, a) as first:
            async with organisation_session(maker, a) as second:
                assert await HeldSaleCRUD(first).showroom(showroom_a, lock=True)
                # The showroom lock is compatible with a foreign-key key-share lock.
                key_share = sa.select(Location.id).where(Location.id == showroom_a)
                assert await second.scalar(key_share.with_for_update(read=True, key_share=True))
                await second.execute(sa.text("SET LOCAL lock_timeout = '100ms'"))
                with pytest.raises(DBAPIError) as error:
                    await HeldSaleCRUD(second).showroom(showroom_a, lock=True)
                assert error.value.orig.sqlstate == "55P03"

        async def consume(actor: uuid.UUID):
            request = HeldSaleResume(location_id=showroom_a, operation_id=uuid.uuid4(), version=1)
            async with organisation_session(maker, a) as session:
                return await HeldSaleService(session).resume(held_id, request, actor)

        results = await asyncio.gather(
            consume(uuid.uuid4()), consume(uuid.uuid4()), return_exceptions=True
        )
        assert sum(isinstance(result, ConflictError) for result in results) == 1
        assert sum(getattr(result, "resumed_id", None) == held_id for result in results) == 1
        async with organisation_session(maker, a) as session:
            assert await session.scalar(sa.text("SELECT count(*) FROM held_sales")) == 0
            assert len(list(await session.scalars(sa.select(HeldSaleOperation)))) == 1
        async with organisation_session(maker, b) as session:
            assert await session.scalar(sa.text("SELECT count(*) FROM held_sale_operations")) == 0
    finally:
        if runtime is not None:
            await runtime.dispose()
        async with owner.begin() as conn:
            if await conn.scalar(
                sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}
            ):
                await conn.execute(sa.text(f"DROP OWNED BY {role}"))
                await conn.execute(sa.text(f"DROP ROLE {role}"))
        await owner.dispose()
