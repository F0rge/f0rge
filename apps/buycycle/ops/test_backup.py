"""Synthetic process-boundary tests; fake age does not prove cryptographic recovery."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from backup import backup
from ops_common import OpsError, local_database, protected_path, read_config


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.uid = os.getuid()
        self.destination = self.root / "backups"
        self.destination.mkdir(mode=0o700)
        self.password = self.file("pgpass", "127.0.0.1:5547:buycycle:buycycle_backup:synthetic-password\n")
        self.recipients = self.file("recipients", "age1" + "q" * 58 + "\n")
        self.dump = self.executable(
            "pg_dump", "import sys\nif '--version' in sys.argv: print('pg_dump (PostgreSQL) 17.6')\nelse: sys.stdout.buffer.write(b'PGDMPsynthetic-records')\n"
        )
        self.age = self.executable("age", "import sys\nsys.stdout.buffer.write(b'FAKE-AGE-BOUNDARY\\n'+sys.stdin.buffer.read())\n")
        self.psql = self.executable("psql", "import sys\nprint('psql (PostgreSQL) 17.6' if '--version' in sys.argv else '170006')\n")
        self.restore = self.executable("pg_restore", "print('pg_restore (PostgreSQL) 17.6')\n")
        self.config = {
            "schema_version": 1,
            "host": "127.0.0.1",
            "port": 5547,
            "database": "buycycle",
            "username": "buycycle_backup",
            "pgpassfile": str(self.password),
            "destination": str(self.destination),
            "recipients_file": str(self.recipients),
            "source_commit": "a" * 40,
            "timeout_seconds": 5,
            "pg_dump": str(self.dump),
            "pg_restore": str(self.restore),
            "psql": str(self.psql),
            "postgres_major": 17,
            "age": str(self.age),
        }

    def file(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content)
        path.chmod(0o600)
        return path

    def executable(self, name: str, content: str) -> Path:
        path = self.file(name, f"#!{sys.executable}\n{content}")
        path.chmod(0o700)
        return path

    def run_backup(self) -> Path:
        return backup(self.config, uid=self.uid)

    def test_pipeline_publishes_only_ciphertext_manifest_and_private_permissions(self):
        final = self.run_backup()
        self.assertEqual(sorted(path.name for path in final.iterdir()), ["database.dump.age", "manifest.json"])
        encrypted = final / "database.dump.age"
        manifest = json.loads((final / "manifest.json").read_text())
        self.assertEqual(manifest["sha256"], hashlib.sha256(encrypted.read_bytes()).hexdigest())
        self.assertEqual(manifest["bytes"], encrypted.stat().st_size)
        self.assertEqual(manifest["source_commit"], "a" * 40)
        self.assertEqual(manifest["postgres_major"], 17)
        self.assertEqual(manifest["server_version_num"], 170006)
        self.assertEqual(stat.S_IMODE(final.stat().st_mode), 0o700)
        for path in final.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertFalse(list(self.destination.glob(".incomplete-*")))
        second = self.run_backup()
        self.assertTrue(final.exists())
        self.assertNotEqual(final, second)

    def test_partial_dump_or_failed_encryption_never_publishes_backup(self):
        for failure in ("dump", "age"):
            with self.subTest(failure=failure):
                if failure == "dump":
                    self.executable(
                        "pg_dump", "import sys\nif '--version' in sys.argv: print('pg_dump (PostgreSQL) 17.6')\nelse:\n sys.stdout.buffer.write(b'partial')\n sys.exit(1)\n"
                    )
                else:
                    self.executable("age", "import sys\nsys.stdout.buffer.write(b'partial-ciphertext')\nsys.exit(1)\n")
                with self.assertRaises(OpsError):
                    self.run_backup()
                self.assertEqual(list(self.destination.iterdir()), [])

    def test_wrong_host_database_or_role_rejected_before_any_process(self):
        for name, value in (("host", "production.example.com"), ("host", "localhost"), ("database", "another_app"), ("username", "postgres"), ("port", True)):
            with self.subTest(name=name, value=value), self.assertRaises(OpsError):
                backup({**self.config, name: value}, uid=self.uid)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_symlink_relative_writable_or_wrong_owner_paths_rejected(self):
        linked = self.root / "link"
        linked.symlink_to(self.destination, target_is_directory=True)
        for destination in ("relative", str(linked), str(self.destination / "../backups")):
            with self.subTest(destination=destination), self.assertRaises(OpsError):
                backup({**self.config, "destination": destination}, uid=self.uid)
        self.destination.chmod(0o750)
        with self.assertRaises(OpsError):
            self.run_backup()
        with self.assertRaises(OpsError):
            protected_path(self.password, uid=self.uid + 1)

    def test_unsafe_password_or_wildcard_scope_rejected(self):
        self.password.chmod(0o644)
        with self.assertRaises(OpsError):
            self.run_backup()
        self.password.chmod(0o600)
        for text in ("*:*:*:*:synthetic\n", "127.0.0.1:5547:buycycle:buycycle_backup:\n", self.password.read_text() * 2):
            self.password.write_text(text)
            with self.subTest(text_length=len(text)), self.assertRaises(OpsError):
                self.run_backup()

    def test_only_public_recipients_and_matching_major_allowed(self):
        self.recipients.write_text("AGE-SECRET-KEY-SYNTHETIC\n")
        with self.assertRaises(OpsError):
            self.run_backup()
        self.recipients.write_text("age1" + "q" * 58 + "\n")
        self.executable("pg_dump", "print('pg_dump (PostgreSQL) 18.0')\n")
        with self.assertRaises(OpsError):
            self.run_backup()

    def test_explicit_pg15_clients_and_server_are_supported(self):
        self.config["postgres_major"] = 15
        self.executable("pg_dump", "import sys\nif '--version' in sys.argv: print('pg_dump (PostgreSQL) 15.19')\nelse: sys.stdout.buffer.write(b'PGDMPfixture')\n")
        self.executable("pg_restore", "print('pg_restore (PostgreSQL) 15.19')\n")
        self.executable("psql", "import sys\nprint('psql (PostgreSQL) 15.19' if '--version' in sys.argv else '150019')\n")
        manifest = json.loads((self.run_backup() / "manifest.json").read_text())
        self.assertEqual(manifest["postgres_major"], 15)
        self.assertEqual(manifest["server_version_num"], 150019)

    def test_missing_major_or_mismatched_client_server_is_rejected(self):
        for value in (None, True, 16, 18, "15"):
            with self.subTest(value=value), self.assertRaises(OpsError):
                backup({**self.config, "postgres_major": value}, uid=self.uid)
        for name in ("pg_dump", "pg_restore", "psql"):
            self.executable(name, f"print('{name} (PostgreSQL) 15.19')\n")
            with self.subTest(client=name), self.assertRaises(OpsError):
                self.run_backup()
            self.executable(name, f"print('{name} (PostgreSQL) 17.6')\n")
        self.executable("psql", "import sys\nprint('psql (PostgreSQL) 17.6' if '--version' in sys.argv else '150019')\n")
        with self.assertRaises(OpsError):
            self.run_backup()
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_subprocess_environment_has_no_password_or_inherited_remote_configuration(self):
        args, env = local_database(self.config, uid=self.uid)
        self.assertNotIn("PGPASSWORD", env)
        self.assertNotIn("DATABASE_URL", env)
        self.assertNotIn("synthetic-password", str(args) + str(env))
        self.assertEqual(env["PGPASSFILE"], str(self.password))
        config_file = self.file("backup.json", json.dumps(self.config))
        self.assertEqual(read_config(config_file, uid=self.uid)["database"], "buycycle")
        config_file.chmod(0o644)
        with self.assertRaises(OpsError):
            read_config(config_file, uid=self.uid)


if __name__ == "__main__":
    unittest.main()
