"""Run reviewed additive migrations once before a Firstout image is promoted.

No credentials or SQL errors are printed. This command never downgrades a
database and never runs in application startup. SOURCE_COMMIT is baked into
the tested image. The caller supplies the existing migration/runtime URLs.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from typing import Optional

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from f0rge_db.db_url import resolve_database_url
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

BACKEND = Path(__file__).resolve().parents[2]
POLICY = Path(__file__).with_name("release_migration_policy.json")
LOCK_KEY = 488949456493427
SOURCE_SHA = re.compile(r"[0-9a-f]{40}\Z")


class MigrationRefused(RuntimeError):
    pass


def load_policy(policy_path: Path = POLICY) -> tuple[dict, str, ScriptDirectory]:
    raw = policy_path.read_bytes()
    policy = json.loads(raw)
    config = Config(str(BACKEND / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    if policy["schema_version"] != 1 or scripts.get_heads() != [policy["target_revision"]]:
        raise MigrationRefused("Migration policy must match the single image schema head")
    for item in scripts.walk_revisions():
        entry = policy["revisions"].get(item.revision)
        digest = hashlib.sha256(Path(item.path).read_bytes()).hexdigest()
        if not entry or entry["sha256"] != digest:
            raise MigrationRefused("Unreviewed or modified migration in the image")
    return policy, hashlib.sha256(raw).hexdigest(), scripts


def plan_pending(policy: dict, scripts: ScriptDirectory, current: Optional[str]) -> list[str]:
    try:
        pending = list(
            reversed(list(scripts.iterate_revisions(policy["target_revision"], current)))
        )
    except Exception as exc:
        raise MigrationRefused("Database revision is not an ancestor of this image") from exc
    if current is not None and current != policy["target_revision"]:
        baseline = list(scripts.iterate_revisions(policy["baseline_revision"], "base"))
        if current in {
            item.revision for item in baseline if item.revision != policy["baseline_revision"]
        }:
            raise MigrationRefused("Database needs an explicitly reviewed baseline upgrade")
    if any(policy["revisions"][item.revision]["automatic"] is not True for item in pending):
        raise MigrationRefused("Pending migration is not approved for automatic deployment")
    return [item.revision for item in pending]


async def current_revision(connection: AsyncConnection) -> Optional[str]:
    exists = await connection.scalar(sa.text("SELECT to_regclass('public.alembic_version')"))
    if not exists:
        return None
    revisions = (
        (await connection.execute(sa.text("SELECT version_num FROM alembic_version")))
        .scalars()
        .all()
    )
    if len(revisions) > 1:
        raise MigrationRefused("Multiple database schema heads are unsupported")
    return revisions[0] if revisions else None


async def acquire_lock(connection: AsyncConnection, timeout_seconds: float) -> None:
    end = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        if await connection.scalar(sa.text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}):
            await connection.commit()
            return
        if asyncio.get_running_loop().time() >= end:
            raise MigrationRefused("Another migration is running; lock wait expired")
        await asyncio.sleep(min(0.1, max(0, end - asyncio.get_running_loop().time())))


async def verify_database_identity(connection: AsyncConnection, runtime_url: str) -> None:
    """Prove both credentials reach the same PostgreSQL database before DDL.

    Advisory locks are scoped to the PostgreSQL database. A fresh unpredictable
    lock held by the migration connection must be unavailable to the runtime
    connection. This permits hostname aliases and distinct database roles while
    rejecting equal database names on unrelated PostgreSQL servers.
    """
    nonce = secrets.randbits(63)
    while nonce in (0, LOCK_KEY):
        nonce = secrets.randbits(63)
    await connection.execute(sa.text("SELECT pg_advisory_lock(:key)"), {"key": nonce})
    await connection.commit()
    runtime = create_async_engine(
        resolve_database_url(runtime_url), pool_pre_ping=True, connect_args={"timeout": 10}
    )
    try:
        async with runtime.connect() as checking:
            acquired = await checking.scalar(
                sa.text("SELECT pg_try_advisory_lock(:key)"), {"key": nonce}
            )
            if acquired:
                await checking.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": nonce})
                await checking.commit()
                raise MigrationRefused(
                    "Migration and runtime credentials reach different databases"
                )
    finally:
        await runtime.dispose()
        await connection.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": nonce})
        await connection.commit()


async def migrate(
    migration_url: str,
    runtime_url: str,
    source_commit: str,
    *,
    bootstrap_test_database: bool = False,
    lock_timeout_seconds: float = 30,
) -> dict:
    if not SOURCE_SHA.fullmatch(source_commit):
        raise MigrationRefused("SOURCE_COMMIT must be the image's full source SHA")
    policy, policy_hash, scripts = load_policy()
    migration_parsed, runtime_parsed = make_url(migration_url), make_url(runtime_url)
    if migration_parsed.database != runtime_parsed.database:
        raise MigrationRefused("Migration and runtime database names differ")
    engine = create_async_engine(resolve_database_url(migration_url), pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await acquire_lock(connection, lock_timeout_seconds)
            try:
                await verify_database_identity(connection, runtime_url)
                current = await current_revision(connection)
                if bootstrap_test_database:
                    count = await connection.scalar(
                        sa.text(
                            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
                        )
                    )
                    if (
                        current is not None
                        or count
                        or not (migration_parsed.database or "").startswith("firstout_cd_test_")
                    ):
                        raise MigrationRefused(
                            "Test bootstrap requires an empty firstout_cd_test_ database"
                        )
                    pending = [item.revision for item in reversed(list(scripts.walk_revisions()))]
                else:
                    if current is None:
                        raise MigrationRefused(
                            "Uninitialized database: production bootstrap is never automatic"
                        )
                    pending = plan_pending(policy, scripts, current)
                await connection.commit()
                async with connection.begin():
                    await connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
                    await connection.execute(sa.text("SET LOCAL statement_timeout = '10min'"))
                    config = Config(str(BACKEND / "alembic.ini"))

                    def upgrade(sync_connection):
                        config.attributes["connection"] = sync_connection
                        command.upgrade(config, policy["target_revision"])

                    await connection.run_sync(upgrade)
                    after = await current_revision(connection)
                    if after != policy["target_revision"]:
                        raise MigrationRefused("Migration did not reach the image schema head")
                    existing = (
                        (
                            await connection.execute(
                                sa.text(
                                    "SELECT schema_revision,policy_sha256 FROM release_migration_receipts WHERE source_commit=:commit"
                                ),
                                {"commit": source_commit},
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if existing and (
                        existing["schema_revision"] != after
                        or existing["policy_sha256"] != policy_hash
                    ):
                        raise MigrationRefused(
                            "Source commit already has a different migration receipt"
                        )
                    if not existing:
                        await connection.execute(
                            sa.text(
                                "INSERT INTO release_migration_receipts (source_commit,schema_revision,policy_sha256,from_revision) VALUES (:commit,:head,:policy,:before)"
                            ),
                            {
                                "commit": source_commit,
                                "head": after,
                                "policy": policy_hash,
                                "before": current,
                            },
                        )
                    runtime_role = runtime_parsed.username
                    if not runtime_role:
                        raise MigrationRefused("Runtime database role is required")
                    quoted_role = connection.dialect.identifier_preparer.quote_identifier(
                        runtime_role
                    )
                    # Readiness reads both the release receipt and Alembic's
                    # current schema version; runtime needs read-only metadata.
                    await connection.execute(
                        sa.text(
                            f"GRANT SELECT ON TABLE release_migration_receipts, alembic_version TO {quoted_role}"
                        )
                    )
                    # 085 adds this tenant-owned table; keep its existing RLS
                    # stage and grant only the app's normal DML capabilities.
                    await connection.execute(
                        sa.text(
                            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE record_workspace_batches TO {quoted_role}"
                        )
                    )
                return {
                    "status": "ok",
                    "source_commit": source_commit,
                    "schema_revision": after,
                    "policy_sha256": policy_hash,
                    "migration_receipt": True,
                    "applied_revisions": pending,
                    "replayed": existing is not None,
                }
            finally:
                await connection.rollback()
                await connection.execute(
                    sa.text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY}
                )
                await connection.commit()
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Describe the image's reviewed schema without connecting to a database",
    )
    parser.add_argument("--bootstrap-test-database", action="store_true")
    args = parser.parse_args()
    try:
        if args.describe:
            policy, policy_hash, _scripts = load_policy()
            print(
                json.dumps(
                    {"schema_revision": policy["target_revision"], "policy_sha256": policy_hash},
                    sort_keys=True,
                )
            )
            return 0
        from app.config import settings

        runtime_url = resolve_database_url(
            settings.database_url, direct_url=settings.direct_database_url
        )
        migration_url = resolve_database_url(
            os.environ.get("MIGRATION_DATABASE_URL") or runtime_url
        )
        receipt = asyncio.run(
            migrate(
                migration_url,
                runtime_url,
                os.environ.get("SOURCE_COMMIT", ""),
                bootstrap_test_database=args.bootstrap_test_database,
            )
        )
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except MigrationRefused as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}))
        return 1
    except Exception:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "reason": "Migration failed; inspect privileged database diagnostics privately",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
