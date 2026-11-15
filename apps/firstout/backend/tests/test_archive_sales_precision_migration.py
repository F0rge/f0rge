"""Sales source precision survives real PostgreSQL migrations under FORCE RLS."""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.no_db
BACKEND = Path(__file__).resolve().parents[1]
REVISION = "088_archive_sales_precision"
PREVIOUS = "087_cin7_archive_provenance"
AMOUNT_COLUMNS = (
    ("tax_invoices", "vat_amount"),
    ("tax_invoices", "total_inc_vat"),
    ("invoice_lines", "vat_amount"),
    ("invoice_lines", "inc_vat"),
    ("archive_credit_notes", "vat_amount"),
    ("archive_credit_notes", "total_inc_vat"),
    ("archive_credit_note_lines", "vat_amount"),
    ("archive_credit_note_lines", "inc_vat"),
)
TABLES = tuple(dict.fromkeys(table for table, _column in AMOUNT_COLUMNS))


def migrate(url: str, revision: str, *, downgrade=False, refused=False) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade" if downgrade else "upgrade", revision],
        cwd=BACKEND,
        env={
            **os.environ,
            "DATABASE_URL": url,
            "MIGRATION_DATABASE_URL": url,
            "DIRECT_DATABASE_URL": "",
        },
        capture_output=True,
        text=True,
    )
    if refused:
        assert result.returncode != 0, "Lossy migration unexpectedly succeeded"
        assert "non-cent, nonfinite or out-of-range amounts" in result.stderr
    else:
        assert result.returncode == 0, result.stderr


async def shapes(connection):
    result = {}
    for table, column in AMOUNT_COLUMNS:
        result[(table, column)] = (
            await connection.execute(
                sa.text(
                    "SELECT numeric_precision,numeric_scale,is_nullable "
                    "FROM information_schema.columns WHERE table_schema='public' "
                    "AND table_name=:table AND column_name=:column"
                ),
                {"table": table, "column": column},
            )
        ).one()
    return result


async def source_values(connection, team_id):
    return {
        (table, column): await connection.scalar(
            sa.text(f'SELECT "{column}" FROM "{table}" WHERE team_id=:team'),
            {"team": team_id},
        )
        for table, column in AMOUNT_COLUMNS
    }


async def insert_records(connection, index: int):
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    async def insert(table, *, timestamps=True, **fields):
        fields.setdefault("id", uuid.uuid4())
        if timestamps:
            fields.update(created_at=now, updated_at=now)
        names = ", ".join(fields)
        parameters = ", ".join(":" + name for name in fields)
        await connection.execute(
            sa.text(f'INSERT INTO "{table}" ({names}) VALUES ({parameters})'), fields
        )
        return fields["id"]

    team_id = await insert(
        "teams", name=f"Source precision {index}", slug=f"source-precision-{index}", status="active"
    )
    customer_id = await insert("customers", team_id=team_id, name=f"Source customer {index}")
    invoice_id = await insert(
        "tax_invoices",
        team_id=team_id,
        invoice_number=f"SOURCE-INV-{index}",
        customer_id=customer_id,
        issue_date=datetime.date(2026, 11, 14),
        subtotal_ex_vat=Decimal("100.00"),
        vat_amount=Decimal("15.12"),
        total_inc_vat=Decimal("115.12"),
        amount_paid=Decimal(0),
        is_archive=True,
    )
    await insert(
        "invoice_lines",
        timestamps=False,
        team_id=team_id,
        invoice_id=invoice_id,
        description="Source invoice line",
        qty=1,
        unit_ex_vat=Decimal("100.00"),
        ex_vat=Decimal("100.00"),
        vat_amount=Decimal("15.12"),
        inc_vat=Decimal("115.12"),
        sort_order=0,
    )
    credit_id = await insert(
        "archive_credit_notes",
        team_id=team_id,
        document_number=f"SOURCE-CR-{index}",
        customer_id=customer_id,
        issue_date=datetime.date(2026, 11, 14),
        subtotal_ex_vat=Decimal("-100.00"),
        vat_amount=Decimal("-15.12"),
        total_inc_vat=Decimal("-115.12"),
        source="cin7",
    )
    await insert(
        "archive_credit_note_lines",
        team_id=team_id,
        credit_note_id=credit_id,
        description="Source credit line",
        qty=Decimal(-1),
        ex_vat=Decimal("-100.00"),
        vat_amount=Decimal("-15.12"),
        inc_vat=Decimal("-115.12"),
        sort_order=0,
    )
    return team_id


