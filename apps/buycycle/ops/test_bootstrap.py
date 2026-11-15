"""Run the bootstrap failure path on a disposable, isolated PostgreSQL 17.

Only the UUID-labelled fixture container and its anonymous volume are removed.
All passwords are generated synthetic values; no production service is read.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

OPS = Path(__file__).resolve().parent


class PostgresBootstrapTests(unittest.TestCase):
    def docker(self, *args: str, check: bool = True, timeout: int = 30):
        result = subprocess.run(["docker", *args], capture_output=True, text=True, check=False, timeout=timeout)
        if check:
            self.assertEqual(result.returncode, 0, "Isolated Docker fixture step failed; captured diagnostics withheld")
        return result

    def cleanup_container(self):
        identity = self.docker("container", "inspect", self.container, "--format", '{{index .Config.Labels "com.f0rge.fixture"}}', check=False)
        if identity.returncode == 0 and identity.stdout.strip() == self.fixture_id:
            self.docker("rm", "--force", "--volumes", self.container)

    def sql(self, query: str):
        return self.docker(
            "exec",
            self.container,
            "psql",
            "--username",
            "postgres",
            "--dbname",
            "buycycle",
            "--no-align",
            "--tuples-only",
            "--set",
            "ON_ERROR_STOP=1",
            "--command",
            query,
        ).stdout.strip()

    def test_real_pg17_duplicate_role_failure_redacts_secrets_and_preserves_roles(self):
        if not shutil.which("docker"):
            self.fail("Docker is required for the PostgreSQL bootstrap regression")
        self.fixture_id = "buycycle-bootstrap-" + uuid.uuid4().hex
        self.container = self.fixture_id
        runtime_password = "synthetic-runtime-" + uuid.uuid4().hex + uuid.uuid4().hex
        migrator_password = "synthetic-migrator-" + uuid.uuid4().hex + uuid.uuid4().hex
        backup_password = "synthetic-backup-" + uuid.uuid4().hex + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix=self.fixture_id + "-") as directory:
            secrets = Path(directory)
            runtime, migrator = secrets / "runtime_password", secrets / "migrator_password"
            backup = secrets / "backup_password"
            runtime.write_text(runtime_password + "\n")
            migrator.write_text(migrator_password + "\n")
            backup.write_text(backup_password + "\n")
            # These disposable synthetic fixtures must be readable by the image's
            # PostgreSQL UID; their host parent directory remains mode 0700.
            runtime.chmod(0o644)
            migrator.chmod(0o644)
            backup.chmod(0o644)
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
                "POSTGRES_DB=buycycle",
                "--env",
                "POSTGRES_PASSWORD=synthetic-bootstrap-admin-only",
                "--mount",
                "type=bind,source=" + str(runtime) + ",target=/run/secrets/runtime_password,readonly",
                "--mount",
                "type=bind,source=" + str(migrator) + ",target=/run/secrets/migrator_password,readonly",
                "--mount",
                "type=bind,source=" + str(backup) + ",target=/run/secrets/backup_password,readonly",
                "--mount",
                "type=bind,source=" + str(OPS / "init-db.sh") + ",target=/bootstrap/init-db.sh,readonly",
                "postgres:17-bookworm",
                timeout=90,
            )
            for _ in range(120):
                ready = self.docker("exec", self.container, "pg_isready", "--host", "127.0.0.1", "--username", "postgres", "--dbname", "buycycle", check=False, timeout=5)
                if ready.returncode == 0:
                    break
                time.sleep(0.25)
            else:
                self.fail("Isolated PostgreSQL did not become ready")

            container = json.loads(self.docker("inspect", self.container).stdout)[0]
            self.assertEqual(container["HostConfig"]["NetworkMode"], "none")
            self.assertFalse(container["HostConfig"].get("PortBindings"))
            self.assertEqual(int(self.sql("SHOW server_version_num")) // 10000, 17)
            bootstrap = ["exec", "--env", "POSTGRES_USER=postgres", "--env", "POSTGRES_DB=buycycle", self.container, "bash", "/bootstrap/init-db.sh"]
            first = self.docker(*bootstrap)
            expected_roles = [
                {"rolname": "buycycle_backup", "rolcanlogin": True, "rolsuper": False, "rolcreatedb": False, "rolcreaterole": False, "rolreplication": False},
                {"rolname": "buycycle_migrator", "rolcanlogin": True, "rolsuper": False, "rolcreatedb": False, "rolcreaterole": False, "rolreplication": False},
                {"rolname": "buycycle_runtime", "rolcanlogin": True, "rolsuper": False, "rolcreatedb": False, "rolcreaterole": False, "rolreplication": False},
            ]
            roles_query = (
                "SELECT json_agg(r) FROM (SELECT rolname,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication "
                "FROM pg_roles WHERE rolname IN ('buycycle_runtime','buycycle_migrator','buycycle_backup') ORDER BY rolname) r"
            )
            self.assertEqual(json.loads(self.sql(roles_query)), expected_roles)
            grants_query = (
                "SELECT json_build_object('runtime_connect',has_database_privilege('buycycle_runtime','buycycle','CONNECT'),"
                "'runtime_usage',has_schema_privilege('buycycle_runtime','public','USAGE'),"
                "'runtime_create',has_schema_privilege('buycycle_runtime','public','CREATE'),"
                "'migrator_create',has_schema_privilege('buycycle_migrator','public','CREATE'),"
                "'backup_connect',has_database_privilege('buycycle_backup','buycycle','CONNECT'),"
                "'backup_usage',has_schema_privilege('buycycle_backup','public','USAGE'),"
                "'backup_create',has_schema_privilege('buycycle_backup','public','CREATE'))"
            )
            expected_grants = {
                "runtime_connect": True,
                "runtime_usage": True,
                "runtime_create": False,
                "migrator_create": True,
                "backup_connect": True,
                "backup_usage": True,
                "backup_create": False,
            }
            self.assertEqual(json.loads(self.sql(grants_query)), expected_grants)
            self.sql("SET ROLE buycycle_migrator; CREATE TABLE public.backup_grant_probe(id integer); RESET ROLE")
            backup_grants = json.loads(
                self.sql(
                    "SELECT json_build_object('select',has_table_privilege('buycycle_backup','public.backup_grant_probe','SELECT'),"
                    "'insert',has_table_privilege('buycycle_backup','public.backup_grant_probe','INSERT'),"
                    "'update',has_table_privilege('buycycle_backup','public.backup_grant_probe','UPDATE'),"
                    "'delete',has_table_privilege('buycycle_backup','public.backup_grant_probe','DELETE'),"
                    "'truncate',has_table_privilege('buycycle_backup','public.backup_grant_probe','TRUNCATE'))"
                )
            )
            self.assertEqual(backup_grants, {"select": True, "insert": False, "update": False, "delete": False, "truncate": False})
            second = self.docker(*bootstrap, check=False)
            self.assertNotEqual(second.returncode, 0, "Repeating bootstrap must fail instead of changing existing roles")
            self.assertIn("Managed database role bootstrap failed; inspect secret custody and role prerequisites", second.stderr)
            self.assertEqual(json.loads(self.sql(roles_query)), expected_roles)
            self.assertEqual(json.loads(self.sql(grants_query)), expected_grants)
            server_logs = self.docker("logs", self.container)
            captured = first.stdout + first.stderr + second.stdout + second.stderr + server_logs.stdout + server_logs.stderr
            self.assertFalse(
                any(password in captured for password in (runtime_password, migrator_password, backup_password)),
                "A synthetic role password appeared in client or PostgreSQL server logs",
            )
            self.assertNotIn("CREATE ROLE buycycle_runtime LOGIN PASSWORD '", second.stderr)
            self.cleanup_container()


class ImageHarnessLogTests(unittest.TestCase):
    def test_credentials_in_either_docker_log_stream_refuse_image_evidence(self):
        spec = importlib.util.spec_from_file_location("buycycle_image_log_test", OPS / "image_rehearsal.py")
        harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(harness)
        commit, image_id = "a" * 40, "sha256:" + "b" * 64

        def commands(*args, **_kwargs):
            if args[:2] == ("git", "rev-parse"):
                return commit
            if args[:2] == ("git", "status"):
                return ""
            if args[:3] == ("docker", "image", "inspect"):
                return json.dumps(
                    [
                        {
                            "Id": image_id,
                            "Architecture": "arm64",
                            "Os": "linux",
                            "Config": {"User": "10001:10001", "Labels": {"org.opencontainers.image.revision": commit}},
                        }
                    ]
                )
            if args[:2] == ("docker", "inspect"):
                return json.dumps([{"Image": image_id}])
            if args[-1] == "/probe.mjs":
                return json.dumps({"synthetic_probe": True})
            return ""

        for contaminated_stream in ("stdout", "stderr"):
            with self.subTest(stream=contaminated_stream), tempfile.TemporaryDirectory() as directory:
                seen_logs = []

                def subprocesses(args, seen_logs=seen_logs, contaminated_stream=contaminated_stream, **kwargs):
                    if args[:2] == ["docker", "logs"]:
                        seen_logs.append(kwargs)
                        output = {"stdout": "safe log", "stderr": "safe log"}
                        output[contaminated_stream] = "synthetic-image-only"
                        return subprocess.CompletedProcess(args, 0, **output)
                    return subprocess.CompletedProcess(args, 0, b"", b"")

                stdout, stderr = io.StringIO(), io.StringIO()
                with (
                    patch.object(harness, "command", commands),
                    patch.object(harness.subprocess, "run", subprocesses),
                    patch.object(sys, "argv", ["image_rehearsal", "--image", image_id, "--output", directory]),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                    self.assertRaisesRegex(AssertionError, "Sensitive fixture"),
                ):
                    harness.main()
                self.assertEqual(len(seen_logs), 1)
                self.assertIs(seen_logs[0]["capture_output"], True)
                self.assertNotIn("synthetic-image-only", stdout.getvalue() + stderr.getvalue())
                self.assertFalse((Path(directory) / "evidence.json").exists())


if __name__ == "__main__":
    unittest.main()
