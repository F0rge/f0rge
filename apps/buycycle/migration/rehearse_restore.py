#!/usr/bin/env python3
"""Synthetic PostgreSQL backup/restore drill, restricted to the local test container.

Creates isolated databases, imports synthetic history, proves complete restore,
then proves a pre-edit backup is stale and refreshes it without losing the edit.
Never reads Turso, a real user's state, or a production database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import uuid

TABLES = (
    "legacy_record",
    "user_state",
    "user_state_history",
    "browser_import",
    "collection_day",
    "collector_runs",
    "source_snapshots",
    "import_manifest",
    "buycycle_schema_migrations",
)


def run(*args, input=None, env=None):
    return subprocess.run(args, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=True).stdout


def verify_container(container, port, postgres_major=17):
    if type(postgres_major) is not int or postgres_major not in {15, 17}:
        raise ValueError("Only explicitly selected PostgreSQL 15 or 17 rehearsal is allowed")
    expected_name = "buycycle-migration-pg15" if postgres_major == 15 else "buycycle-migration-pg"
    valid_port = type(port) is int and (1024 <= port <= 65535 if postgres_major == 15 else port == 5549)
    if container != expected_name or not valid_port:
        raise ValueError("Only the task-owned synthetic rehearsal container and port are allowed")
    info = json.loads(run("docker", "inspect", container))[0]
    variables = dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)
    bindings = info["NetworkSettings"]["Ports"].get("5432/tcp", [])
    if (
        variables.get("POSTGRES_DB") != "buycycle_rehearsal"
        or not bindings
        or any(binding != {"HostIp": "127.0.0.1", "HostPort": str(port)} for binding in bindings)
    ):
        raise ValueError("Container is not the expected isolated PostgreSQL rehearsal")
    if not info["Config"]["Image"].startswith(f"postgres:{postgres_major}"):
        raise ValueError("The rehearsal image does not match the selected PostgreSQL major")
    versions = {}
    for binary in ("postgres", "pg_dump", "pg_restore", "psql"):
        version = run("docker", "exec", container, binary, "--version").decode().strip()
        match = re.fullmatch(re.escape(binary) + r" \(PostgreSQL\) ([0-9]+)(?:\.[0-9]+)?[^\n]*", version)
        if match is None or int(match[1]) != postgres_major:
            raise ValueError("Rehearsal server and dump/restore/query clients must match the selected major")
        versions[binary] = version
    server_version = int(psql(container, "buycycle_rehearsal", "SHOW server_version_num").strip())
    if server_version // 10000 != postgres_major:
        raise ValueError("Observed rehearsal server major differs from its configuration")
    return {"server_version_num": server_version, "client_versions": versions, "image": info["Config"]["Image"]}


def psql(container, database, sql):
    return run("docker", "exec", "-i", container, "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", database, input=sql.encode())


def fingerprints(container, database):
    result = {}
    for table in TABLES:
        data = psql(container, database, f"SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM \"{table}\" t;").strip()
        result[table] = {"sha256": hashlib.sha256(data).hexdigest(), "rows": len(json.loads(data))}
    return result


def dump(container, database, path):
    data = run("docker", "exec", container, "pg_dump", "-U", "postgres", "--format=custom", "--no-owner", "--no-acl", "--dbname", database)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest()


def restore(container, database, path):
    run(
        "docker",
        "exec",
        "-i",
        container,
        "pg_restore",
        "-U",
        "postgres",
        "--exit-on-error",
        "--no-owner",
        "--no-acl",
        "--dbname",
        database,
        input=path.read_bytes(),
    )


def assert_candidate_current(authoritative, candidate):
    if authoritative != candidate:
        raise ValueError("Recovery candidate is stale; activation is blocked until later writes are preserved")


def rehearse(container, port, bin_dir, postgres_major=17):
    engine = verify_container(container, port, postgres_major)
    suffix = uuid.uuid4().hex
    source, restored, refreshed = [f"buycycle_rehearsal_{purpose}_{suffix}" for purpose in ("source", "restored", "refreshed")]
    databases = []
    try:
        for database in (source, restored, refreshed):
            psql(container, "buycycle_rehearsal", f"CREATE DATABASE {database};")
            databases.append(database)
        env = os.environ.copy()
        env["MIGRATION_DATABASE_URL"] = f"postgres://postgres:buycycle-local-rehearsal@127.0.0.1:{port}/{source}"
        env["BUYCYCLE_LOCAL_SEED"] = "1"
        run(str(bin_dir / "migrate"), env=env)
        run(str(bin_dir / "seed"), env=env)
        psql(
            container,
            source,
            """BEGIN;
