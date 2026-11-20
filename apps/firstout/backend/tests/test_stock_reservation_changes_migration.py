"""The reservation-change trigger marks SKUs under a non-owner runtime role and RLS."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import TenantSession
from f0rge_db.organisation import organisation_session
from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db


async def test_trigger_marks_changes_per_sku_and_rls_isolates_the_marker(second_postgres_url):
    url = second_postgres_url
    migrate(url, "094_personal_mcp_tokens")
    owner = create_async_engine(url)
    runtime = None
    role = "reservation_runtime_" + uuid.uuid4().hex[:10]
    password = "synthetic-" + uuid.uuid4().hex
    a, b, loc_a, sku_1, sku_2, holder = (uuid.uuid4() for _ in range(6))
    try:
        async with owner.begin() as conn:
            await conn.execute(sa.text("ALTER TABLE roles ENABLE ROW LEVEL SECURITY"))
            await conn.execute(sa.text("ALTER TABLE roles FORCE ROW LEVEL SECURITY"))
        migrate(url, "101_stock_reservation_changes")
        async with owner.begin() as conn:
            assert (
                await conn.scalar(
                    sa.text(
                        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                        "WHERE relname='stock_reservation_changes'"
                    )
                )
                is True
            )
            await conn.execute(
                sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))
            await conn.execute(
                sa.text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON stock_reservations, "
                    f"stock_reservation_changes TO {role}"
                )
            )
            for team in (a, b):
                await conn.execute(
                    sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                        VALUES (:id,'Synthetic team',:slug,'active',now(),now())"""),
                    {"id": team, "slug": f"reservation-{team.hex}"},
                )
            await conn.execute(
                sa.text("""INSERT INTO locations(id,team_id,name,type,is_archived,created_at,updated_at)
                    VALUES (:id,:team,'Synthetic showroom','showroom',false,now(),now())"""),
                {"id": loc_a, "team": a},
            )
            for sku in (sku_1, sku_2):
                await conn.execute(
                    sa.text("""INSERT INTO skus(id,team_id,our_ref,our_barcode,name,design,fabric,created_at,updated_at)
                        VALUES (:id,:team,:ref,:ref,'Sku',:ref,'F',now(),now())"""),
                    {"id": sku, "team": a, "ref": f"R-{sku.hex[:8]}"},
                )

        runtime = create_async_engine(make_url(url).set(username=role, password=password))
        maker = async_sessionmaker(
            runtime, expire_on_commit=False, sync_session_class=TenantSession
        )

        async def marks(team: uuid.UUID) -> dict[uuid.UUID, object]:
            async with organisation_session(maker, team) as session:
                rows = await session.execute(
                    sa.text("SELECT sku_id, changed_at FROM stock_reservation_changes")
                )
                return dict(rows.all())

        async with organisation_session(maker, a) as session:
            await session.execute(
                sa.text("""INSERT INTO stock_reservations
                    (id,sku_id,qty,holder_kind,holder_id,location_id)
                    VALUES (gen_random_uuid(),:sku,2,'basket',:holder,:loc)"""),
                {"sku": sku_1, "holder": holder, "loc": loc_a},
            )
            await session.commit()
        created = await marks(a)
        assert set(created) == {sku_1}
        # The marker is tenant-isolated: another company sees nothing.
        assert await marks(b) == {}

        # An update that moves the row to another SKU marks both the old and the new one.
        async with organisation_session(maker, a) as session:
            await session.execute(
                sa.text("UPDATE stock_reservations SET sku_id=:sku WHERE holder_id=:holder"),
                {"sku": sku_2, "holder": holder},
            )
            await session.commit()
        moved = await marks(a)
        assert set(moved) == {sku_1, sku_2}
        assert moved[sku_1] > created[sku_1]

        # A delete (release or prune) marks the SKU and leaves the marker row behind.
        async with organisation_session(maker, a) as session:
            await session.execute(
                sa.text("DELETE FROM stock_reservations WHERE holder_id=:holder"),
                {"holder": holder},
            )
            await session.commit()
        released = await marks(a)
        assert set(released) == {sku_1, sku_2}
        assert released[sku_2] > moved[sku_2]
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
