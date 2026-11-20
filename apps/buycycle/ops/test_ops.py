"""Exercise the private operations boundary without production credentials.

Compose config is parsed by Docker without starting containers or networks.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

OPS = Path(__file__).resolve().parent


def run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=30, **kwargs)


class ComposeAndEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("docker"):
            raise RuntimeError("Docker Compose is required to parse the production configuration")
        cls.temp = tempfile.TemporaryDirectory(prefix="buycycle-compose-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        envfile = root / "fixture.env"
        cls.image = "ghcr.io/f0rge/buycycle@sha256:" + "a" * 64
        envfile.write_text(
            "BUYCYCLE_IMAGE=" + cls.image + "\nACCESS_ISSUER=https://synthetic.cloudflareaccess.com\n"
            "ACCESS_AUDIENCE=synthetic-audience\nACCESS_ALLOWED_EMAILS=owner@example.test\n"
            "BUYCYCLE_DATABASE_NETWORK=buycycle-synthetic-existing-network\nBUYCYCLE_SECRETS_DIR=" + str(root / "secrets") + "\n"
        )
        result = run(
            "docker",
            "compose",
            "--env-file",
            str(envfile),
            "--file",
            str(OPS / "compose.yml"),
            "--profile",
            "*",
            "config",
            "--format",
            "json",
            env={"PATH": os.environ["PATH"]},
        )
        cls.config = json.loads(result.stdout)

    def test_private_origin_and_application_credentials_are_separate(self):
        services = self.config["services"]
        self.assertLessEqual({"app", "postgres", "migrate", "tunnel"}, set(services))
        self.assertLessEqual(set(services), {"app", "postgres", "migrate", "tunnel", "collector"})
        for name, service in services.items():
            with self.subTest(service=name):
                ports = service.get("ports", [])
                if name == "postgres":
                    self.assertLessEqual(len(ports), 1)
                    for port in ports:
                        self.assertEqual(port["host_ip"], "127.0.0.1")
                        self.assertEqual(str(port["published"]), "5547")
                        self.assertEqual(port["target"], 5432)
                        self.assertEqual(port["protocol"], "tcp")
                else:
                    self.assertFalse(ports)
                self.assertNotIn("docker.sock", json.dumps(service))
        self.assertEqual(services["app"]["image"], self.image)
        self.assertEqual({s["source"] for s in services["app"]["secrets"]}, {"runtime_database_url"})
        self.assertEqual({s["source"] for s in services["migrate"]["secrets"]}, {"migrator_database_url"})
        self.assertEqual({s["source"] for s in services["tunnel"]["secrets"]}, {"tunnel_token"})
        environment = services["app"]["environment"]
        self.assertEqual(environment["BUYCYCLE_COLLECTION_ENABLED"], "0")
        self.assertNotIn("BUYCYCLE_ENV", environment)
        self.assertNotIn("MIGRATION_DATABASE_URL", environment)
        self.assertNotIn("DATABASE_URL", environment)
        self.assertTrue(environment["ACCESS_ISSUER"].startswith("https://"))
        self.assertTrue(self.config["networks"]["origin"]["internal"])
        self.assertTrue(self.config["networks"]["data"]["external"])

    def test_postgres_bootstrap_and_schema_migration_are_explicit_profiles(self):
        services = self.config["services"]
        self.assertEqual(services["postgres"]["profiles"], ["bootstrap-cluster"])
        self.assertEqual(services["migrate"]["profiles"], ["maintenance"])
        self.assertEqual(services["migrate"]["command"], ["migrate", "--grant-runtime"])
        self.assertFalse(services["app"].get("depends_on", {}).get("postgres"))
        for name in ("app", "migrate", "tunnel"):
            service = services[name]
            self.assertIs(service["read_only"], True)
            self.assertEqual(service["cap_drop"], ["ALL"])
            self.assertIn("no-new-privileges:true", service["security_opt"])

    def test_entrypoint_selects_secret_files_without_evaluating_or_logging_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, migrator = root / "runtime secret", root / "migrator secret"
            values = {
                "DATABASE_URL": "postgres://runtime:synthetic-$(touch SHOULD_NOT_EXIST)@db/app",
                "MIGRATION_DATABASE_URL": "postgres://migrator:synthetic-`touch SHOULD_NOT_EXIST`@db/app",
            }
            runtime.write_text(values["DATABASE_URL"])
            migrator.write_text(values["MIGRATION_DATABASE_URL"])
            probe = "import hashlib,json,os; print(json.dumps({k:hashlib.sha256(os.environ.get(k,'').encode()).hexdigest() for k in ('DATABASE_URL','MIGRATION_DATABASE_URL')}))"
            for selected in ("runtime", "migrator", "both"):
                environment = {"PATH": os.environ["PATH"]}
                expected = dict.fromkeys(values, hashlib.sha256(b"").hexdigest())
                if selected in ("runtime", "both"):
                    environment["BUYCYCLE_DATABASE_URL_FILE"] = str(runtime)
                    expected["DATABASE_URL"] = hashlib.sha256(values["DATABASE_URL"].encode()).hexdigest()
                if selected in ("migrator", "both"):
                    environment["BUYCYCLE_MIGRATION_DATABASE_URL_FILE"] = str(migrator)
                    expected["MIGRATION_DATABASE_URL"] = hashlib.sha256(values["MIGRATION_DATABASE_URL"].encode()).hexdigest()
                result = run("sh", str(OPS / "entrypoint.sh"), sys.executable, "-c", probe, env=environment, cwd=root)
                self.assertEqual(json.loads(result.stdout), expected)
                self.assertEqual(result.stderr, "")
                self.assertFalse((root / "SHOULD_NOT_EXIST").exists())
                self.assertNotIn("synthetic-", result.stdout)

    def test_missing_secret_fails_before_command_and_shell_scripts_parse(self):
        result = subprocess.run(
            ["sh", str(OPS / "entrypoint.sh"), "printf", "COMMAND_RAN"],
            env={"PATH": os.environ["PATH"], "BUYCYCLE_DATABASE_URL_FILE": "/not-a-buycycle-secret"},
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("COMMAND_RAN", result.stdout)
        run("sh", "-n", str(OPS / "entrypoint.sh"))
        run("bash", "-n", str(OPS / "init-db.sh"))


if __name__ == "__main__":
    unittest.main()