INSERT INTO user_state(subject,revision,state) VALUES('synthetic-recovery-subject',1,'{"version":1,"bikes":{"watch":{},"log":[],"costs":{}},"wheels":{"watch":{},"log":[],"costs":{}}}');
INSERT INTO user_state_history(subject,revision,state) SELECT subject,revision,state FROM user_state;
INSERT INTO browser_import(id,subject,sha256,source,state_revision) VALUES('00000000-0000-4000-8000-000000000001','synthetic-recovery-subject',repeat('a',64),'{"original":"synthetic-browser-export"}',1);
INSERT INTO collector_runs(id,day,kind,complete,metadata) VALUES('00000000-0000-4000-8000-000000000002','2026-01-15','bikes',false,'{"processing_version":"synthetic-drill-v1"}');
INSERT INTO source_snapshots(id,run_id,kind,source_kind,sha256,payload) VALUES('00000000-0000-4000-8000-000000000003','00000000-0000-4000-8000-000000000002','bikes','feed',repeat('b',64),'{"response":"synthetic-retained-input"}');
COMMIT;""",
        )
        before = fingerprints(container, source)
        with tempfile.TemporaryDirectory(prefix="buycycle-restore-") as temporary:
            backup = Path(temporary) / "before-edit.dump"
            backup_sha = dump(container, source, backup)
            restore(container, restored, backup)
            initial_restore = fingerprints(container, restored)
            assert_candidate_current(before, initial_restore)
            # Simulate an acknowledged post-backup edit with its durable journal.
            psql(
                container,
                source,
                """BEGIN;
UPDATE user_state SET revision=2,state='{"version":1,"bikes":{"watch":{"fixture-bikes-0":{"n":"Retained watch"}},"log":[{"name":"Retained trade","buy":100,"sell":0}],"costs":{"buffer":37}},"wheels":{"watch":{},"log":[],"costs":{"shipin":12}}}' WHERE subject='synthetic-recovery-subject';
INSERT INTO user_state_history(subject,revision,state) SELECT subject,revision,state FROM user_state;
COMMIT;""",
            )
            latest = fingerprints(container, source)
            stale_blocked = False
            try:
                assert_candidate_current(latest, initial_restore)
            except ValueError:
                stale_blocked = True
            if not stale_blocked:
                raise AssertionError("A pre-edit backup was incorrectly accepted")
            fresh = Path(temporary) / "after-edit.dump"
            fresh_sha = dump(container, source, fresh)
            restore(container, refreshed, fresh)
            final_restore = fingerprints(container, refreshed)
            assert_candidate_current(latest, final_restore)
            return {
                "version": 1,
                "engine": f"PostgreSQL {postgres_major}",
                **engine,
                "synthetic_only": True,
                "before_edit_backup_sha256": backup_sha,
                "after_edit_backup_sha256": fresh_sha,
                "initial_restore_exact": True,
                "stale_recovery_activation_blocked": stale_blocked,
                "later_watch_trade_costs_and_history_retained": final_restore["user_state"]["rows"] == 1 and final_restore["user_state_history"]["rows"] == 2,
                "all_tables": final_restore,
                "turso_restart": False,
            }
    finally:
        for database in reversed(databases):
            psql(container, "buycycle_rehearsal", f"DROP DATABASE IF EXISTS {database} WITH (FORCE);")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="buycycle-migration-pg")
    parser.add_argument("--port", type=int)
    parser.add_argument("--postgres-major", type=int, choices=(15, 17), default=17)
    parser.add_argument("--bin-dir", type=Path, default=Path("target/nx/buycycle-backend/debug"))
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if args.postgres_major == 15 and args.port is None:
        parser.error("PostgreSQL 15 rehearsal requires an explicit unused loopback --port")
    port = args.port if args.port is not None else 5549
    try:
        evidence = rehearse(args.container, port, args.bin_dir.absolute(), args.postgres_major)
        fd = os.open(args.evidence, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(evidence, stream, sort_keys=True, indent=2)
            stream.write("\n")
        print("Synthetic restore, stale-backup rejection and later-write preservation passed.")
    except (OSError, ValueError, AssertionError, subprocess.CalledProcessError):
        parser.exit(1, "Restore rehearsal refused or failed; production was not accessed. Inspect local evidence privately.\n")


if __name__ == "__main__":
    main()
