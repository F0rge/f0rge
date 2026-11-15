"""Read-only provider response fixtures; no live tokens, data or operations."""

from __future__ import annotations

import contextlib
import copy
import datetime as dt
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import preflight


class ProviderFixture:
    def __init__(self, directory: Path):
        self.compose_path, self.env_path = directory / "compose.yml", directory / "runtime.env"
        self.compose_path.write_text("synthetic immutable compose")
        self.env_path.write_text("synthetic non-secret environment")
        self.config = {
            "app": preflight.APP,
            "project_name": "buycycle",
            "commit": "a" * 40,
            "domain": preflight.DOMAIN,
            "access_issuer": "https://fixture.cloudflareaccess.com",
            "access_audience": "synthetic-audience",
            "owner_email": "owner@example.invalid",
            "cf_account_id": "a" * 32,
            "cf_zone_id": "b" * 32,
            "cf_application_id": "11111111-1111-1111-1111-111111111111",
            "otp_provider_id": "22222222-2222-2222-2222-222222222222",
            "access_policy_id": "33333333-3333-3333-3333-333333333333",
            "tunnel_id": "44444444-4444-4444-4444-444444444444",
            "compose_path": str(self.compose_path),
            "managed_env_file": str(self.env_path),
            "compose_sha256": preflight.digest(self.compose_path),
            "managed_env_sha256": preflight.digest(self.env_path),
            "expected_docker_engine_id": "fixture-local-engine",
            "journal_dir": str(directory / "journal"),
            "database_network": "platform_database",
            "cloudflare_token_file": "/managed/cf-token",
            "coolify_token_file": "/managed/coolify-token",
            "coolify_base_url": "https://fixture.invalid/api/v1",
            "postgres_container": "platform-postgres",
            "secret_owners": {"/managed/runtime-url": 10001, "/managed/migrator-url": 10001, "/managed/tunnel-token": 65532},
        }
        self.application = {
            "id": self.config["cf_application_id"],
            "type": "self_hosted",
            "domain": preflight.DOMAIN,
            "aud": self.config["access_audience"],
            "allowed_idps": [self.config["otp_provider_id"]],
            "use_all_idps": False,
            "options_preflight_bypass": False,
            "allow_authenticate_via_warp": False,
        }
        self.policies = [{"id": self.config["access_policy_id"], "decision": "allow", "include": [{"email": {"email": self.config["owner_email"]}}], "exclude": [], "require": []}]
        self.identity = {"id": self.config["otp_provider_id"], "type": "onetimepin"}
        self.tunnel = {"id": self.config["tunnel_id"], "status": "healthy"}
        self.routes = {"config": {"ingress": [{"hostname": preflight.DOMAIN, "service": "http://app:8080"}, {"service": "http_status:404"}]}}
        self.dns = [{"name": preflight.DOMAIN, "type": "CNAME", "proxied": True, "content": self.config["tunnel_id"] + ".cfargotunnel.com"}]
        self.legacy = {
            "uuid": preflight.APP,
            "status": "exited:unhealthy",
            "settings": {"is_auto_deploy_enabled": False, "is_preview_deployments_enabled": False},
            "manual_webhook_secret_github": None,
            "manual_webhook_secret_gitlab": None,
            "manual_webhook_secret_bitbucket": None,
            "manual_webhook_secret_gitea": None,
        }
        self.tasks = []
        self.containers = [{"id": "c" * 64, "name": "/platform-postgres", "labels": {}, "running": True, "restart": "unless-stopped", "ports": {}, "image": "postgres:17-bookworm"}]
        base = {"read_only": True, "cap_drop": ["ALL"], "image": "ghcr.io/f0rge/buycycle@sha256:" + "e" * 64}
        self.compose = {
            "services": {
                "app": {
                    **base,
                    "secrets": [{"source": "runtime_database_url"}],
                    "environment": {
                        "ACCESS_ISSUER": self.config["access_issuer"],
                        "ACCESS_AUDIENCE": self.config["access_audience"],
                        "ACCESS_ALLOWED_EMAILS": self.config["owner_email"],
                        "BUYCYCLE_COLLECTION_ENABLED": "0",
                    },
                },
                "migrate": {**base, "secrets": [{"source": "migrator_database_url"}], "command": ["migrate", "--grant-runtime"], "profiles": ["maintenance"]},
                "tunnel": {**base, "secrets": [{"source": "tunnel_token"}]},
            },
            "networks": {"data": {"external": True, "name": self.config["database_network"]}},
            "secrets": {
                "runtime_database_url": {"file": "/managed/runtime-url"},
                "migrator_database_url": {"file": "/managed/migrator-url"},
                "tunnel_token": {"file": "/managed/tunnel-token"},
            },
        }
        self.grants, self.engine = {"passed": True}, {"ID": self.config["expected_docker_engine_id"], "Architecture": "arm64", "OSType": "linux"}
        self.files_seen, self.urls, self.commands = [], [], []

    @staticmethod
    def response(value):
        result = {"success": True, "result": value}
        if isinstance(value, list):
            result["result_info"] = {"total_count": len(value), "total_pages": 1}
        return result

    def fetch(self, url, token_file):
        self.urls.append((url, token_file))
        if "/applications/" in url:
            return self.tasks if url.endswith("/scheduled-tasks") else self.legacy
        if url.endswith("/organizations"):
            return self.response({"auth_domain": "fixture.cloudflareaccess.com"})
        if "/policies?" in url:
            return self.response(self.policies)
        if "/identity_providers/" in url:
            return self.response(self.identity)
        if url.endswith("/configurations"):
            return self.response(self.routes)
        if "/cfd_tunnel/" in url:
            return self.response(self.tunnel)
        if "/dns_records?" in url:
            return self.response(self.dns)
        if "/access/apps/" in url:
            return self.response(self.application)
        raise AssertionError("Unexpected endpoint")

    def read(self, command):
        self.commands.append(command)
        if command[0] == "info":
            return json.dumps(self.engine)
        if command[0] == "ps":
            return "\n".join(container["id"] for container in self.containers)
        if command[0] == "inspect":
            return json.dumps(next(container for container in self.containers if container["id"] == command[-1]))
        if command[0] == "compose":
            return json.dumps(self.compose)
        if command[0] == "exec":
            return json.dumps(self.grants)
        raise AssertionError("Unexpected local command")

    def files(self, path, **kwargs):
        self.files_seen.append((path, kwargs))
        return Path(path)

    def observe(self):
        return preflight.observe(self.config, fetch=self.fetch, read=self.read, files=self.files, directories=Path)

    def access(self):
        preflight.validate_access(self.config, self.application, self.policies, self.identity, self.tunnel, self.routes, self.dns)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.fixture = ProviderFixture(Path(self.directory.name))

    def test_observed_receipt_is_bound_fresh_and_contains_no_identity(self):
        receipt = self.fixture.observe()
        self.assertEqual(receipt["target"], {"host": "pi", "app": preflight.APP})
        self.assertEqual(receipt["commit"], "a" * 40)
        self.assertLess(abs((dt.datetime.now(dt.UTC) - dt.datetime.fromisoformat(receipt["created_at"])).total_seconds()), 5)
        self.assertNotIn("owner@example.invalid", json.dumps(receipt))
        self.assertTrue(all(command[0] in {"info", "ps", "inspect", "compose", "exec"} for command in self.fixture.commands))
        self.assertIn(("/managed/tunnel-token", {"uid": 65532, "secret": True}), self.fixture.files_seen)

    def test_access_wrong_owner_audience_bypass_and_otp_are_denied(self):
        for field, value, reason in [
            ("aud", "other", "access_destination_audience"),
            ("options_preflight_bypass", True, "access_bypass"),
            ("use_all_idps", True, "access_otp_only"),
        ]:
            with self.subTest(field=field):
                previous = self.fixture.application[field]
                self.fixture.application[field] = value
                with self.assertRaisesRegex(preflight.Refused, reason):
                    self.fixture.access()
                self.fixture.application[field] = previous
        self.fixture.policies[0]["include"] = [{"everyone": {}}]
        with self.assertRaisesRegex(preflight.Refused, "access_owner"):
            self.fixture.access()

    def test_extra_or_bypass_policy_is_denied(self):
        self.fixture.policies.append({"decision": "bypass"})
        with self.assertRaisesRegex(preflight.Refused, "access_policy_count"):
            self.fixture.access()

    def test_tunnel_route_and_unproxied_dns_are_denied(self):
        self.fixture.routes["config"]["ingress"][0]["service"] = "http://other:8095"
        with self.assertRaisesRegex(preflight.Refused, "tunnel_origin"):
            self.fixture.access()
        self.fixture.routes["config"]["ingress"][0]["service"] = "http://app:8080"
        self.fixture.dns[0]["proxied"] = False
        with self.assertRaisesRegex(preflight.Refused, "dns_gateway"):
            self.fixture.access()

    def test_unknown_policy_pagination_is_not_complete_evidence(self):
        for info in [{}, {"total_count": 2, "total_pages": 1}, {"total_count": 1, "total_pages": 2}]:
            with self.subTest(info=info), self.assertRaisesRegex(preflight.Refused, "cloudflare_pagination"):
                preflight.cf_result({"success": True, "result": [{}], "result_info": info}, collection=True)

    def test_public_ports_and_local_identity_mode_are_denied(self):
        self.fixture.compose["services"]["app"]["ports"] = [{"published": "8080"}]
        with self.assertRaisesRegex(preflight.Refused, "origin_published"):
            self.fixture.observe()
        self.fixture.compose["services"]["app"].pop("ports")
        self.fixture.compose["services"]["app"]["environment"]["BUYCYCLE_ENV"] = "local"
        with self.assertRaisesRegex(preflight.Refused, "runtime_owner_mode"):
            self.fixture.observe()

    def test_postgres_port_is_loopback_and_fixed_only(self):
        self.fixture.compose["services"]["postgres"] = {
            "profiles": ["bootstrap-cluster"],
            "ports": [{"host_ip": "127.0.0.1", "published": "5547", "target": 5432, "protocol": "tcp"}],
        }
        self.fixture.observe()
        self.fixture.compose["services"]["postgres"]["ports"][0]["host_ip"] = "0.0.0.0"
        with self.assertRaisesRegex(preflight.Refused, "postgres_loopback_only"):
            self.fixture.observe()

    def test_host_mount_root_override_and_mutable_image_are_denied(self):
        for field, value, reason in [
            ("volumes", [{"source": "/", "target": "/host"}], "app_host_authority"),
            ("user", "0", "app_runtime_user"),
            ("image", "buycycle:latest", "compose_pinned_app_image"),
        ]:
            with self.subTest(field=field):
                original = self.fixture.compose["services"]["app"].get(field)
                self.fixture.compose["services"]["app"][field] = value
                with self.assertRaisesRegex(preflight.Refused, reason):
                    self.fixture.observe()
                if original is None:
                    self.fixture.compose["services"]["app"].pop(field)
                else:
                    self.fixture.compose["services"]["app"][field] = original

    def test_docker_uses_same_sanitized_environment_as_release(self):
        with (
            patch.dict(
                "os.environ", {"ACCESS_ISSUER": "hostile", "BUYCYCLE_SECRETS_DIR": "/hostile", "COMPOSE_FILE": "/hostile", "DOCKER_HOST": "tcp://hostile", "GH_TOKEN": "synthetic"}
            ),
            patch.object(preflight.subprocess, "run") as run,
        ):
            run.return_value.stdout = "{}"
            self.assertEqual(preflight.docker(["info"]), "{}")
        self.assertEqual(run.call_args.args[0][:3], ["docker", "--host", "unix:///run/docker.sock"])
        self.assertFalse({"ACCESS_ISSUER", "BUYCYCLE_SECRETS_DIR", "COMPOSE_FILE", "DOCKER_HOST", "GH_TOKEN"} & run.call_args.kwargs["env"].keys())

    def test_wrong_engine_or_database_grants_is_denied(self):
        self.fixture.engine["ID"] = "other-daemon"
        with self.assertRaisesRegex(preflight.Refused, "preflight_engine"):
            self.fixture.observe()
        self.fixture.engine["ID"] = self.fixture.config["expected_docker_engine_id"]
        self.fixture.grants = {"passed": False}
        with self.assertRaisesRegex(preflight.Refused, "database_grants"):
            self.fixture.observe()

    def test_second_platform_postgres_cluster_is_denied(self):
        duplicate = copy.deepcopy(self.fixture.containers[0])
        duplicate.update(id="d" * 64, name="/unapproved-second-postgres")
        self.fixture.containers.append(duplicate)
        with self.assertRaisesRegex(preflight.Refused, "postgres_single_managed_cluster"):
            self.fixture.observe()

    def test_active_legacy_collector_schedule_or_webhook_is_denied(self):
        for mutate, reason in [
            (lambda: self.fixture.legacy["settings"].update(is_auto_deploy_enabled=True), "legacy_auto_deploy"),
            (lambda: self.fixture.tasks.append({"enabled": True}), "legacy_schedules"),
            (lambda: self.fixture.legacy.update(manual_webhook_secret_github="synthetic"), "legacy_webhook"),
            (lambda: self.fixture.legacy.update(status="running:healthy"), "legacy_provider_running"),
        ]:
            with self.subTest(reason=reason):
                self.fixture = ProviderFixture(Path(self.directory.name))
                mutate()
                with self.assertRaisesRegex(preflight.Refused, reason):
                    self.fixture.observe()

    def test_missing_managed_secret_or_wrong_owner_is_denied(self):
        self.fixture.config["secret_owners"].pop("/managed/runtime-url")
        with self.assertRaisesRegex(preflight.Refused, "managed_secret_inventory"):
            self.fixture.observe()
        self.fixture.config["secret_owners"]["/managed/runtime-url"] = 0
        with self.assertRaisesRegex(preflight.Refused, "managed_secret_owner"):
            self.fixture.observe()

    def test_caller_passed_flags_do_not_replace_provider_reads(self):
        self.fixture.config.update(passed=True, access_policy_verified=True, source_builds_disabled=True)
        self.fixture.application["aud"] = "wrong"
        with self.assertRaisesRegex(preflight.Refused, "access_destination_audience"):
            self.fixture.observe()

    def test_active_receipt_is_scoped_but_not_required_before_first_release(self):
        self.fixture.observe()
        self.fixture.config["active_release_receipt"] = "/arbitrary/active.json"
        with self.assertRaisesRegex(preflight.Refused, "active_receipt_path"):
            self.fixture.observe()

    def test_wrong_access_team_issuer_is_denied(self):
        self.fixture.config["access_issuer"] = "https://other.cloudflareaccess.com"
        self.fixture.compose["services"]["app"]["environment"]["ACCESS_ISSUER"] = self.fixture.config["access_issuer"]
        with self.assertRaisesRegex(preflight.Refused, "access_team_issuer"):
            self.fixture.observe()

    def test_no_passed_receipt_written_when_observation_fails(self):
        config_path = Path(self.directory.name) / "config.json"
        config_path.write_text("{}")
        output_path = Path(self.directory.name) / "receipt.json"
        with (
            patch("sys.argv", ["preflight", "--config", str(config_path), "--output", str(output_path)]),
            patch.object(preflight, "managed_file", return_value=config_path),
            patch.object(preflight, "observe", side_effect=preflight.Refused("synthetic_failure")),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            self.assertEqual(preflight.main(), 1)
        self.assertFalse(output_path.exists())
        self.assertEqual(json.loads(stdout.getvalue()), {"passed": False, "reason": "synthetic_failure"})

    def test_managed_symlink_is_rejected_before_reading(self):
        link = Path(self.directory.name) / "symlink"
        link.symlink_to(self.fixture.env_path)
        with self.assertRaisesRegex(preflight.Refused, "managed_path_symlink"):
            preflight.managed_file(str(link))

    def test_grant_query_requires_every_positive_privilege(self):
        query = preflight.database_query()
        self.assertIn("'public.legacy_record','INSERT')", query)
        self.assertIn("'public.legacy_record','UPDATE')", query)
        self.assertNotIn("'SELECT,INSERT,UPDATE'", query)
        self.assertTrue(query.startswith("SELECT json_build_object"))
        self.assertNotIn("PASSWORD", query)


if __name__ == "__main__":
    unittest.main()
