"""Sales staff are tenant-isolated under a non-owner runtime role, and documents can only
name a colleague of their own organisation."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import TenantSession
from app.schemas.sales_staff import SalesStaffUpdate
from app.services.sales_staff import SalesStaffService
from f0rge_core.exceptions import NotFoundError
from f0rge_db.organisation import organisation_session
from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db


async def test_sales_staff_rls_and_tenant_scoped_document_reference(second_postgres_url):
    url = second_postgres_url
    migrate(url, "103_invoice_notes")
    owner = create_async_engine(url)
    runtime = None
    role = "sales_staff_runtime_" + uuid.uuid4().hex[:10]
    password = "synthetic-" + uuid.uuid4().hex
    a, b, staff_a, customer_b, invoice_b = (uuid.uuid4() for _ in range(5))
    try:
        async with owner.begin() as conn:
            await conn.execute(sa.text("ALTER TABLE roles ENABLE ROW LEVEL SECURITY"))
            await conn.execute(sa.text("ALTER TABLE roles FORCE ROW LEVEL SECURITY"))
        migrate(url, "104_sales_staff_commission")
        async with owner.begin() as conn:
            assert (
                await conn.execute(
                    sa.text("""SELECT c.relrowsecurity, c.relforcerowsecurity, p.polname
                        FROM pg_class c JOIN pg_policy p ON p.polrelid = c.oid
                        WHERE c.relname = 'sales_staff'""")
                )
            ).all() == [(True, True, "organisation_isolation")]
            await conn.execute(
                sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {role}"))
            await conn.execute(
                sa.text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON sales_staff, tax_invoices, quotes "
                    f"TO {role}"
                )
            )
            for team in (a, b):
                await conn.execute(
                    sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                        VALUES (:id,'Synthetic team',:slug,'active',now(),now())"""),
                    {"id": team, "slug": f"sales-staff-{team.hex}"},
                )
            await conn.execute(
                sa.text("""INSERT INTO customers (id,team_id,name,created_at,updated_at)
                    VALUES (:id,:team,'Synthetic customer',now(),now())"""),
                {"id": customer_b, "team": b},
            )
            await conn.execute(
                sa.text("""INSERT INTO tax_invoices
                    (id,team_id,invoice_number,customer_id,issue_date,subtotal_ex_vat,
                     vat_amount,total_inc_vat,amount_paid,created_at,updated_at)
                    VALUES (:id,:team,'INV-B-1',:customer,current_date,100,15,115,0,now(),now())"""),
                {"id": invoice_b, "team": b, "customer": customer_b},
            )

        runtime = create_async_engine(make_url(url).set(username=role, password=password))
        maker = async_sessionmaker(
            runtime, expire_on_commit=False, sync_session_class=TenantSession
        )
        insert = sa.text("""INSERT INTO sales_staff(id,team_id,name,created_at,updated_at)
            VALUES (:id, :team, 'Thandi', now(), now())""")
        async with organisation_session(maker, a) as session:
            await session.execute(insert, {"id": staff_a, "team": a})
            await session.commit()

        async with organisation_session(maker, b) as other:
            # Organisation B neither sees, changes nor removes A's colleague.
            assert await other.scalar(sa.text("SELECT count(*) FROM sales_staff")) == 0
            assert await SalesStaffService(other).list() == []
            with pytest.raises(NotFoundError):
                await SalesStaffService(other).update(staff_a, SalesStaffUpdate(is_active=False))
            with pytest.raises(NotFoundError):
                await SalesStaffService(other).delete(staff_a)
            with pytest.raises(DBAPIError):  # cannot write into another tenant
                async with other.begin_nested():
                    await other.execute(insert, {"id": uuid.uuid4(), "team": a})
            # The composite key refuses a colleague id from another organisation,
            # although a plain foreign key would not see past RLS.
            with pytest.raises(IntegrityError):
                async with other.begin_nested():
                    await other.execute(
                        sa.text("UPDATE tax_invoices SET sales_staff_id=:staff WHERE id=:id"),
                        {"staff": staff_a, "id": invoice_b},
                    )

        async with organisation_session(maker, a) as session:
            staff = await SalesStaffService(session).list()
            assert [(row.id, row.name, row.is_active) for row in staff] == [
                (staff_a, "Thandi", True)
            ]

        await runtime.dispose()
        runtime = None
        async with owner.begin() as conn:
            await conn.execute(
                sa.text("""INSERT INTO books_events
                    (id,team_id,document_type,document_id,action,note,created_at)
                    VALUES (gen_random_uuid(),:team,'invoice',:doc,'updated',
                            'Sales colleague: none → Thandi',now())"""),
                {"team": b, "doc": invoice_b},
            )
        # Additive and reversible: the previous release's schema comes back cleanly,
        # without "updated" events the earlier code cannot read.
        migrate(url, "103_invoice_notes", command="downgrade")
        async with owner.begin() as conn:
            assert await conn.scalar(sa.text("SELECT count(*) FROM books_events")) == 0
        migrate(url, "104_sales_staff_commission")
    finally:
        if runtime is not None:
            await runtime.dispose()
        await owner.dispose()
