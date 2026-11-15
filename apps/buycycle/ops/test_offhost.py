"""Synthetic restic boundary: no remote repository, credentials or notifications."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import offhost
from ops_common import OpsError


class OffhostTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.uid = os.getuid()
        self.source = self.root / "backups"
        self.state = self.root / "state"
        for path in (self.source, self.state):
            path.mkdir(mode=0o700)
        self.snapshot = self.source / "buycycle-20261115T053000Z-fixture"
        self.snapshot.mkdir(mode=0o700)
        self.cipher = b"synthetic-age-ciphertext-no-real-data"
        self.file(self.snapshot / "database.dump.age", self.cipher)
        self.manifest = {
            "schema_version": 1,
            "database": "buycycle",
            "format": "pg_dump-custom+age",
            "created_at": datetime.now(UTC).isoformat(),
            "source_commit": "a" * 40,
            "bytes": len(self.cipher),
            "sha256": hashlib.sha256(self.cipher).hexdigest(),
        }
        self.file(self.snapshot / "manifest.json", json.dumps(self.manifest).encode())
        self.key = self.file(self.root / "identity", b"synthetic-key-not-an-identity")
        self.known = self.file(self.root / "known-hosts", b"synthetic-pinned-host-key")
        self.fixed_ssh = {**offhost.FIXED_SSH, "identityfile": str(self.key), "userknownhostsfile": str(self.known)}
        self.ssh_text = "\n".join(f"{key} {value}" for key, value in {**self.fixed_ssh, "hostname": "backup.example.invalid", "user": "backup_user", "port": "22"}.items())
        self.ssh = self.file(self.root / "ssh.conf", self.ssh_text.encode())
        self.repository = self.file(self.root / "repository", b"sftp:buycycle-backup:/backup/repo\n")
        self.password = self.file(self.root / "password", b"synthetic-no-real-secret")
        self.binary = self.file(self.root / "restic", b"synthetic-binary-boundary")
        self.config = {
            "schema_version": 1,
            "restic": str(self.binary),
            "repository_file": str(self.repository),
            "password_file": str(self.password),
            "ssh_config": str(self.ssh),
            "state_directory": str(self.state),
            "backup_directory": str(self.source),
            "backup_max_age_seconds": 86400,
            "maximum_ciphertext_bytes": 1024,
            "timeout_seconds": 60,
        }
        self.calls = []
        self.change = None

    def file(self, path, value):
        path.write_bytes(value)
        path.chmod(0o600)
        return path

    def fake(self, command, *, deadline, limit=65536, destination=None):
        self.assertGreater(deadline, time.monotonic())
        self.calls.append(command)
        if "backup" in command:
            self.tag = command[command.index("--", command.index("backup")) - 1]
            self.assertEqual(command[-1], str(self.snapshot))
            return json.dumps({"message_type": "summary", "snapshot_id": "f" * 64 if self.change != "id" else "short"}).encode()
        if "cat" in command:
            return json.dumps({"paths": [str(self.snapshot)] if self.change != "path" else ["/other-app"], "hostname": offhost.HOST, "tags": [offhost.TAG, self.tag]}).encode()
        if command[-1].endswith("manifest.json"):
            return (self.snapshot / "manifest.json").read_bytes() if self.change != "manifest" else b"changed"
        self.assertEqual(limit, len(self.cipher))
        self.assertTrue(destination.is_relative_to(self.state))
        destination.write_bytes(self.cipher if self.change != "cipher" else b"changed")
        return b""

    def copy(self):
        with patch.dict(offhost.FIXED_SSH, self.fixed_ssh), patch("offhost.restic", self.fake):
            return offhost.copy_backup(self.config, uid=self.uid)

    def test_snapshot_and_both_readbacks_are_verified_before_receipt_and_no_source_changes(self):
        before = {path.name: path.read_bytes() for path in self.snapshot.iterdir()}
        receipt = self.copy()
        self.assertEqual(receipt["snapshot_id"], "f" * 64)
        self.assertEqual(receipt["ciphertext_sha256"], self.manifest["sha256"])
        self.assertEqual(json.loads((self.state / "latest.json").read_text()), receipt)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.snapshot.iterdir()})
        self.assertEqual([path.name for path in self.state.iterdir()], ["latest.json"])
        self.assertEqual(len(self.calls), 4)
        for command in self.calls:
            self.assertNotIn("synthetic-no-real-secret", " ".join(command))
            self.assertIn("--repository-file", command)
            self.assertIn("--password-file", command)
            self.assertIn("--no-cache", command)
            self.assertFalse(set(command) & {"prune", "forget", "unlock", "init", "restore"})

    def test_wrong_snapshot_path_manifest_or_cipher_preserves_old_receipt_and_local_backup(self):
        self.copy()
        old = (self.state / "latest.json").read_bytes()
        for change in ("id", "path", "manifest", "cipher"):
            self.change = change
            with self.subTest(change=change), self.assertRaises(OpsError):
                self.copy()
            self.assertEqual((self.state / "latest.json").read_bytes(), old)
            self.assertEqual((self.snapshot / "database.dump.age").read_bytes(), self.cipher)
            self.assertFalse(list(self.state.glob("verify-*")))

    def test_ssh_directives_cannot_inject_commands_disable_host_verification_or_select_other_identity(self):
        for line in ("ProxyCommand arbitrary", "Include /other/config", "LocalCommand arbitrary", "StrictHostKeyChecking no", "IdentityFile /other/key"):
            self.ssh.write_text(self.ssh_text + "\n" + line)
            with self.subTest(line=line), patch.dict(offhost.FIXED_SSH, self.fixed_ssh), self.assertRaises(OpsError):
                offhost.connection_files(self.config, uid=self.uid)
        self.assertEqual(self.calls, [])

    def test_repository_file_rejects_local_backends_alias_changes_options_shell_syntax_and_traversal(self):
        for value in (
            "/local/repo",
            "s3:secret-bucket",
            "sftp:other:/repo",
            "sftp:buycycle-backup:/repo;command",
            "sftp:buycycle-backup:/../repo",
            "sftp:buycycle-backup:/repo --option command",
        ):
            self.repository.write_text(value)
            with self.subTest(value=value), patch.dict(offhost.FIXED_SSH, self.fixed_ssh), self.assertRaises(OpsError):
                offhost.connection_files(self.config, uid=self.uid)

    def test_bad_local_hash_size_bound_or_extra_files_never_start_remote_copy(self):
        self.config["maximum_ciphertext_bytes"] = 1
        with self.assertRaises(OpsError):
            self.copy()
        self.config["maximum_ciphertext_bytes"] = 1024
        self.file(self.snapshot / "unrelated", b"never-copy")
        with self.assertRaises(OpsError):
            self.copy()
        (self.snapshot / "unrelated").unlink()
        (self.snapshot / "database.dump.age").write_bytes(b"bad")
        with self.assertRaises(OpsError):
            self.copy()
        self.assertEqual(self.calls, [])

    def test_bounded_command_runner_sanitizes_environment_and_does_not_log_stderr(self):
        with patch.dict(os.environ, {"RESTIC_PASSWORD": "must-not-be-inherited"}):
            value = offhost.restic([sys.executable, "-c", "import os; print('RESTIC_PASSWORD' in os.environ)"], deadline=time.monotonic() + 10)
        self.assertEqual(value.strip(), b"False")
        with self.assertRaises(OpsError):
            offhost.restic([sys.executable, "-c", "print('x'*1000)"], deadline=time.monotonic() + 10, limit=10)
        with self.assertRaises((OpsError, subprocess.TimeoutExpired)):
            offhost.restic([sys.executable, "-c", "import time; time.sleep(30)"], deadline=time.monotonic() + 0.05)
        with self.assertRaisesRegex(OpsError, "command failed"):
            offhost.restic([sys.executable, "-c", "import sys; print('never expose secret',file=sys.stderr); sys.exit(7)"], deadline=time.monotonic() + 10)


if __name__ == "__main__":
    unittest.main()