@pytest_asyncio.fixture
async def precision_database(second_postgres_url):
    migrate(second_postgres_url, PREVIOUS)
    engine = create_async_engine(second_postgres_url, poolclass=NullPool)
    role = "firstout_088_" + uuid.uuid4().hex
    base = make_url(second_postgres_url)
    migration_url = base.set(username=role, password="synthetic-precision-only").render_as_string(
        hide_password=False
    )
    async with engine.begin() as connection:
        first_team = await insert_records(connection, 1)
        second_team = await insert_records(connection, 2)
        before = await source_values(connection, second_team)
    # Commit the deferrable document/line FK checks before changing table ownership.
    async with engine.begin() as connection:
        await connection.execute(
            sa.text(
                f"CREATE ROLE \"{role}\" LOGIN PASSWORD 'synthetic-precision-only' "
                "NOSUPERUSER NOBYPASSRLS"
            )
        )
        await connection.execute(sa.text(f'GRANT USAGE,CREATE ON SCHEMA public TO "{role}"'))
        await connection.execute(sa.text(f'GRANT SELECT,UPDATE ON alembic_version TO "{role}"'))
        await connection.execute(
            sa.text(f'ALTER ROLE "{role}" SET "app.tenant_id" = \'{first_team}\'')
        )
        for table in TABLES:
            await connection.execute(sa.text(f'ALTER TABLE "{table}" OWNER TO "{role}"'))
            await connection.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            await connection.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    migration_engine = create_async_engine(migration_url, poolclass=NullPool)
    try:
        async with migration_engine.connect() as connection:
            role_flags = (
                await connection.execute(
                    sa.text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
                )
            ).one()
            assert role_flags == (False, False)
            for table in TABLES:
                assert await connection.scalar(sa.text(f'SELECT count(*) FROM "{table}"')) == 1
                assert not await connection.scalar(
                    sa.text(f'SELECT EXISTS(SELECT 1 FROM "{table}" WHERE team_id=:team)'),
                    {"team": second_team},
                )
        yield engine, migration_url, second_team, before
    finally:
        await migration_engine.dispose()
        async with engine.begin() as connection:
            for table in TABLES:
                await connection.execute(
                    sa.text(f'ALTER TABLE "{table}" OWNER TO "{base.username}"')
                )
            await connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
            await connection.execute(sa.text(f'DROP ROLE "{role}"'))
        await engine.dispose()


async def test_088_preserves_existing_cents_and_exact_source_precision(precision_database):
    engine, migration_url, second_team, before = precision_database
    async with engine.begin() as connection:
        await connection.execute(
            sa.text("UPDATE tax_invoices SET total_inc_vat=999999999999.99 WHERE team_id=:team"),
            {"team": second_team},
        )
        before = await source_values(connection, second_team)
    migrate(migration_url, REVISION)
    exact = {}
    async with engine.begin() as connection:
        assert all(row == (16, 4, "NO") for row in (await shapes(connection)).values())
        assert await source_values(connection, second_team) == before
        for table, column in AMOUNT_COLUMNS:
            amount = Decimal("15.1234") if column == "vat_amount" else Decimal("115.1234")
            if table.startswith("archive_credit"):
                amount = -amount
            exact[(table, column)] = amount
            await connection.execute(
                sa.text(f'UPDATE "{table}" SET "{column}"=:amount WHERE team_id=:team'),
                {"amount": amount, "team": second_team},
            )
    async with engine.connect() as connection:
        values = await source_values(connection, second_team)
        assert values == exact
        assert all(value.as_tuple().exponent == -4 for value in values.values())
        assert values[("tax_invoices", "vat_amount")] == Decimal("15.1234")
        assert values[("archive_credit_note_lines", "inc_vat")] == Decimal("-115.1234")
    # Clear only source sub-cent precision; an exact-cent rollback is then safe.
    async with engine.begin() as connection:
        for table, column in AMOUNT_COLUMNS:
            await connection.execute(
                sa.text(f'UPDATE "{table}" SET "{column}"=:value WHERE team_id=:team'),
                {"value": before[(table, column)], "team": second_team},
            )
    migrate(migration_url, PREVIOUS, downgrade=True)
    async with engine.connect() as connection:
        assert all(row == (14, 2, "NO") for row in (await shapes(connection)).values())
        assert await source_values(connection, second_team) == before
        assert not await connection.scalar(
            sa.text("SELECT EXISTS(SELECT 1 FROM pg_policy WHERE polname='migration_bypass')")
        )
    migrate(migration_url, REVISION)


@pytest.mark.parametrize("table,column", AMOUNT_COLUMNS)
async def test_088_non_cent_hidden_tenant_refuses_lossy_downgrade(
    precision_database, table, column
):
    engine, migration_url, second_team, before = precision_database
    migrate(migration_url, REVISION)
    async with engine.begin() as connection:
        await connection.execute(
            sa.text(f'UPDATE "{table}" SET "{column}"=0.0001 WHERE team_id=:team'),
            {"team": second_team},
        )
        expected = await source_values(connection, second_team)
    migrate(migration_url, PREVIOUS, downgrade=True, refused=True)
    async with engine.connect() as connection:
        assert all(row == (16, 4, "NO") for row in (await shapes(connection)).values())
        assert await source_values(connection, second_team) == expected
        assert expected[(table, column)] == Decimal("0.0001")
        assert (
            await connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
        )
        assert not await connection.scalar(
            sa.text("SELECT EXISTS(SELECT 1 FROM pg_policy WHERE polname='migration_bypass')")
        )
        assert len(before) == 8


async def test_088_nonfinite_source_value_refuses_downgrade(precision_database):
    engine, migration_url, second_team, _before = precision_database
    migrate(migration_url, REVISION)
    async with engine.begin() as connection:
        await connection.execute(
            sa.text(
                "UPDATE archive_credit_note_lines SET inc_vat='NaN'::numeric WHERE team_id=:team"
            ),
            {"team": second_team},
        )
    migrate(migration_url, PREVIOUS, downgrade=True, refused=True)
    async with engine.connect() as connection:
        assert all(row == (16, 4, "NO") for row in (await shapes(connection)).values())
        assert (
            await connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
        )
        assert (
            str(
                await connection.scalar(
                    sa.text("SELECT inc_vat FROM archive_credit_note_lines WHERE team_id=:team"),
                    {"team": second_team},
                )
            )
            == "NaN"
        )
