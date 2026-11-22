"""113 gives every sale document a NOT NULL vat_rate; existing rows read 0.15 (they were all
computed at the old hard-coded 1.15), even under forced RLS on a non-superuser owner."""

from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db
PREVIOUS = "113_sale_line_discount"
VAT_RATE = "114_sale_document_vat_rate"
TABLES = ("credit_notes", "laybys", "quotes", "sales_orders", "tax_invoices")
COLUMNS = sa.text("""SELECT table_name, is_nullable, numeric_precision, numeric_scale
    FROM information_schema.columns WHERE column_name = 'vat_rate'
    AND table_name IN ('tax_invoices', 'credit_notes', 'quotes', 'sales_orders', 'laybys')
    ORDER BY table_name""")


async def test_vat_rate_columns_backfill_under_forced_rls(second_postgres_url):
    url = second_postgres_url
    migrate(url, PREVIOUS)
    admin = create_async_engine(url)
    owner = "vat_rate_migration_owner_" + uuid.uuid4().hex[:8]
    password = "synthetic-" + uuid.uuid4().hex
    team, customer, invoice = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        async with admin.begin() as conn:
            await conn.execute(
                sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                    VALUES (:id,'Synthetic VAT team',:slug,'active',now(),now())"""),
                {"id": team, "slug": f"vat-{team.hex}"},
            )
            await conn.execute(
                sa.text("""INSERT INTO customers(id,team_id,name,created_at,updated_at)
                    VALUES (:id,:team,'Synthetic VAT customer',now(),now())"""),
                {"id": customer, "team": team},
            )
            await conn.execute(
                sa.text("""INSERT INTO tax_invoices(id,team_id,invoice_number,customer_id,
                    issue_date,subtotal_ex_vat,vat_amount,total_inc_vat,amount_paid,
                    created_at,updated_at)
                    VALUES (:id,:team,'INV-VAT-1',:customer,:day,100,15,115,0,now(),now())"""),
                {"id": invoice, "team": team, "customer": customer, "day": datetime.date.today()},
            )
        async with admin.begin() as conn:
            await conn.execute(
                sa.text(f"CREATE ROLE {owner} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT CREATE, USAGE ON SCHEMA public TO {owner}"))
            await conn.execute(sa.text(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {owner}"))
            for table in (*TABLES, "alembic_version"):
                await conn.execute(sa.text(f"ALTER TABLE {table} OWNER TO {owner}"))
            for table in TABLES:
                await conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
                await conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

        migrate(
            make_url(url).set(username=owner, password=password).render_as_string(False),
            VAT_RATE,
        )
        async with admin.connect() as conn:
            assert (await conn.execute(COLUMNS)).all() == [(table, "NO", 5, 4) for table in TABLES]
            stored = await conn.scalar(
                sa.text("SELECT vat_rate FROM tax_invoices WHERE id = :id"), {"id": invoice}
            )
        assert str(stored) == "0.1500"

        migrate(url, PREVIOUS, command="downgrade")
        async with admin.connect() as conn:
            assert (await conn.execute(COLUMNS)).all() == []
    finally:
        await admin.dispose()
