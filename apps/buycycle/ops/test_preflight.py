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
            "coolify_control_plane": {
                "container_id": "f" * 64,
                "image": "ghcr.io/coollabsio/coolify:fixture",
                "image_id": "sha256:" + "8" * 64,
                "compose_project": "source",
                "compose_service": "coolify",
            },
            "postgres_container": "c" * 64,
            "postgres_major": 17,
            "postgres_admin_role": "postgres",
            "postgres_inventory": [
                {
                    "container_id": "c" * 64,
                    "image": "postgres:17-bookworm",
                    "image_id": "sha256:" + "1" * 64,
                    "compose_project": "platform",
                    "compose_service": "postgres",
                    "postgres_major": 17,
                    "classification": "application_data",
                    "purpose": "Synthetic shared application database",
                }
            ],
            "secret_owners": {"/managed/runtime-url": 10001, "/managed/migrator-url": 10001, "/managed/tunnel-token": 65532},
        }
        self.application = {
            "id": self.config["cf_application_id"],
            "type": "self_hosted",
            "domain": preflight.DOMAIN,
            "aud": self.config["access_audience"],
            "allowed_idps": [self.config["otp_provider_id"]],
            "options_preflight_bypass": False,
        }
        self.organization = {"auth_domain": "fixture.cloudflareaccess.com", "allow_authenticate_via_warp": False}
        self.policies = [{"id": self.config["access_policy_id"], "decision": "allow", "include": [{"email": {"email": self.config["owner_email"]}}], "exclude": [], "require": []}]
        self.identity = {"id": self.config["otp_provider_id"], "type": "onetimepin"}
        self.tunnel = {"id": self.config["tunnel_id"], "status": "healthy"}
        self.routes = {"config": {"ingress": [{"hostname": preflight.DOMAIN, "service": "http://app:8080"}, {"service": "http_status:404"}]}}
        self.dns = [{"name": preflight.DOMAIN, "type": "CNAME", "proxied": True, "content": self.config["tunnel_id"] + ".cfargotunnel.com"}]
        self.legacy = {
            "version": 1,
            "uuid": preflight.APP,
            "status": "exited:unhealthy",
            "auto_deploy": False,
            "preview_deploy": False,
            "webhooks_present": dict.fromkeys(("github", "gitlab", "bitbucket", "gitea"), False),
        }
        self.tasks = []
        self.legacy["tasks"] = self.tasks
        self.projection_raw = None
        self.containers = [
            {
                "id": "c" * 64,
                "name": "/platform-postgres",
                "labels": {"com.docker.compose.project": "platform", "com.docker.compose.service": "postgres"},
                "running": True,
                "restart": "unless-stopped",
                "ports": {},
                "image": "postgres:17-bookworm",
                "image_id": "sha256:" + "1" * 64,
            }
        ]
        control = self.config["coolify_control_plane"]
        self.containers.append(
            {
                "id": control["container_id"],
                "name": "/coolify",
                "labels": {"com.docker.compose.project": control["compose_project"], "com.docker.compose.service": control["compose_service"]},
                "running": True,
                "restart": "unless-stopped",
                "ports": {},
                "image": control["image"],
                "image_id": control["image_id"],
            }
        )
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
        self.grants, self.engine = (
            {"passed": True, "server_version_num": 170006, "current_user": "postgres", "current_database": "buycycle"},
            {"ID": self.config["expected_docker_engine_id"], "Architecture": "arm64", "OSType": "linux"},
        )
        self.files_seen, self.urls, self.commands = [], [], []

    @staticmethod
    def response(value):
        result = {"success": True, "result": value}
        if isinstance(value, list):
            result["result_info"] = {"total_count": len(value), "total_pages": 1}
        return result

    def fetch(self, url, token_file):
        self.urls.append((url, token_file))
        if not url.startswith("https://api.cloudflare.com/client/v4/"):
            raise AssertionError("No Coolify API/token request is allowed")
        if url.endswith("/organizations"):
            return self.response(self.organization)
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
            if command[1:3] == ["--workdir", "/var/www/html"]:
                expected = [
                    "exec",
                    "--workdir",
                    "/var/www/html",
                    self.config["coolify_control_plane"]["container_id"],
                    "php",
                    "artisan",
                    "tinker",
                    "--execute=" + preflight.COOLIFY_PROJECTION,
                ]
                if command != expected:
                    raise AssertionError("Only the fixed selected-app metadata projection may execute")
                return self.projection_raw if self.projection_raw is not None else preflight.COOLIFY_PREFIX + json.dumps(self.legacy)
            if command[-2:] == ["postgres", "--version"]:
                entry = next(entry for entry in self.config["postgres_inventory"] if entry["container_id"] == command[1])
                return f"postgres (PostgreSQL) {entry['postgres_major']}.6"
            return json.dumps(self.grants)
        raise AssertionError("Unexpected local command")

    def files(self, path, **kwargs):
        self.files_seen.append((path, kwargs))
        return Path(path)

    def observe(self):
        return preflight.observe(self.config, fetch=self.fetch, read=self.read, files=self.files, directories=Path)

    def access(self):
        preflight.validate_access(self.config, self.application, self.policies, self.identity, self.tunnel, self.routes, self.dns, organization=self.organization)


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
                previous = copy.deepcopy(self.fixture.application)
                self.fixture.application[field] = value
                with self.assertRaisesRegex(preflight.Refused, reason):
                    self.fixture.access()
                self.fixture.application = previous
        self.fixture.policies[0]["include"] = [{"everyone": {}}]
        with self.assertRaisesRegex(preflight.Refused, "access_owner"):
            self.fixture.access()

    def test_exact_nonempty_otp_selection_is_required_without_ui_only_flag(self):
        self.fixture.access()
        missing = object()
        for value in (
            missing,
            None,
            [],
            [self.fixture.config["otp_provider_id"], "other-idp"],
            [self.fixture.config["otp_provider_id"]] * 2,
            ["other-idp"],
            self.fixture.config["otp_provider_id"],
            {},
        ):
            with self.subTest(value=value):
                if value is missing:
                    self.fixture.application.pop("allowed_idps", None)
                else:
                    self.fixture.application["allowed_idps"] = value
                with self.assertRaisesRegex(preflight.Refused, "access_otp_only"):
                    self.fixture.access()
        self.fixture.application["allowed_idps"] = [self.fixture.config["otp_provider_id"]]
        for value in (False, True, None, 0, "false", {}):
            self.fixture.application["use_all_idps"] = value
            with self.subTest(use_all_idps=value):
                if value is False:
                    self.fixture.access()
                else:
                    with self.assertRaisesRegex(preflight.Refused, "access_otp_only"):
                        self.fixture.access()
        self.fixture.application.pop("use_all_idps")
        self.fixture.config["otp_provider_id"] = ""
        self.fixture.application["allowed_idps"] = [""]
        with self.assertRaisesRegex(preflight.Refused, "access_otp_only"):
            self.fixture.access()

    def test_app_warp_override_and_organization_inheritance_matrix(self):
        missing = object()
        values = (missing, False, True, None, 0, "false", {})
        for app_value in values:
            for organization_value in values:
                with self.subTest(app=app_value, organization=organization_value):
                    self.fixture.application.pop("allow_authenticate_via_warp", None)
                    self.fixture.organization.pop("allow_authenticate_via_warp", None)
                    if app_value is not missing:
                        self.fixture.application["allow_authenticate_via_warp"] = app_value
                    if organization_value is not missing:
                        self.fixture.organization["allow_authenticate_via_warp"] = organization_value
                    if app_value is False or (app_value is missing and organization_value is False):
                        self.fixture.access()
                    else:
                        with self.assertRaisesRegex(preflight.Refused, "access_bypass"):
                            self.fixture.access()

    def test_full_observation_uses_parent_warp_setting_when_app_omits_it(self):
        self.fixture.observe()
        self.fixture.organization["allow_authenticate_via_warp"] = True
        with self.assertRaisesRegex(preflight.Refused, "access_bypass"):
            self.fixture.observe()
        self.fixture.application["allow_authenticate_via_warp"] = False
        self.fixture.observe()

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
        with self.assertRaisesRegex(preflight.Refused, "postgres_inventory_incomplete"):
            self.fixture.observe()

    def test_unlisted_digest_pinned_and_registry_qualified_clusters_are_denied(self):
        for image in ("postgres:15.19-bookworm@sha256:" + "f" * 64, "docker.io/library/postgres:16", "registry-1.docker.io/library/postgres@sha256:" + "e" * 64):
            duplicate = copy.deepcopy(self.fixture.containers[0])
            duplicate.update(id="d" * 64, name="/unlisted-postgres", image=image)
            self.fixture.containers.append(duplicate)
            with self.subTest(image=image), self.assertRaisesRegex(preflight.Refused, "postgres_inventory_incomplete"):
                self.fixture.observe()
            self.fixture.containers.pop()

    def test_stopped_control_plane_is_recorded_without_starting_or_executing_it(self):
        entry = dict(
            self.fixture.config["postgres_inventory"][0], container_id="d" * 64, classification="coolify_control_plane", purpose="Synthetic stopped historical control plane"
        )
        self.fixture.config["postgres_inventory"].append(entry)
        stopped = dict(self.fixture.containers[0], id=entry["container_id"], running=False)
        self.fixture.containers.append(stopped)
        receipt = self.fixture.observe()
        observed = next(item for item in receipt["postgres_inventory"] if item["container_id"] == entry["container_id"])
        self.assertFalse(observed["running"])
        self.assertIsNone(observed["observed_version"])
        self.assertEqual(observed["version_evidence"], "declared_image_binding_only")
        self.assertFalse(any(command[:2] == ["exec", entry["container_id"]] for command in self.fixture.commands))
        self.assertFalse(receipt["p018_single_cluster_observed"])

    def test_missing_duplicate_or_unknown_inventory_cannot_pass(self):
        original = copy.deepcopy(self.fixture.config["postgres_inventory"])
        for value, reason in ((None, "postgres_inventory_required"), ([], "postgres_inventory_required"), (original * 2, "postgres_inventory_duplicate")):
            self.fixture.config["postgres_inventory"] = value
            with self.subTest(reason=reason), self.assertRaisesRegex(preflight.Refused, reason):
                self.fixture.observe()
        self.fixture.config["postgres_inventory"] = original
        self.fixture.config["postgres_inventory"][0]["classification"] = "ignore"
        with self.assertRaisesRegex(preflight.Refused, "postgres_inventory_classification"):
            self.fixture.observe()

    def test_selected_pg15_and_concrete_control_plane_inventory_remain_explicit(self):
        self.fixture.config["postgres_major"] = 15
        selected = self.fixture.config["postgres_inventory"][0]
        selected.update(postgres_major=15, image="postgres:15-alpine")
        self.fixture.containers[0]["image"] = selected["image"]
        self.fixture.grants["server_version_num"] = 150019
        for letter, project, classification, major in [("d", "airflow", "airflow_metadata", 16), ("e", "source", "coolify_control_plane", 15)]:
            entry = {
                "container_id": letter * 64,
                "image": f"postgres:{major}",
                "image_id": "sha256:" + letter * 64,
                "compose_project": project,
                "compose_service": "postgres",
                "postgres_major": major,
                "classification": classification,
                "purpose": "Synthetic existing control-plane metadata",
            }
            self.fixture.config["postgres_inventory"].append(entry)
            self.fixture.containers.append(
                {
                    "id": entry["container_id"],
                    "image": entry["image"],
                    "image_id": entry["image_id"],
                    "running": True,
                    "labels": {"com.docker.compose.project": project, "com.docker.compose.service": "postgres"},
                }
            )
        receipt = self.fixture.observe()
        self.assertEqual(receipt["postgres_major"], 15)
        self.assertEqual(receipt["postgres_server_version_num"], 150019)
        self.assertEqual(len(receipt["postgres_inventory"]), 3)
        self.assertFalse(receipt["p018_single_cluster_observed"])
        self.assertFalse(receipt["p018_host_wide_compliance_verified"])
        self.fixture.config["postgres_inventory"][1]["classification"] = "application_data"
        with self.assertRaisesRegex(preflight.Refused, "postgres_single_managed_cluster"):
            self.fixture.observe()

    def test_inventory_and_server_major_mismatches_are_not_ignored(self):
        for key, value in [
            ("image_id", "sha256:" + "f" * 64),
            ("image", "postgres:15"),
            ("compose_project", "other-project"),
            ("compose_service", "other-service"),
            ("postgres_major", 15),
        ]:
            original = self.fixture.config["postgres_inventory"][0][key]
            self.fixture.config["postgres_inventory"][0][key] = value
            with self.subTest(key=key), self.assertRaises(preflight.Refused):
                self.fixture.observe()
            self.fixture.config["postgres_inventory"][0][key] = original
        self.fixture.grants["server_version_num"] = 150019
        with self.assertRaisesRegex(preflight.Refused, "database_grants"):
            self.fixture.observe()

    def test_admin_role_is_explicit_and_cannot_inject_options_or_sql(self):
        for role in (None, "", "-postgres", "postgres;DROP DATABASE buycycle", "postgres\nother", "a" * 64):
            self.fixture.config["postgres_admin_role"] = role
            with self.subTest(role=role), self.assertRaisesRegex(preflight.Refused, "postgres_admin_role"):
                self.fixture.observe()
        self.fixture.config["postgres_admin_role"] = "nextcloud"
        self.fixture.grants["current_user"] = "nextcloud"
        self.fixture.observe()
        self.assertIn("nextcloud", self.fixture.commands[-1])
        self.fixture.grants["current_user"] = "another_role"
        with self.assertRaisesRegex(preflight.Refused, "database_grants"):
            self.fixture.observe()

    def test_active_legacy_collector_schedule_or_webhook_is_denied(self):
        for mutate, reason in [
            (lambda: self.fixture.legacy.update(auto_deploy=True), "legacy_auto_deploy"),
            (lambda: self.fixture.tasks.append({"id": 1, "enabled": True}), "legacy_schedules"),
            (lambda: self.fixture.legacy["webhooks_present"].update(github=True), "legacy_webhook"),
            (lambda: self.fixture.legacy.update(status="running:healthy"), "legacy_provider_running"),
        ]:
            with self.subTest(reason=reason):
                self.fixture = ProviderFixture(Path(self.directory.name))
                mutate()
                with self.assertRaisesRegex(preflight.Refused, reason):
                    self.fixture.observe()

    def test_fixed_local_coolify_projection_is_bound_without_api_credentials(self):
        receipt = self.fixture.observe()
        binding = receipt["coolify_control_plane"]
        self.assertEqual(binding["container_id"], self.fixture.config["coolify_control_plane"]["container_id"])
        self.assertTrue(binding["running"])
        self.assertEqual(binding["observation"], "fixed_selected_app_metadata")
        self.assertTrue(all(url.startswith("https://api.cloudflare.com/client/v4/") for url, _ in self.fixture.urls))
        self.assertFalse(any("coolify-token" in path for path, _ in self.fixture.files_seen))
        projection = next(command for command in self.fixture.commands if command[:3] == ["exec", "--workdir", "/var/www/html"])
        self.assertEqual(projection[-1], "--execute=" + preflight.COOLIFY_PROJECTION)
        self.assertIn("->where('uuid','" + preflight.APP + "')->select(['id','uuid','status'])", projection[-1])
        self.assertNotIn("->save(", projection[-1])
        self.assertNotIn("->update(", projection[-1])
        self.assertNotIn("->delete(", projection[-1])

    def test_changed_or_missing_control_plane_is_rejected_before_php_exec(self):
        original = copy.deepcopy(self.fixture.containers[-1])
        for name, value, reason in (
            ("id", "e" * 64, "coolify_container_running"),
            ("running", False, "coolify_container_running"),
            ("image_id", "sha256:" + "9" * 64, "coolify_container_binding"),
            ("image", "ghcr.io/coollabsio/coolify:changed", "coolify_container_binding"),
            ("labels", {"com.docker.compose.project": "other", "com.docker.compose.service": "coolify"}, "coolify_container_binding"),
        ):
            self.fixture.containers[-1] = {**copy.deepcopy(original), name: value}
            self.fixture.commands = []
            with self.subTest(name=name), self.assertRaisesRegex(preflight.Refused, reason):
                self.fixture.observe()
            self.assertFalse(any(command[:3] == ["exec", "--workdir", "/var/www/html"] for command in self.fixture.commands))
        self.fixture.containers[-1] = original
        self.fixture.config.pop("coolify_control_plane")
        with self.assertRaisesRegex(preflight.Refused, "coolify_inventory_required"):
            self.fixture.observe()

    def test_metadata_projection_requires_exact_version_and_typed_booleans(self):
        baseline = copy.deepcopy(self.fixture.legacy)
        for name, value, reason in (
            ("version", True, "legacy_projection_shape"),
            ("version", 2, "legacy_projection_shape"),
            ("uuid", "another-app", "legacy_app_identity"),
            ("auto_deploy", None, "legacy_auto_deploy"),
            ("auto_deploy", 0, "legacy_auto_deploy"),
            ("preview_deploy", "false", "legacy_preview_deploy"),
            ("status", None, "legacy_provider_running"),
        ):
            self.fixture.legacy = {**copy.deepcopy(baseline), name: value}
            with self.subTest(name=name, value=value), self.assertRaisesRegex(preflight.Refused, reason):
                self.fixture.observe()
        for webhook in ("github", "gitlab", "bitbucket", "gitea"):
            for value in (True, None, 0, "false"):
                self.fixture.legacy = copy.deepcopy(baseline)
                self.fixture.legacy["webhooks_present"][webhook] = value
                with self.subTest(webhook=webhook, value=value), self.assertRaisesRegex(preflight.Refused, "legacy_webhook"):
                    self.fixture.observe()
        self.fixture.legacy = copy.deepcopy(baseline)
        self.fixture.legacy["webhooks_present"].pop("github")
        with self.assertRaisesRegex(preflight.Refused, "legacy_webhook"):
            self.fixture.observe()
        self.fixture.legacy = copy.deepcopy(baseline)
        self.fixture.legacy.pop("auto_deploy")
        with self.assertRaisesRegex(preflight.Refused, "legacy_projection_shape"):
            self.fixture.observe()

    def test_unknown_or_truncated_projection_and_schedules_fail_closed(self):
        for raw in ("", "{}", preflight.COOLIFY_PREFIX + "null", preflight.COOLIFY_PREFIX + "{}", preflight.COOLIFY_PREFIX + "{"):
            self.fixture.projection_raw = raw
            with self.subTest(raw=raw), self.assertRaises((preflight.Refused, ValueError)):
                self.fixture.observe()
        self.fixture.projection_raw = None
        for tasks in (
            None,
            [{"enabled": False}],
            [{"id": True, "enabled": False}],
            [{"id": 1, "enabled": 0}],
            [{"id": 1, "enabled": False}] * 2,
            [{"id": index + 1, "enabled": False} for index in range(101)],
        ):
            self.fixture.legacy["tasks"] = tasks
            with self.subTest(tasks=tasks), self.assertRaisesRegex(preflight.Refused, "legacy_schedules"):
                self.fixture.observe()
        self.fixture.legacy["tasks"] = [{"id": 1, "enabled": False}]
        self.fixture.observe()

    def test_stopped_projection_cannot_hide_running_or_restartable_legacy_container(self):
        legacy = {
            "id": "7" * 64,
            "name": "/" + preflight.APP + "-legacy",
            "labels": {},
            "image": "synthetic-legacy",
            "image_id": "sha256:" + "6" * 64,
            "running": True,
            "restart": "no",
            "ports": {},
        }
        self.fixture.containers.append(legacy)
        with self.assertRaisesRegex(preflight.Refused, "legacy_container_running"):
            self.fixture.observe()
        legacy.update(running=False, restart="unless-stopped")
        with self.assertRaisesRegex(preflight.Refused, "legacy_container_running"):
            self.fixture.observe()
        legacy["restart"] = "no"
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
