"""Run the real migration chain and preserve old records through an archive round trip."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.no_db
BACKEND = Path(__file__).resolve().parents[1]


def migrate(url: str, target: str, command: str = "upgrade") -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", command, target],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": url, "MIGRATION_DATABASE_URL": url},
        check=True,
        capture_output=True,
        text=True,
    )


async def test_party_archive_migration_preserves_records_defaults_and_indexes(second_postgres_url):
    url = second_postgres_url
    migrate(url, "083_portal_clerk_identity")
    engine = create_async_engine(url)
    team_id, customer_id, supplier_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    "INSERT INTO teams (id,name,slug,status,created_at,updated_at) VALUES (:id,'Archive migration','archive-migration','active',now(),now())"
                ),
                {"id": team_id},
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO customers (id,team_id,name,email,created_at,updated_at) VALUES (:id,:team,'Archive migration customer','archive-history@example.com',now(),now())"
                ),
                {"id": customer_id, "team": team_id},
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO suppliers (id,team_id,name,default_currency,created_at,updated_at) VALUES (:id,:team,'Archive migration supplier','USD',now(),now())"
                ),
                {"id": supplier_id, "team": team_id},
            )
        migrate(url, "084_party_archives")
        async with engine.begin() as conn:
            for table, party_id in (("customers", customer_id), ("suppliers", supplier_id)):
                record = (
                    await conn.execute(
                        sa.text(f"SELECT id,team_id,name,is_archived FROM {table} WHERE id=:id"),
                        {"id": party_id},
                    )
                ).one()
                assert record.id == party_id and record.team_id == team_id
                assert record.name.startswith("Archive migration") and record.is_archived is False
                index_def = await conn.scalar(
                    sa.text("SELECT indexdef FROM pg_indexes WHERE indexname=:name"),
                    {"name": f"ix_{table}_team_id_is_archived"},
                )
                assert "(team_id, is_archived)" in index_def
                new_id = uuid.uuid4()
                columns = "id,team_id,name,created_at,updated_at"
                values = ":id,:team,:name,now(),now()"
                if table == "suppliers":
                    columns += ",default_currency"
                    values += ",'USD'"
                inserted = await conn.scalar(
                    sa.text(
                        f"INSERT INTO {table} ({columns}) VALUES ({values}) RETURNING is_archived"
                    ),
                    {"id": new_id, "team": team_id, "name": f"Archive default {table}"},
                )
                assert inserted is False
                await conn.execute(
                    sa.text(f"UPDATE {table} SET is_archived=true WHERE id=:id"), {"id": party_id}
                )
        migrate(url, "083_portal_clerk_identity", "downgrade")
        async with engine.connect() as conn:
            for table in ("customers", "suppliers"):
                assert (
                    await conn.scalar(
                        sa.text(f"SELECT count(*) FROM {table} WHERE team_id=:team"),
                        {"team": team_id},
                    )
                    == 2
                )
                assert (
                    await conn.scalar(
                        sa.text(
                            "SELECT count(*) FROM information_schema.columns WHERE table_name=:table AND column_name='is_archived'"
                        ),
                        {"table": table},
                    )
                    == 0
                )
        migrate(url, "084_party_archives")
        async with engine.connect() as conn:
            for table in ("customers", "suppliers"):
                assert (
                    await conn.scalar(
                        sa.text(
                            f"SELECT count(*) FROM {table} WHERE team_id=:team AND is_archived=false"
                        ),
                        {"team": team_id},
                    )
                    == 2
                )
    finally:
        await engine.dispose()
