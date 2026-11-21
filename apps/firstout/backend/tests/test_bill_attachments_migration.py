"""107 backfills every team's bills even when RLS is forced on its non-superuser owner."""

from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db

ISSUE = datetime.date(2026, 3, 1)


async def test_backfill_reaches_each_team_under_forced_rls(second_postgres_url):
    url = second_postgres_url
    migrate(url, "106_payment_reference_void")
    admin = create_async_engine(url)
    role = "bill_migration_owner_" + uuid.uuid4().hex[:10]
    password = "synthetic-" + uuid.uuid4().hex
    teams = [uuid.uuid4(), uuid.uuid4()]
    bills = {team: (uuid.uuid4(), uuid.uuid4()) for team in teams}
    try:
        async with admin.begin() as conn:
            for team in teams:
                supplier = uuid.uuid4()
                await conn.execute(
                    sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                        VALUES (:id,'Synthetic bill team',:slug,'active',now(),now())"""),
                    {"id": team, "slug": f"bills-{team.hex}"},
                )
                await conn.execute(
                    sa.text("""INSERT INTO suppliers(id,team_id,name,default_currency,created_at,updated_at)
                        VALUES (:id,:team,'Synthetic supplier','ZAR',now(),now())"""),
                    {"id": supplier, "team": team},
                )
                with_file, without_file = bills[team]
                for bill, key in (
                    (with_file, f"tenants/{team}/bills/{with_file}.png"),
                    (without_file, None),
                ):
                    await conn.execute(
                        sa.text("""INSERT INTO bills(id,team_id,bill_number,supplier_id,supplier_ref,
                            issue_date,currency,fx_to_zar,amount_foreign,amount_zar,amount_paid_zar,
                            amount_paid_foreign,payment_status,pdf_storage_key,created_at,updated_at)
                            VALUES (:id,:team,:number,:supplier,:number,:issue,'ZAR',1,100,100,0,0,
                            'unpaid',:key,now(),now())"""),
                        {
                            "id": bill,
                            "team": team,
                            "number": "BILL-" + bill.hex[:6],
                            "supplier": supplier,
                            "issue": ISSUE,
                            "key": key,
                        },
                    )
        # The release migrates as the table owner, not a superuser, with RLS forced.
        async with admin.begin() as conn:
            await conn.execute(
                sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT CREATE, USAGE ON SCHEMA public TO {role}"))
            await conn.execute(sa.text(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {role}"))
            for table in ("bills", "alembic_version"):
                await conn.execute(sa.text(f"ALTER TABLE {table} OWNER TO {role}"))
            for table in ("bills", "roles"):
                await conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
                await conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

        owner_url = make_url(url).set(username=role, password=password)
        migrate(owner_url.render_as_string(hide_password=False), "107_bill_approval_attachments")

        async with admin.begin() as conn:
            assert (
                await conn.execute(
                    sa.text("""SELECT c.relrowsecurity, c.relforcerowsecurity, p.polname
                        FROM pg_class c JOIN pg_policy p ON p.polrelid = c.oid
                        WHERE c.relname = 'bill_attachments'""")
                )
            ).all() == [(True, True, "organisation_isolation")]
            bill_fk = await conn.scalar(
                sa.text("""SELECT pg_get_constraintdef(oid) FROM pg_constraint
                    WHERE conname = 'fk_bill_attachments_bill_tenant'""")
            )
            assert bill_fk.startswith(
                "FOREIGN KEY (team_id, bill_id) REFERENCES bills(team_id, id)"
            )
            rows = (
                await conn.execute(
                    sa.text("SELECT id, due_date, approval_status FROM bills ORDER BY id")
                )
            ).all()
            assert len(rows) == 4
            assert {(due, status) for _, due, status in rows} == {
                (ISSUE + datetime.timedelta(days=30), "approved")
            }
            attachments = (
                await conn.execute(
                    sa.text("""SELECT team_id, bill_id, filename, content_type, storage_key
                        FROM bill_attachments""")
                )
            ).all()
        # One copy per bill with a file, in its own team, never duplicated across teams.
        assert sorted(attachments) == sorted(
            (
                team,
                bills[team][0],
                f"BILL-{bills[team][0].hex[:6]}.png",
                "image/png",
                f"tenants/{team}/bills/{bills[team][0]}.png",
            )
            for team in teams
        )
    finally:
        await admin.dispose()
