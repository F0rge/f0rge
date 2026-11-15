"""Real PostgreSQL 15.19 schema/grants/backup compatibility, using only synthetic data.

The pinned fixture has no network or published ports and a distinct UUID label.
The fake age process tests streaming only; cryptographic recovery is a separate
operator rehearsal with real age and offline recovery-key custody.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from backup import backup
from preflight import database_query

OPS = Path(__file__).resolve().parent
PG15_IMAGE = "postgres:15.19-bookworm@sha256:19b8449e2187e8a174b40c8832a7ed9da45813b74c2779b1c614e7e7d0ee47f0"
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


class Postgres15CompatibilityTests(unittest.TestCase):
    def docker(self, *args, input=None, check=True, timeout=60):
        result = subprocess.run([self.docker_binary, "--host", self.docker_endpoint, *args], input=input, capture_output=True, check=False, timeout=timeout)
        if check:
            self.assertEqual(result.returncode, 0, "Isolated PostgreSQL 15 fixture failed; captured diagnostics withheld")
        return result

    def cleanup_container(self):
        identity = self.docker("inspect", self.container, "--format", '{{index .Config.Labels "com.f0rge.fixture"}}', check=False)
        if identity.returncode == 0 and identity.stdout.decode().strip() == self.fixture_id:
            self.docker("rm", "--force", "--volumes", self.container)

    def sql(self, query, *, database="buycycle", check=True):
        result = self.docker(
            "exec",
            "-i",
            self.container,
            "psql",
            "--no-psqlrc",
            "--username",
            "nextcloud",
            "--dbname",
            database,
            "--tuples-only",
            "--no-align",
            "--set",
            "ON_ERROR_STOP=1",
            input=query.encode(),
            check=check,
        )
        return result.stdout.strip() if check else result

    def fingerprints(self, database):
        return {
            table: hashlib.sha256(self.sql(f"SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM \"{table}\" t", database=database)).hexdigest()
            for table in TABLES
        }

    def private_file(self, name, content, mode=0o600):
        path = self.directory / name
        path.write_text(content)
        path.chmod(mode)
        return path

    def age_fixture(self):
        executable = self.private_file("age", f"#!{sys.executable}\nimport sys\nsys.stdout.buffer.write(b'FAKE-AGE-BOUNDARY\\n'+sys.stdin.buffer.read())\n", 0o700)
        recipients = self.private_file("recipients", "age1" + "q" * 58 + "\n")
        return executable, recipients

    def decrypt_fixture(self, path):
        encrypted = path.read_bytes()
        self.assertTrue(encrypted.startswith(b"FAKE-AGE-BOUNDARY\n"))
        return encrypted.removeprefix(b"FAKE-AGE-BOUNDARY\n")

    def client_fixture(self, binary):
        # Fixed local fixture endpoint and container; no inherited Docker context,
        # password environment variable, host database or arbitrary command.
        command = [
            self.docker_binary,
            "--host",
            self.docker_endpoint,
            "exec",
            "--env",
            "PGPASSFILE=/run/secrets/backup_pgpass",
            "--env",
            "PGOPTIONS=-c default_transaction_read_only=on -c statement_timeout=1800000",
            self.container,
            binary,
        ]
        return self.private_file(binary, f"#!{sys.executable}\nimport os, sys\nos.execv({self.docker_binary!r}, {command!r} + sys.argv[1:])\n", 0o700)

    def test_pg15_actual_schema_roles_and_read_only_backup_restore(self):
        self.docker_binary = shutil.which("docker")
        self.assertTrue(self.docker_binary, "Docker is required for the PostgreSQL 15 compatibility regression")
        context = subprocess.run([self.docker_binary, "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], capture_output=True, text=True, check=True, timeout=10)
        self.docker_endpoint = context.stdout.strip()
        self.assertRegex(self.docker_endpoint, r"\Aunix:///[^\r\n]+\Z", "Only an explicit local Unix Docker fixture endpoint is allowed")
        self.fixture_id = self.container = "buycycle-pg15-" + uuid.uuid4().hex
        temporary = tempfile.TemporaryDirectory(prefix=self.fixture_id + "-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        passwords = {role: "synthetic-" + role + "-" + uuid.uuid4().hex + uuid.uuid4().hex for role in ("runtime", "migrator", "backup")}
        mounts = []
        for role, password in passwords.items():
            path = self.private_file(role + "_password", password + "\n", 0o644)
            mounts += ["--mount", f"type=bind,source={path},target=/run/secrets/{role}_password,readonly"]
        pgpass = self.private_file("backup_pgpass", f"127.0.0.1:5432:buycycle:buycycle_backup:{passwords['backup']}\n")
        mounts += ["--mount", f"type=bind,source={pgpass},target=/run/secrets/backup_pgpass,readonly"]
        mounts += ["--mount", f"type=bind,source={OPS / 'init-db.sh'},target=/bootstrap/init-db.sh,readonly"]
        self.addCleanup(self.cleanup_container)
        self.docker(
            "run",
            "--detach",
            "--name",
            self.container,
            "--network",
            "none",
            "--label",
            "com.f0rge.fixture=" + self.fixture_id,
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--pids-limit",
            "256",
            "--env",
            "POSTGRES_USER=nextcloud",
            "--env",
            "POSTGRES_DB=buycycle",
            "--env",
            "POSTGRES_PASSWORD=synthetic-pg15-admin-only",
            *mounts,
            PG15_IMAGE,
            timeout=180,
        )
        for _ in range(160):
            ready = self.docker("exec", self.container, "pg_isready", "--host", "127.0.0.1", "--username", "nextcloud", "--dbname", "buycycle", check=False)
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            self.fail("Isolated PostgreSQL 15 did not become ready")
        inspected = json.loads(self.docker("inspect", self.container).stdout)[0]
        self.assertEqual(inspected["HostConfig"]["NetworkMode"], "none")
        self.assertFalse(inspected["HostConfig"].get("PortBindings"))
        self.assertEqual(self.sql("SHOW server_version_num"), b"150019")
        self.docker("exec", self.container, "bash", "/bootstrap/init-db.sh")
        # The other app is synthetic and already isolated, as the selected live
        # cluster must be; this regression never authorizes changing another app.
        self.sql("CREATE DATABASE other_app")
        self.sql("REVOKE CONNECT ON DATABASE other_app FROM PUBLIC")
        self.sql("CREATE ROLE oc_admin LOGIN CREATEDB NOSUPERUSER NOCREATEROLE NOREPLICATION NOBYPASSRLS; GRANT CONNECT ON DATABASE other_app TO oc_admin")
        schema = (OPS.parent / "backend/migrations/0001_initial/up.sql").read_text()
        schema += "CREATE TABLE buycycle_schema_migrations(version text PRIMARY KEY,checksum text NOT NULL,applied_at timestamptz NOT NULL DEFAULT clock_timestamp());"
        schema += (OPS / "grant-runtime.sql").read_text()
        self.sql("SET ROLE buycycle_migrator;" + schema)
        self.sql("""SET ROLE buycycle_migrator;
