"""Host-only fixtures for approved dispatch and read-only failure signals."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from collect import TARGET, collect
from monitor import check_backup, monitor
from ops_common import OpsError

IMAGE = "ghcr.io/f0rge/buycycle@sha256:" + "d" * 64
COMMIT = "c" * 40
CONTAINER = "e" * 64
LOCAL_IMAGE = "sha256:" + "f" * 64


class ScheduleMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.uid = os.getuid()
        self.compose = self.file("compose.yml", "name: buycycle\n")
        self.environment = self.file("runtime.env", "BUYCYCLE_IMAGE=old@sha256:untrusted-old-value\n")
        self.docker = self.file("docker", "synthetic-docker-boundary\n")
        self.activation = self.file(
            "activation.json",
            json.dumps({"schema_version": 1, "enabled": True, "legacy_scheduler_disabled": True, "budget_import_verified": True, "source_commit": COMMIT, "image": IMAGE}),
        )
        self.receipt = {
            "version": 1,
            "state": "verified",
            "target": TARGET,
            "commit": COMMIT,
            "image": IMAGE,
            "config_digest": "sha256:" + "a" * 64,
            "image_id": LOCAL_IMAGE,
            "container_id": CONTAINER,
            "docker_engine_id": "synthetic-local-engine",
            "compose_sha256": hashlib.sha256(self.compose.read_bytes()).hexdigest(),
            "managed_env_sha256": hashlib.sha256(self.environment.read_bytes()).hexdigest(),
        }
        provider = {
            "passed": True,
            "commit": COMMIT,
            "target": TARGET,
            "legacy_collector_fenced": True,
            "source_builds_disabled": True,
            "origin_unpublished": True,
            "access_policy_verified": True,
            "database_grants_verified": True,
            "managed_secrets_verified": True,
            **{key: self.receipt[key] for key in ("docker_engine_id", "compose_sha256", "managed_env_sha256")},
        }
        self.provider = self.file("provider.json", json.dumps(provider))
        self.migration = self.file("migration.json", json.dumps({"passed": True, "commit": COMMIT, "target": TARGET}))
        self.receipt["receipt_hashes"] = {"provider": hashlib.sha256(self.provider.read_bytes()).hexdigest(), "migration": hashlib.sha256(self.migration.read_bytes()).hexdigest()}
        self.active = self.file("active.json", json.dumps(self.receipt))
        activation = json.loads(self.activation.read_text())
        self.activation.write_text(
            json.dumps(
                {
                    **activation,
                    "active_release_sha256": hashlib.sha256(self.active.read_bytes()).hexdigest(),
                    **{f"{kind}_receipt_sha256": digest for kind, digest in self.receipt["receipt_hashes"].items()},
                }
            )
        )
        self.config = {
            "docker": str(self.docker),
            "compose_file": str(self.compose),
            "env_file": str(self.environment),
            "source_commit": COMMIT,
            "image": IMAGE,
            "activation_file": str(self.activation),
            "active_release_receipt": str(self.active),
            "provider_receipt": str(self.provider),
            "migration_receipt": str(self.migration),
            "timeout_seconds": 600,
        }
        self.backups = self.root / "backups"
        self.backups.mkdir(mode=0o700)
        self.snapshot = self.backups / "buycycle-20261115T060000Z-fixture"
        self.snapshot.mkdir(mode=0o700)
        self.ciphertext = self.snapshot / "database.dump.age"
        self.ciphertext.write_bytes(b"synthetic-encrypted-boundary")
        self.ciphertext.chmod(0o600)
        self.manifest = {
            "schema_version": 1,
            "database": "buycycle",
            "format": "pg_dump-custom+age",
            "created_at": datetime.now(UTC).isoformat(),
            "source_commit": COMMIT,
            "bytes": self.ciphertext.stat().st_size,
            "sha256": hashlib.sha256(self.ciphertext.read_bytes()).hexdigest(),
        }
        self.write_manifest()
        self.password = self.file("pgpass", "127.0.0.1:5547:buycycle:buycycle_backup:synthetic-password\n")
        self.psql = self.file("psql", "synthetic-psql-boundary\n")
        self.config.update(
            host="127.0.0.1",
            port=5547,
            database="buycycle",
            username="buycycle_backup",
            pgpassfile=str(self.password),
            psql=str(self.psql),
            backup_directory=str(self.backups),
            backup_max_age_seconds=3600,
            collection_max_age_seconds=86400,
            memory_max_percent=85,
            disk_max_percent=99,
        )
        self.calls = []
        self.response_changes = {}

    def file(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content)
        path.chmod(0o600)
        return path

    def write_manifest(self):
        path = self.snapshot / "manifest.json"
        path.write_text(json.dumps(self.manifest))
        path.chmod(0o600)

    def command(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[0] == str(self.psql):
            kind, payload = "collection", "3600\n"
        elif "info" in args:
            kind, payload = "engine", "synthetic-local-engine"
        elif "ps" in args:
            kind, payload = "container", CONTAINER + "\n"
        elif args[1] == "inspect":
            kind, payload = "inspect", [{"Image": LOCAL_IMAGE, "Config": {"Image": IMAGE}, "State": {"Health": {"Status": "healthy"}}}]
        elif args[1:3] == ["image", "inspect"]:
            kind, payload = "image", [{"Id": LOCAL_IMAGE, "RepoDigests": [IMAGE], "Config": {"Labels": {"org.opencontainers.image.revision": COMMIT}}}]
        elif "exec" in args:
            kind = "ready" if args[-1].endswith("/ready") else "health"
            payload = {"status": "ready", "source_commit": COMMIT}
        elif "stats" in args:
            kind, payload = "stats", {"MemPerc": "15.0%"}
        elif "config" in args:
            kind, payload = "config", {"services": {"collector": {"image": IMAGE, "command": ["collect"], "environment": {"BUYCYCLE_COLLECTION_ENABLED": "true"}}}}
        elif "run" in args:
            kind, payload = "dispatch", ""
        else:
            raise AssertionError(f"Unexpected host command: {args}")
        payload = self.response_changes.get(kind, payload)
        if isinstance(payload, BaseException):
            raise payload
        raw = payload if kind in {"container", "collection", "dispatch"} else json.dumps(payload)
        return subprocess.CompletedProcess(args, 0, raw.encode(), b"")

    def test_only_active_image_is_dispatched_without_pull_or_secret_environment(self):
        with patch("collect.subprocess.run", self.command):
            collect(self.config, uid=self.uid)
        dispatch = [call for call in self.calls if "run" in call[0]]
        self.assertEqual(len(dispatch), 1)
        args, options = dispatch[0]
        self.assertEqual(args[-6:], ["run", "--rm", "--no-deps", "--pull", "never", "collector"])
        self.assertEqual(options["env"]["BUYCYCLE_IMAGE"], IMAGE)
        self.assertEqual(options["env"]["BUYCYCLE_COLLECTION_ENABLED"], "true")
        self.assertIn("collection", args)
        self.assertEqual(options["env"]["DOCKER_HOST"], "unix:///var/run/docker.sock")
        self.assertNotIn("PGPASSWORD", options["env"])
        self.assertNotIn("BUYCYCLE_API_KEY", options["env"])

    def test_activation_and_release_must_match_before_docker_is_contacted(self):
        for key, value in (("enabled", False), ("legacy_scheduler_disabled", False), ("budget_import_verified", False), ("source_commit", "b" * 40), ("image", "old")):
            original = json.loads(self.activation.read_text())
            self.activation.write_text(json.dumps({**original, key: value}))
            with self.subTest(key=key), patch("collect.subprocess.run", self.command), self.assertRaises(OpsError):
                collect(self.config, uid=self.uid)
            self.assertFalse(self.calls)
            self.activation.write_text(json.dumps(original))
        self.active.write_text(json.dumps({**self.receipt, "state": "running"}))
        with patch("collect.subprocess.run", self.command), self.assertRaises(OpsError):
            collect(self.config, uid=self.uid)
        self.assertFalse(self.calls)

    def test_changed_managed_files_hold_collection(self):
        self.environment.write_text("changed-since-approved-release\n")
        with patch("collect.subprocess.run", self.command), self.assertRaises(OpsError):
            collect(self.config, uid=self.uid)
        self.assertFalse(self.calls)

    def test_changed_provider_or_migration_evidence_holds_collection(self):
        for evidence in (self.provider, self.migration):
            original = evidence.read_bytes()
            evidence.write_text('{"passed":false}')
            with self.subTest(evidence=evidence.name), patch("collect.subprocess.run", self.command), self.assertRaises(OpsError):
                collect(self.config, uid=self.uid)
            self.assertFalse(self.calls)
            evidence.write_bytes(original)

    def test_activation_is_bound_to_exact_active_receipt_bytes(self):
        self.active.write_text(json.dumps(self.receipt, indent=2))
        with patch("collect.subprocess.run", self.command), self.assertRaises(OpsError):
            collect(self.config, uid=self.uid)
        self.assertFalse(self.calls)

    def test_changed_engine_api_or_rendered_job_never_dispatches(self):
        changes = {
            "engine": "different-engine",
            "container": "a" * 64,
            "inspect": [{"Image": LOCAL_IMAGE, "Config": {"Image": IMAGE}, "State": {"Health": {"Status": "unhealthy"}}}],
            "image": [{"Id": "sha256:" + "b" * 64, "RepoDigests": [IMAGE], "Config": {"Labels": {"org.opencontainers.image.revision": COMMIT}}}],
            "health": {"source_commit": "b" * 40},
            "config": {"services": {"collector": {"image": IMAGE, "command": ["collect", "--force"], "environment": {"BUYCYCLE_COLLECTION_ENABLED": "true"}}}},
        }
        for kind, response in changes.items():
            self.calls = []
            self.response_changes = {kind: response}
            with self.subTest(kind=kind), patch("collect.subprocess.run", self.command), self.assertRaises(OpsError):
                collect(self.config, uid=self.uid)
            self.assertFalse(any("run" in args for args, _ in self.calls))

    def test_monitor_only_reads_health_resource_completion_and_backup_status(self):
        with patch("monitor.subprocess.run", self.command):
            monitor(self.config, uid=self.uid)
        self.assertFalse(any("run" in args for args, _ in self.calls))
        query = next(args for args, _ in self.calls if args[0] == str(self.psql))
        self.assertIn("--no-psqlrc", query)
        self.assertIn("WHERE complete", query[-1])
        self.assertNotIn("payload", query[-1])

    def test_monitor_rejects_health_memory_and_stale_collection(self):
        for kind, response in (("ready", {"status": "unready"}), ("stats", {"MemPerc": "99.0%"}), ("collection", "-1\n"), ("collection", "86401\n")):
            self.response_changes = {kind: response}
            with self.subTest(kind=kind, response=response), patch("monitor.subprocess.run", self.command), self.assertRaises(OpsError):
                monitor(self.config, uid=self.uid)

    def test_backup_freshness_checksum_and_partial_directory_fail_closed(self):
        check_backup(self.config, uid=self.uid)
        self.ciphertext.write_bytes(b"tampered")
        with self.assertRaises(OpsError):
            check_backup(self.config, uid=self.uid)
        self.ciphertext.write_bytes(b"synthetic-encrypted-boundary")
        self.manifest["created_at"] = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        self.write_manifest()
        with self.assertRaises(OpsError):
            check_backup(self.config, uid=self.uid)
        self.snapshot.rename(self.backups / ".incomplete-fixture")
        with self.assertRaises(OpsError):
            check_backup(self.config, uid=self.uid)

    def test_collection_timer_preserves_local_time_and_never_catches_up(self):
        ops = Path(__file__).resolve().parent
        timer = (ops / "buycycle-collect.timer").read_text()
        self.assertIn("OnCalendar=*-*-* 06:15:00 Europe/Luxembourg", timer)
        self.assertIn("Persistent=false", timer)
        service = (ops / "buycycle-collect.service").read_text()
        self.assertIn("ConditionPathExists=/etc/buycycle/collector-activation.json", service)
        self.assertNotIn("Restart=", service)


if __name__ == "__main__":
    unittest.main()
