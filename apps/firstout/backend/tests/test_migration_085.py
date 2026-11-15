"""Exercise the real archive/batch migration with retained links and a nonowner role."""

from __future__ import annotations

import json
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


@pytest.mark.parametrize("already_enforced", [False, True])
async def test_workspace_migration_retains_links_receipts_and_tenant_isolation(
    second_postgres_url: str, already_enforced: bool
) -> None:
    url = second_postgres_url
    migrate(url, "084_party_archives")
    engine = create_async_engine(url)
    team_a, team_b, actor, price_list, customer, supplier, proforma, po = (
        uuid.uuid4() for _ in range(8)
    )
    request_id = uuid.uuid4()
    role = "fo_workspace_test_" + uuid.uuid4().hex[:12]
    role_created = False
    try:
        async with engine.begin() as conn:
            for team, slug in ((team_a, "workspace-a"), (team_b, "workspace-b")):
                await conn.execute(
                    sa.text("""INSERT INTO teams (id,name,slug,status,created_at,updated_at)
                        VALUES (:id,:slug,:slug,'active',now(),now())"""),
                    {"id": team, "slug": slug},
                )
            await conn.execute(
                sa.text("""INSERT INTO users
                    (id,team_id,email,password_hash,role,is_disabled,created_at,updated_at)
                    VALUES (:id,:team,'workspace-migration@example.com','fixture-only',
                            'owner',false,now(),now())"""),
                {"id": actor, "team": team_a},
            )
            await conn.execute(
                sa.text("""INSERT INTO price_lists (id,team_id,name,created_at,updated_at)
                    VALUES (:id,:team,'Preserved list',now(),now())"""),
                {"id": price_list, "team": team_a},
            )
            await conn.execute(
                sa.text("""INSERT INTO customers
                    (id,team_id,name,price_list_id,created_at,updated_at)
                    VALUES (:id,:team,'Preserved customer',:price,now(),now())"""),
                {"id": customer, "team": team_a, "price": price_list},
            )
            await conn.execute(
                sa.text("""INSERT INTO suppliers
                    (id,team_id,name,default_currency,created_at,updated_at)
                    VALUES (:id,:team,'Preserved supplier','ZAR',now(),now())"""),
                {"id": supplier, "team": team_a},
            )
            await conn.execute(
                sa.text("""INSERT INTO proformas
                    (id,team_id,supplier_id,invoice_number,invoice_date,currency,
                     pdf_storage_key,created_at,updated_at)
                    VALUES (:id,:team,:supplier,'PF-PRESERVE','2026-11-15','ZAR',
                            'fixture-only/proforma.pdf',now(),now())"""),
                {"id": proforma, "team": team_a, "supplier": supplier},
            )
            await conn.execute(
                sa.text("""INSERT INTO purchase_orders
                    (id,team_id,po_number,supplier_id,proforma_id,status,created_at,updated_at)
                    VALUES (:id,:team,'PO-PRESERVE',:supplier,:proforma,'open',now(),now())"""),
                {"id": po, "team": team_a, "supplier": supplier, "proforma": proforma},
            )
            if already_enforced:
                await conn.execute(sa.text("ALTER TABLE roles ENABLE ROW LEVEL SECURITY"))
                await conn.execute(sa.text("ALTER TABLE roles FORCE ROW LEVEL SECURITY"))

        migrate(url, "085_record_workspaces")
        async with engine.begin() as conn:
            for table, record_id in (("price_lists", price_list), ("proformas", proforma)):
                assert (
                    await conn.scalar(
                        sa.text(f"SELECT is_archived FROM {table} WHERE id=:id"), {"id": record_id}
                    )
                    is False
                )
                index = await conn.scalar(
                    sa.text("SELECT indexdef FROM pg_indexes WHERE indexname=:name"),
                    {"name": f"ix_{table}_team_id_is_archived"},
                )
                assert "(team_id, is_archived)" in index
                await conn.execute(
                    sa.text(f"UPDATE {table} SET is_archived=true WHERE id=:id"),
                    {"id": record_id},
                )
            assert (
                await conn.scalar(
                    sa.text("SELECT price_list_id FROM customers WHERE id=:id"), {"id": customer}
                )
                == price_list
            )
            assert (
                await conn.scalar(
                    sa.text("SELECT proforma_id FROM purchase_orders WHERE id=:id"), {"id": po}
                )
                == proforma
            )
            assert (
                await conn.scalar(
                    sa.text("SELECT pdf_storage_key FROM proformas WHERE id=:id"), {"id": proforma}
                )
                == "fixture-only/proforma.pdf"
            )
            flags = (
                await conn.execute(
                    sa.text("""SELECT relrowsecurity,relforcerowsecurity
                    FROM pg_class WHERE oid='public.record_workspace_batches'::regclass""")
                )
            ).one()
            assert flags.relrowsecurity is already_enforced
            assert flags.relforcerowsecurity is already_enforced

            insert = sa.text("""INSERT INTO record_workspace_batches
                (id,team_id,actor_user_id,request_id,resource,action,payload_hash,selection,result)
                VALUES (:id,:team,:actor,:request,'customers','archive',:digest,
                        CAST(:selection AS jsonb),CAST(:result AS jsonb))""")
            params = {
                "team": team_a,
                "actor": actor,
                "request": request_id,
                "digest": "a" * 64,
                "selection": json.dumps([{"id": str(customer), "revision": "expected-revision"}]),
                "result": json.dumps({"changed_ids": [str(customer)]}),
            }
            await conn.execute(insert, {**params, "id": uuid.uuid4()})
            with pytest.raises(sa.exc.IntegrityError):
                async with conn.begin_nested():
                    await conn.execute(insert, {**params, "id": uuid.uuid4()})
            # The same global actor/request may operate in a different approved
            # organisation: the idempotency key is deliberately tenant-scoped.
            await conn.execute(insert, {**params, "team": team_b, "id": uuid.uuid4()})
            receipt = (
                await conn.execute(
                    sa.text("""SELECT selection,result FROM record_workspace_batches
                    WHERE team_id=:team"""),
                    {"team": team_a},
                )
            ).one()
            assert receipt.selection == json.loads(params["selection"])
            assert receipt.result == json.loads(params["result"])

            await conn.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
            role_created = True
            await conn.execute(sa.text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            await conn.execute(
                sa.text(
                    f'GRANT SELECT,INSERT,UPDATE,DELETE ON record_workspace_batches TO "{role}"'
                )
            )
            # Exercise the prepared policy even for a compatibility installation.
            await conn.execute(
                sa.text("ALTER TABLE record_workspace_batches ENABLE ROW LEVEL SECURITY")
            )
            await conn.execute(
                sa.text("ALTER TABLE record_workspace_batches FORCE ROW LEVEL SECURITY")
            )

        async with engine.begin() as conn:
            await conn.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            assert await conn.scalar(sa.text("SELECT count(*) FROM record_workspace_batches")) == 0
            await conn.execute(
                sa.text("SELECT set_config('app.tenant_id',:team,true)"), {"team": str(team_a)}
            )
            assert list(
                await conn.scalars(sa.text("SELECT team_id FROM record_workspace_batches"))
            ) == [team_a]
            with pytest.raises(sa.exc.DBAPIError, match="row-level security"):
                async with conn.begin_nested():
                    await conn.execute(
                        insert,
                        {**params, "team": team_b, "id": uuid.uuid4(), "request": uuid.uuid4()},
                    )
            changed = await conn.execute(
                sa.text(
                    "UPDATE record_workspace_batches SET payload_hash=:digest WHERE team_id=:team"
                ),
                {"digest": "b" * 64, "team": team_b},
            )
            assert changed.rowcount == 0

        migrate(url, "084_party_archives", "downgrade")
        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    sa.text("SELECT price_list_id FROM customers WHERE id=:id"), {"id": customer}
                )
                == price_list
            )
            assert (
                await conn.scalar(
                    sa.text("SELECT proforma_id FROM purchase_orders WHERE id=:id"), {"id": po}
                )
                == proforma
            )
            assert (
                await conn.scalar(sa.text("SELECT to_regclass('record_workspace_batches')")) is None
            )
        migrate(url, "085_record_workspaces")
        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    sa.text("SELECT is_archived FROM price_lists WHERE id=:id"), {"id": price_list}
                )
                is False
            )
            assert (
                await conn.scalar(
                    sa.text("SELECT pdf_storage_key FROM proformas WHERE id=:id"), {"id": proforma}
                )
                == "fixture-only/proforma.pdf"
            )
    finally:
        if role_created:
            async with engine.begin() as conn:
                await conn.execute(sa.text(f'DROP OWNED BY "{role}"'))
                await conn.execute(sa.text(f'DROP ROLE "{role}"'))
        await engine.dispose()