INSERT INTO legacy_record VALUES('listing','synthetic-pg15','{"kind":"bikes","title":"Synthetic PG15 bike"}');
INSERT INTO user_state(subject,revision,state) VALUES('synthetic-subject',2,'{"watch":{"one":true},"costs":{"shipping":12}}');
INSERT INTO user_state_history(subject,revision,state) VALUES('synthetic-subject',1,'{}'),('synthetic-subject',2,'{"watch":{"one":true},"costs":{"shipping":12}}');
INSERT INTO browser_import(id,subject,sha256,source,state_revision) VALUES('00000000-0000-4000-8000-000000000001','synthetic-subject',repeat('a',64),'{}',2);
INSERT INTO collection_day(day,detail_attempts,blocked,pending) VALUES('2026-01-15',0,false,false);
INSERT INTO collector_runs(id,day,kind,complete,metadata) VALUES('00000000-0000-4000-8000-000000000002','2026-01-15','bikes',true,'{}');
INSERT INTO source_snapshots(id,run_id,kind,source_kind,sha256,payload) VALUES('00000000-0000-4000-8000-000000000003','00000000-0000-4000-8000-000000000002','bikes','feed',repeat('b',64),'{}');
INSERT INTO import_manifest VALUES(repeat('c',64),'{}',clock_timestamp());
INSERT INTO buycycle_schema_migrations(version,checksum) VALUES('0001_initial','synthetic');""")
        observed = json.loads(self.sql(database_query(15)))
        self.assertEqual(observed, {"passed": True, "server_version_num": 150019, "current_user": "nextcloud", "current_database": "buycycle"})
        self.assertFalse(json.loads(self.sql(database_query(17)))["passed"])
        reverse_isolation = json.loads(
            self.sql(
                "SELECT json_build_object('superuser',(SELECT rolsuper FROM pg_roles WHERE rolname='oc_admin'),"
                "'member_of_admin',pg_has_role('oc_admin','nextcloud','MEMBER'),"
                "'connect',has_database_privilege('oc_admin','buycycle','CONNECT'),"
                "'read',has_table_privilege('oc_admin','public.legacy_record','SELECT'),"
                "'other_app_connect',has_database_privilege('oc_admin','other_app','CONNECT'))"
            )
        )
        self.assertEqual(reverse_isolation, {"superuser": False, "member_of_admin": False, "connect": False, "read": False, "other_app_connect": True})
        denied_connection = self.docker("exec", self.container, "psql", "-X", "-U", "oc_admin", "-d", "buycycle", "-c", "SELECT 1", check=False)
        self.assertNotEqual(denied_connection.returncode, 0, "The existing other-app runtime must not connect to Buycycle")
        self.assertNotEqual(self.sql("SET ROLE oc_admin; SELECT * FROM legacy_record", check=False).returncode, 0, "Other-app runtime must not read Buycycle tables")
        for query in ("INSERT INTO user_state_history VALUES('bad',1,'{}')", "CREATE TABLE forbidden(id integer)", "DELETE FROM legacy_record"):
            denied = self.sql("SET ROLE buycycle_backup;" + query, check=False)
            self.assertNotEqual(denied.returncode, 0, "Backup role must remain read-only")
        destination = self.directory / "backups"
        destination.mkdir(mode=0o700)
        age, recipients = self.age_fixture()
        config = {
            "host": "127.0.0.1",
            "port": 5432,
            "database": "buycycle",
            "username": "buycycle_backup",
            "pgpassfile": str(pgpass),
            "destination": str(destination),
            "recipients_file": str(recipients),
            "source_commit": "a" * 40,
            "timeout_seconds": 60,
            "postgres_major": 15,
            "age": str(age),
        }
        config.update({name: str(self.client_fixture(name)) for name in ("pg_dump", "pg_restore", "psql")})
        before = self.fingerprints("buycycle")
        published = backup(config, uid=os.getuid())
        manifest = json.loads((published / "manifest.json").read_text())
        self.assertEqual(manifest["server_version_num"], 150019)
        self.assertEqual(manifest["postgres_major"], 15)
        self.assertTrue(all(re.search(r"\b15\.19\b", version) for version in manifest["client_versions"].values()))
        dump = self.decrypt_fixture(published / "database.dump.age")
        self.assertTrue(dump.startswith(b"PGDMP"))
        # Revoking CREATE DATABASE and all writes did not prevent a complete dump.
        self.sql("CREATE DATABASE restored_pg15")
        self.docker("exec", "-i", self.container, "pg_restore", "--username", "nextcloud", "--exit-on-error", "--no-owner", "--no-acl", "--dbname", "restored_pg15", input=dump)
        self.assertEqual(before, self.fingerprints("restored_pg15"))
        self.assertEqual(self.sql("SELECT count(*) FROM user_state_history", database="restored_pg15"), b"2")
        logs = self.docker("logs", self.container)
        self.assertFalse(any(password.encode() in logs.stdout + logs.stderr for password in passwords.values()), "Synthetic role secret appeared in PostgreSQL logs")
