"""Actual PostgreSQL release sequencing, denial and durable acknowledgement."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from f0rge_testing import async_url
from testcontainers.postgres import PostgresContainer

from app.commands.release_migrate import (
    BACKEND,
    LOCK_KEY,
    POLICY,
    MigrationRefused,
    load_policy,
    migrate,
    plan_pending,
)
from app.services.release_readiness import release_readiness

pytestmark = pytest.mark.no_db
COMMIT = "a" * 40


def baseline(url: str, revision: str = "083_portal_clerk_identity") -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": url, "MIGRATION_DATABASE_URL": url},
        capture_output=True,
        timeout=90,
    )
    assert result.returncode == 0, "Synthetic PostgreSQL fixture migration failed"


def test_policy_has_one_head_and_no_unreviewed_automatic_history() -> None:
    policy, digest, scripts = load_policy()
    assert len(digest) == 64
    assert plan_pending(policy, scripts, "083_portal_clerk_identity") == [
        "084_party_archives",
        "085_record_workspaces",
        "086_release_migration_receipts",
    ]
    policy["revisions"]["085_record_workspaces"]["automatic"] = False
    with pytest.raises(MigrationRefused, match="not approved"):
        plan_pending(policy, scripts, "083_portal_clerk_identity")
    with pytest.raises(MigrationRefused, match="baseline upgrade"):
        plan_pending(policy, scripts, "082_tenant_onboarding")
    with pytest.raises(MigrationRefused, match="not an ancestor"):
        plan_pending(policy, scripts, "unrecognized_revision")


def test_changed_migration_checksum_is_rejected(tmp_path: Path) -> None:
    policy = json.loads(POLICY.read_text())
    policy["revisions"]["084_party_archives"]["sha256"] = "0" * 64
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    with pytest.raises(MigrationRefused, match="modified migration"):
        load_policy(path)


async def test_empty_production_database_is_not_bootstrapped(second_postgres_url: str) -> None:
    with pytest.raises(MigrationRefused, match="Uninitialized"):
        await migrate(second_postgres_url, second_postgres_url, COMMIT)
    engine = create_async_engine(second_postgres_url)
    try:
        async with engine.connect() as conn:
            assert await conn.scalar(sa.text("SELECT to_regclass('alembic_version')")) is None
    finally:
        await engine.dispose()


async def test_release_upgrade_preserves_old_reads_and_receipt_is_repeat_safe(
    second_postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = second_postgres_url
    baseline(url)
    engine = create_async_engine(url)
    team, customer = uuid.uuid4(), uuid.uuid4()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    "INSERT INTO teams (id,name,slug,status,created_at,updated_at) VALUES (:id,'CD fixture','cd-fixture','active',now(),now())"
                ),
                {"id": team},
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO customers (id,team_id,name,created_at,updated_at) VALUES (:id,:team,'Preserved customer',now(),now())"
                ),
                {"id": customer, "team": team},
            )
        first = await migrate(url, url, COMMIT)
        assert logging.getLogger("app.http").disabled is False
        assert first["applied_revisions"] == [
            "084_party_archives",
            "085_record_workspaces",
            "086_release_migration_receipts",
        ]
        assert first["replayed"] is False
        second = await migrate(url, url, COMMIT)
        assert second["replayed"] is True
        assert second["applied_revisions"] == []
        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    sa.text("SELECT name FROM customers WHERE id=:id"), {"id": customer}
                )
                == "Preserved customer"
            )
            assert (
                await conn.scalar(sa.text("SELECT count(*) FROM release_migration_receipts")) == 1
            )
            assert (
                await conn.scalar(
                    sa.text("SELECT is_archived FROM customers WHERE id=:id"), {"id": customer}
                )
                is False
            )
        monkeypatch.setenv("SOURCE_COMMIT", COMMIT)
        response = await release_readiness(engine)
        assert response.status_code == 200
        payload = json.loads(response.body)
        assert payload["migration_receipt"] is True
        assert payload["source_commit"] == COMMIT
        assert payload["schema_revision"] == "086_release_migration_receipts"
        # Old retained image readiness may observe a newer, additive schema.
        async with engine.begin() as conn:
            await conn.execute(
                sa.text("UPDATE alembic_version SET version_num='087_future_compatible'")
            )
        response = await release_readiness(engine)
        assert response.status_code == 200
        assert json.loads(response.body)["schema_revision"] == "087_future_compatible"
        monkeypatch.setenv("SOURCE_COMMIT", "b" * 40)
        assert (await release_readiness(engine)).status_code == 503
    finally:
        await engine.dispose()


async def test_distinct_runtime_role_can_read_but_cannot_mutate_receipts(
    second_postgres_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = second_postgres_url
    baseline(url)
    admin = create_async_engine(url)
    name = "cd_runtime_" + uuid.uuid4().hex[:12]
    password = uuid.uuid4().hex
    runtime_url = (
        make_url(url).set(username=name, password=password).render_as_string(hide_password=False)
    )
    runtime = create_async_engine(runtime_url)
    try:
        async with admin.begin() as conn:
            await conn.execute(
                sa.text(
                    f"CREATE ROLE \"{name}\" LOGIN PASSWORD '{password}' NOSUPERUSER NOBYPASSRLS"
                )
            )
        receipt = await migrate(url, runtime_url, COMMIT)
        assert receipt["migration_receipt"] is True
        monkeypatch.setenv("SOURCE_COMMIT", COMMIT)
        readiness = await release_readiness(runtime)
        assert readiness.status_code == 200
        assert json.loads(readiness.body)["migration_receipt"] is True
        async with runtime.connect() as conn:
            assert (
                await conn.scalar(sa.text("SELECT count(*) FROM release_migration_receipts")) == 1
            )
            assert (
                await conn.scalar(
                    sa.text("SELECT has_table_privilege(current_user,'alembic_version','SELECT')")
                )
                is True
            )
            assert (
                await conn.scalar(
                    sa.text("SELECT has_table_privilege(current_user,'alembic_version','UPDATE')")
                )
                is False
            )
            assert (
                await conn.scalar(
                    sa.text(
                        "SELECT has_table_privilege(current_user,'record_workspace_batches','INSERT')"
                    )
                )
                is True
            )
            with pytest.raises(sa.exc.DBAPIError):
                await conn.execute(sa.text("DELETE FROM release_migration_receipts"))
    finally:
        await runtime.dispose()
        async with admin.begin() as conn:
            await conn.execute(sa.text(f'DROP OWNED BY "{name}"'))
            await conn.execute(sa.text(f'DROP ROLE "{name}"'))
        await admin.dispose()


async def test_separate_session_lock_timeout_does_not_mutate(second_postgres_url: str) -> None:
    url = second_postgres_url
    baseline(url)
    engine = create_async_engine(url)
    try:
        async with engine.connect() as holding:
            await holding.execute(sa.text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
            with pytest.raises(MigrationRefused, match="lock wait expired"):
                await migrate(url, url, COMMIT, lock_timeout_seconds=0.05)
            assert (
                await holding.scalar(sa.text("SELECT version_num FROM alembic_version"))
                == "083_portal_clerk_identity"
            )
            await holding.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
        assert (await migrate(url, url, COMMIT))["status"] == "ok"
    finally:
        await engine.dispose()


async def test_migration_receipt_error_rolls_back_all_pending_schema(
    second_postgres_url: str,
) -> None:
    url = second_postgres_url
    baseline(url)
    engine = create_async_engine(url)
    try:
        # A real conflicting table makes revision086 fail after revisions084
        # and085 execute. Their schema/version changes must roll back together.
        async with engine.begin() as conn:
            await conn.execute(
                sa.text("CREATE TABLE release_migration_receipts (fixture_only integer)")
            )
        with pytest.raises(sa.exc.DBAPIError):
            await migrate(url, url, COMMIT)
        async with engine.begin() as conn:
            assert (
                await conn.scalar(sa.text("SELECT version_num FROM alembic_version"))
                == "083_portal_clerk_identity"
            )
            assert (
                await conn.scalar(
                    sa.text(
                        "SELECT count(*) FROM information_schema.columns WHERE table_name='customers' AND column_name='is_archived'"
                    )
                )
                == 0
            )
            await conn.execute(sa.text("DROP TABLE release_migration_receipts"))
        assert (await migrate(url, url, COMMIT))["status"] == "ok"
    finally:
        await engine.dispose()


async def test_bootstrap_is_scoped_to_empty_named_test_database(second_postgres_url: str) -> None:
    with pytest.raises(MigrationRefused, match="empty firstout_cd_test_"):
        await migrate(
            second_postgres_url, second_postgres_url, COMMIT, bootstrap_test_database=True
        )


async def test_explicit_empty_ci_database_bootstrap_reaches_ready_schema(
    second_postgres_url: str,
) -> None:
    parsed = make_url(second_postgres_url)
    name = "firstout_cd_test_" + uuid.uuid4().hex
    admin = create_async_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    url = parsed.set(database=name).render_as_string(hide_password=False)
    try:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
        receipt = await migrate(url, url, COMMIT, bootstrap_test_database=True)
        assert receipt["schema_revision"] == "086_release_migration_receipts"
        assert len(receipt["applied_revisions"]) == 86
        with pytest.raises(MigrationRefused, match="empty firstout_cd_test_"):
            await migrate(url, url, COMMIT, bootstrap_test_database=True)
        assert (await migrate(url, url, COMMIT))["replayed"] is True
    finally:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        await admin.dispose()


async def test_wrong_source_commit_and_database_target_are_denied(second_postgres_url: str) -> None:
    with pytest.raises(MigrationRefused, match="full source SHA"):
        await migrate(second_postgres_url, second_postgres_url, "main")
    other = (
        make_url(second_postgres_url)
        .set(database="unrelated")
        .render_as_string(hide_password=False)
    )
    with pytest.raises(MigrationRefused, match="names differ"):
        await migrate(second_postgres_url, other, COMMIT)


async def test_equal_names_on_separate_postgres_servers_are_denied_before_ddl(
    second_postgres_url: str,
) -> None:
    baseline(second_postgres_url)
    parsed = make_url(second_postgres_url)
    with PostgresContainer(
        "postgres:16", username="test", password="test", dbname=parsed.database
    ) as other_server:
        other_url = async_url(other_server)
        assert make_url(other_url).database == parsed.database
        with pytest.raises(MigrationRefused, match="different databases"):
            await migrate(second_postgres_url, other_url, COMMIT)
        # The deployed application honors DIRECT_DATABASE_URL. The CLI must
        # prove the migration target against that same effective runtime DSN,
        # even if DATABASE_URL itself points to the migration database.
        refused = subprocess.run(
            [sys.executable, "-m", "app.commands.release_migrate"],
            cwd=BACKEND,
            env={
                **os.environ,
                "SOURCE_COMMIT": COMMIT,
                "MIGRATION_DATABASE_URL": second_postgres_url,
                "DATABASE_URL": second_postgres_url,
                "DIRECT_DATABASE_URL": other_url,
            },
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert refused.returncode == 1
        assert json.loads(refused.stdout) == {
            "status": "refused",
            "reason": "Migration and runtime credentials reach different databases",
        }
        migration = create_async_engine(second_postgres_url)
        runtime = create_async_engine(other_url)
        try:
            async with migration.connect() as conn:
                assert (
                    await conn.scalar(sa.text("SELECT version_num FROM alembic_version"))
                    == "083_portal_clerk_identity"
                )
                assert (
                    await conn.scalar(sa.text("SELECT to_regclass('release_migration_receipts')"))
                    is None
                )
            async with runtime.connect() as conn:
                assert await conn.scalar(sa.text("SELECT to_regclass('alembic_version')")) is None
                assert (
                    await conn.scalar(sa.text("SELECT to_regclass('release_migration_receipts')"))
                    is None
                )
        finally:
            await migration.dispose()
            await runtime.dispose()


async def test_hostname_aliases_for_same_database_are_accepted(second_postgres_url: str) -> None:
    baseline(second_postgres_url)
    parsed = make_url(second_postgres_url)
    if parsed.host not in ("localhost", "127.0.0.1"):
        pytest.skip("Local hostname alias check requires a loopback Docker host")
    alias = parsed.set(host="127.0.0.1" if parsed.host == "localhost" else "localhost")
    result = await migrate(second_postgres_url, alias.render_as_string(hide_password=False), COMMIT)
    assert result["migration_receipt"] is True


async def test_readiness_failure_is_non_sensitive(
    second_postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_async_engine(second_postgres_url)
    try:
        monkeypatch.setenv("SOURCE_COMMIT", "")
        response = await release_readiness(engine)
        assert response.status_code == 503
        assert json.loads(response.body) == {"status": "unavailable"}
        monkeypatch.setenv("SOURCE_COMMIT", COMMIT)
        response = await release_readiness(engine)
        assert response.status_code == 503
        assert json.loads(response.body) == {"status": "unavailable"}
    finally:
        await engine.dispose()


async def test_readiness_invalid_database_credentials_return_sanitized_503(
    second_postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken_url = make_url(second_postgres_url).set(
        username="missing_runtime_role", password="synthetic-invalid-secret"
    )
    engine = create_async_engine(broken_url)
    monkeypatch.setenv("SOURCE_COMMIT", COMMIT)
    try:
        response = await release_readiness(engine)
        assert response.status_code == 503
        assert json.loads(response.body) == {"status": "unavailable"}
        assert "secret" not in response.body.decode()
    finally:
        await engine.dispose()
