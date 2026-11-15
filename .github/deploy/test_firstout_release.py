from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "firstout_release", Path(__file__).with_name("firstout_release.py")
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def evidence(profile=release.FRONTEND):
    run = {
        "id": 12,
        "run_attempt": 2,
        "head_sha": "a" * 40,
        "head_branch": "main",
        "event": "workflow_dispatch",
        "path": release.WORKFLOW,
        "status": "completed",
        "conclusion": "success",
        "repository": {"full_name": release.REPOSITORY},
    }
    manifest = {
        "schema_version": 1,
        "repository": release.REPOSITORY,
        "source_commit": "b" * 40,
        "workflow_commit": run["head_sha"],
        "release_tag": f"release/firstout-{profile.component}/railway/20261114T180000Z",
        "platform": "linux/amd64",
        "digest": "sha256:" + "c" * 64,
        "target": {
            "project": release.PROJECT,
            "environment": release.ENVIRONMENT,
            "service": profile.service,
        },
        "workflow_run_id": 12,
        "workflow_run_attempt": 2,
        "tested": True,
        "checks": dict.fromkeys(profile.checks, True),
    }
    if profile == release.API:
        manifest.update(component="api", schema_revision="087_cin7_archive_provenance")
    manifest["image"] = profile.image + "@" + manifest["digest"]
    return manifest, run


def state(profile=release.FRONTEND):
    digest = "sha256:" + "c" * 64
    image = profile.image + "@" + digest
    return {
        "service": profile.service,
        "source": {"image": image, "repo": None},
        "pending_patch": {},
        "config": {
            "source": {"image": image, "autoUpdates": {"type": "disabled"}},
            "deploy": {"numReplicas": 1},
        },
        "active_deployments": [
            {
                "id": "deployment",
                "status": "SUCCESS",
                "projectId": release.PROJECT,
                "environmentId": release.ENVIRONMENT,
                "serviceId": profile.service,
                "image_digest": digest,
                "instances": [{"id": "replica", "status": "RUNNING"}],
            }
        ],
    }


class ArtifactIdentityTests(unittest.TestCase):
    def test_matching_successful_run_and_manifest(self):
        manifest, run = evidence()
        release.validate_manifest(manifest, run)

    def test_rejects_wrong_artifact_identity_and_missing_checks(self):
        for key, value in [
            ("repository", "elsewhere/repo"),
            ("source_commit", "main"),
            ("workflow_commit", "d" * 40),
            ("platform", "linux/arm64"),
            ("image", release.IMAGE + ":latest"),
            ("digest", "bad"),
            ("release_tag", "release/firstout-api/railway/20261114T180000Z"),
            ("workflow_run_id", 13),
            ("workflow_run_attempt", 1),
            ("tested", False),
            ("checks", {"unit": True}),
            (
                "target",
                {
                    "project": release.PROJECT,
                    "environment": "wrong",
                    "service": release.SERVICE,
                },
            ),
        ]:
            with self.subTest(key=key):
                manifest, run = evidence()
                manifest[key] = value
                with self.assertRaises(release.ReleaseError):
                    release.validate_manifest(manifest, run)

    def test_rejects_untrusted_run_origin_or_failure(self):
        for key, value in [
            ("head_branch", "feature"),
            ("event", "pull_request"),
            ("path", ".github/workflows/other.yml"),
            ("status", "in_progress"),
            ("conclusion", "failure"),
            ("run_attempt", 3),
            ("repository", {"full_name": "fork/repo"}),
        ]:
            with self.subTest(key=key):
                manifest, run = evidence()
                run[key] = value
                with self.assertRaises(release.ReleaseError):
                    release.validate_manifest(manifest, run)


class ServingEvidenceTests(unittest.TestCase):
    def test_removed_instance_history_is_excluded_from_serving_evidence(self):
        for profile in (release.FRONTEND, release.API):
            with self.subTest(profile=profile.component):
                current = state(profile)
                current["active_deployments"][0]["instances"].insert(
                    0, {"id": "old-job", "status": "REMOVED"}
                )
                self.assertEqual(
                    release.stable_deployment(
                        current, "sha256:" + "c" * 64, "deployment", profile
                    ),
                    ["replica"],
                )

    def test_exact_provider_image_and_running_instance(self):
        current = state()
        self.assertEqual(
            release.stable_deployment(current, "sha256:" + "c" * 64, "deployment"),
            ["replica"],
        )

    def test_rejects_source_only_match_without_provider_digest(self):
        current = state()
        current["active_deployments"][0]["image_digest"] = "sha256:" + "d" * 64
        with self.assertRaises(release.ReleaseError):
            release.stable_deployment(current, "sha256:" + "c" * 64, "deployment")

    def test_rejects_overlap_missing_or_unhealthy_replica(self):
        for instances in [
            [],
            [{"id": "old-job", "status": "REMOVED"}],
            [{"id": "replica", "status": "STARTING"}],
            [
                {"id": "replica", "status": "RUNNING"},
                {"id": "other", "status": "RUNNING"},
            ],
            *[
                [
                    {"id": "replica", "status": "RUNNING"},
                    {"id": "other", "status": status},
                ]
                for status in ("CRASHED", "PENDING", "STARTING", "REMOVING", "UNKNOWN")
            ],
        ]:
            with self.subTest(instances=instances):
                current = state()
                current["active_deployments"][0]["instances"] = instances
                with self.assertRaises(release.ReleaseError):
                    release.stable_deployment(
                        current, "sha256:" + "c" * 64, "deployment"
                    )
        current = state()
        current["active_deployments"].append(
            copy.deepcopy(current["active_deployments"][0])
        )
        with self.assertRaises(release.ReleaseError):
            release.stable_deployment(current, "sha256:" + "c" * 64, "deployment")

    def test_rejects_pending_changes_and_mutable_source(self):
        for location, value in [
            ("pending", {"services": {"unrelated": {"source": {"repo": "x"}}}}),
            ("git", "F0rge/f0rge"),
            ("updates", "patch"),
        ]:
            with self.subTest(location=location):
                current = state()
                if location == "pending":
                    current["pending_patch"] = value
                elif location == "git":
                    current["source"]["repo"] = value
                else:
                    current["config"]["source"]["autoUpdates"]["type"] = value
                with self.assertRaises(release.ReleaseError):
                    release.stable_deployment(
                        current, "sha256:" + "c" * 64, "deployment"
                    )

    def test_rejects_wrong_serving_target(self):
        for field in ("projectId", "environmentId", "serviceId", "id", "status"):
            with self.subTest(field=field):
                current = state()
                current["active_deployments"][0][field] = "different"
                with self.assertRaises(release.ReleaseError):
                    release.stable_deployment(
                        current, "sha256:" + "c" * 64, "deployment"
                    )

    def test_runtime_changes_are_not_accepted_as_source_promotion(self):
        before = state()
        after = state()
        after["config"]["deploy"]["numReplicas"] = 2
        with self.assertRaises(release.ReleaseError):
            release.unchanged_runtime(before, after)


class ReceiptTests(unittest.TestCase):
    def test_exclusive_journal_prevents_replay_and_update_retains_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            release.write_receipt(path, {"state": "submission_started"}, exclusive=True)
            with self.assertRaises(FileExistsError):
                release.write_receipt(path, {}, exclusive=True)
            release.write_receipt(path, {"state": "submitted"})
            self.assertEqual(json.loads(path.read_text()), {"state": "submitted"})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class RemoteBoundary:
    """Fake only outbound CLI/API transport; exercise the full release code."""

    def __init__(self, profile=release.FRONTEND):
        self.profile = profile
        self.manifest, self.run = evidence(profile)
        self.rebuild_archive()
        self.tag_commit = self.manifest["source_commit"]
        self.check_conclusion = "success"
        self.check_app = "github-actions"
        self.mutation_count = 0
        self.lose_submission_response = False
        self.active = state(profile)
        self.active["active_deployments"][0]["canRollback"] = True
        if profile == release.API:
            self.active["config"]["deploy"].update(
                preDeployCommand=release.API_LEGACY_PREDEPLOY,
                startCommand=release.API_LEGACY_START,
            )
        self.promoted = False
        self.provider_reads = 0
        self.change_instance = False
        self.check_branch = "main"
        self.last_patch = None
        self.schema_reads = 0
        self.change_schema = False
        self.schema = {
            "schema_revision": "087_cin7_archive_provenance",
            "database_identity": {
                "database_name": "firstout_runtime",
                "server_address": "10.0.0.2",
                "server_port": 5432,
            },
            "runtime_role": {
                "role": "firstout_app",
                "rolsuper": False,
                "rolbypassrls": False,
                "owns_public_tables": False,
                "can_assume_bypass_role": False,
            },
        }

    def rebuild_archive(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr(self.profile.manifest_file, json.dumps(self.manifest))
        self.archive = archive.getvalue()
        self.archive_digest = "sha256:" + hashlib.sha256(self.archive).hexdigest()

    def __call__(self, args, **_kwargs):
        if args[0] == "gh":
            endpoint = args[2].removeprefix(f"repos/{release.REPOSITORY}/")
            if endpoint == "actions/runs/12":
                value = self.run
            elif endpoint == "actions/runs/12/artifacts?per_page=100":
                value = {
                    "total_count": 1,
                    "artifacts": [
                        {
                            "id": 22,
                            "name": self.profile.artifact,
                            "expired": False,
                            "size_in_bytes": len(self.archive),
                            "digest": self.archive_digest,
                        }
                    ],
                }
            elif endpoint == "actions/artifacts/22/zip":
                return subprocess.CompletedProcess(args, 0, self.archive, b"")
            elif endpoint.startswith("git/ref/tags/"):
                value = {"object": {"type": "commit", "sha": self.tag_commit}}
            elif endpoint.startswith("compare/"):
                value = {"status": "ahead"}
            elif endpoint.startswith("commits/"):
                value = {
                    "total_count": 2,
                    "check_runs": [
                        {
                            "id": i,
                            "name": name,
                            "app": {"slug": self.check_app},
                            "head_sha": self.manifest["source_commit"],
                            "status": "completed",
                            "conclusion": self.check_conclusion,
                            "details_url": f"https://github.com/F0rge/f0rge/actions/runs/{i}/job/1",
                        }
                        for i, name in [(101, "ci"), (102, "playwright smoke")]
                    ],
                }
            elif endpoint in ("actions/runs/101", "actions/runs/102"):
                number = int(endpoint.rsplit("/", 1)[1])
                value = {
                    **self.run,
                    "id": number,
                    "event": "push",
                    "head_sha": self.manifest["source_commit"],
                    "head_branch": self.check_branch,
                    "path": ".github/workflows/ci.yml"
                    if number == 101
                    else ".github/workflows/e2e-smoke.yml",
                }
            else:
                raise AssertionError(endpoint)
        else:
            if args[:2] == ["railway", "ssh"]:
                if args[args.index("--service") + 1] != release.API.service:
                    raise AssertionError("Wrong database-read service")
                self.schema_reads += 1
                if self.change_schema and self.schema_reads > 1:
                    self.schema["schema_revision"] = "086_cin7_sellability"
                return subprocess.CompletedProcess(
                    args, 0, json.dumps(self.schema).encode(), b""
                )
            self.assert_railway(args)
            if args[2].startswith("mutation"):
                self.mutation_count += 1
                if self.lose_submission_response:
                    raise subprocess.TimeoutExpired(args, 90)
                self.last_patch = json.loads(args[args.index("--variables") + 1])[
                    "patch"
                ]
                change = self.last_patch["services"][self.profile.service]
                self.active["config"]["source"] = copy.deepcopy(change["source"])
                self.active["config"]["deploy"].update(change.get("deploy", {}))
                self.active["source"] = {
                    "repo": None,
                    "image": change["source"]["image"],
                }
                self.promoted = True
                value = {"data": {"environmentPatchCommit": "workflow"}}
            else:
                self.provider_reads += 1
                current = copy.deepcopy(self.active)
                deployments = []
                for deployment in current["active_deployments"]:
                    if self.change_instance and self.provider_reads > 1:
                        deployment["instances"][0]["id"] = "replacement"
                    digest = deployment.pop("image_digest")
                    deployment["meta"] = {"imageDigest": digest}
                    deployments.append(deployment)
                value = {
                    "data": {
                        "project": {
                            "deploymentTriggers": {
                                "pageInfo": {"hasNextPage": False},
                                "edges": [],
                            }
                        },
                        "environment": {
                            "id": release.ENVIRONMENT,
                            "projectId": release.PROJECT,
                            "config": {
                                "services": {self.profile.service: current["config"]}
                            },
                        },
                        "serviceInstance": {
                            "serviceId": self.profile.service,
                            "environmentId": release.ENVIRONMENT,
                            "serviceName": self.profile.service_name,
                            "source": current["source"]
                            if self.promoted
                            else {"repo": "F0rge/f0rge", "image": None},
                            "activeDeployments": deployments,
                            "latestDeployment": None,
                        },
                        "environmentStagedChanges": {"patch": current["pending_patch"]},
                    }
                }
        return subprocess.CompletedProcess(args, 0, json.dumps(value).encode(), b"")

    @staticmethod
    def assert_railway(args):
        if args[:2] != ["railway", "api"]:
            raise AssertionError(args[:2])


class TransportTrustTests(unittest.TestCase):
    def test_archive_and_source_checks_are_verified_through_api(self):
        boundary = RemoteBoundary()
        with patch("subprocess.run", side_effect=boundary):
            result = release.verified_artifact(12)
        self.assertEqual(result["artifact_digest"], boundary.archive_digest)
        self.assertEqual(
            [item["name"] for item in result["source_checks"]],
            ["ci", "playwright smoke"],
        )

    def test_bad_archive_digest_moved_tag_and_untrusted_checks_block(self):
        for failure in ("archive", "tag", "failing_ci", "spoofed_ci", "wrong_branch"):
            with self.subTest(failure=failure):
                boundary = RemoteBoundary()
                if failure == "archive":
                    boundary.archive_digest = "sha256:" + "0" * 64
                elif failure == "tag":
                    boundary.tag_commit = "d" * 40
                elif failure == "failing_ci":
                    boundary.check_conclusion = "failure"
                elif failure == "spoofed_ci":
                    boundary.check_app = "some-other-app"
                else:
                    boundary.check_branch = "feature"
                with (
                    patch("subprocess.run", side_effect=boundary),
                    self.assertRaises(release.ReleaseError),
                ):
                    release.verified_artifact(12)

    def test_ambiguous_submission_is_recorded_and_not_retried(self):
        boundary = RemoteBoundary()
        boundary.lose_submission_response = True
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "receipt.json"
            with patch("subprocess.run", side_effect=boundary):
                with self.assertRaises(subprocess.TimeoutExpired):
                    release.promote(12, receipt, "explicit-user-chat-release-approval")
                self.assertEqual(boundary.mutation_count, 1)
                self.assertEqual(
                    json.loads(receipt.read_text())["state"],
                    "submission_outcome_unknown",
                )
                with self.assertRaises(FileExistsError):
                    release.promote(12, receipt, "explicit-user-chat-release-approval")
                self.assertEqual(boundary.mutation_count, 1)

    def test_credentials_are_redacted_at_any_config_depth(self):
        original = {
            "source": {
                "registryCredentials": {
                    "username": "private",
                    "password": "secret-value",
                }
            },
            "deploy": {"registryCredentials": None},
        }
        redacted = release.redact_configuration(original)
        self.assertNotIn("secret-value", json.dumps(redacted))
        self.assertEqual(
            redacted["source"]["registryCredentials"], {"configured": True}
        )

    def test_inspect_never_retains_unrelated_pending_patch_values(self):
        boundary = RemoteBoundary()
        boundary.active["pending_patch"] = {
            "services": {"unrelated": {"variables": {"PASSWORD": "private-value"}}}
        }
        with patch("subprocess.run", side_effect=boundary):
            current = release.provider_state()
        self.assertIs(current["pending_patch"], True)
        self.assertNotIn("private-value", json.dumps(current))

    def test_health_and_unchanged_serving_set_required_for_verified_receipt(self):
        class Response:
            status = 200
            body = b'{"status":"ok"}'

            def __init__(self):
                self.headers = {"Cache-Control": "no-store"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def geturl(self):
                return release.HEALTH

            def read(self, _limit):
                return self.body

        for failure in (None, "body", "replacement"):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory() as directory,
            ):
                boundary = RemoteBoundary()
                boundary.promoted = True
                boundary.change_instance = failure == "replacement"
                boundary.active["active_deployments"][0]["id"] = (
                    "11111111-1111-4111-8111-111111111111"
                )
                response = Response()
                if failure == "body":
                    response.body = b'{"status":"broken"}'
                receipt = Path(directory) / "receipt.json"
                with patch("subprocess.run", side_effect=boundary):
                    trusted = release.verified_artifact(12)
                    release.write_receipt(
                        receipt,
                        {"evidence": trusted, "before": boundary.active},
                        exclusive=True,
                    )
                    with patch("urllib.request.urlopen", return_value=response):
                        if failure:
                            with self.assertRaises(release.ReleaseError):
                                release.verify(
                                    receipt, "11111111-1111-4111-8111-111111111111"
                                )
                        else:
                            result = release.verify(
                                receipt, "11111111-1111-4111-8111-111111111111"
                            )
                            self.assertEqual(result["state"], "verified")


class ApiProfileTests(unittest.TestCase):
    def test_schema_probe_uses_effective_application_engine_and_readonly_transaction(
        self,
    ):
        resolver_spec = importlib.util.spec_from_file_location(
            "firstout_probe_db_url",
            Path(__file__).resolve().parents[2]
            / "libs/backend/db/src/f0rge_db/db_url.py",
        )
        resolver = importlib.util.module_from_spec(resolver_spec)
        resolver_spec.loader.exec_module(resolver)
        primary = "postgresql://runtime@pooler.example/wrong_database"
        direct = "postgresql://runtime@direct.example/serving_database"
        effective = resolver.resolve_database_url(primary, direct_url=direct)
        used = []
        options = []
        metadata = RemoteBoundary(release.API).schema
        role = metadata["runtime_role"]

        class Result:
            def __init__(self, value):
                self.value = value

            def scalars(self):
                return self

            def all(self):
                return self.value

            def mappings(self):
                return self

            def one(self):
                return self.value

        class Connection:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def execution_options(self, **values):
                options.append(values)
                return self

            def begin(self):
                return self

            async def execute(self, statement):
                if statement.startswith("SELECT version_num"):
                    return Result(["087_cin7_archive_provenance"])
                if statement.startswith("SELECT current_user"):
                    return Result(role)
                if statement.startswith("SELECT current_database()"):
                    # PostgreSQL inet::text contains /32 or /128. The probe
                    # must return a bare IP while strict identity checks stay.
                    assert "host(inet_server_addr()) AS server_address" in statement
                    assert "inet_server_addr()::text" not in statement
                    return Result(metadata["database_identity"])
                if not statement.startswith("SET LOCAL statement_timeout"):
                    raise AssertionError("Unexpected schema probe statement")
                return Result(None)

        class Engine:
            def connect(self):
                used.append(effective)
                return Connection()

            async def dispose(self):
                pass

        database = types.ModuleType("app.database")
        database.engine = Engine()
        sqlalchemy = types.ModuleType("sqlalchemy")
        sqlalchemy.text = lambda value: value
        modules = {
            "app": types.ModuleType("app"),
            "app.database": database,
            "sqlalchemy": sqlalchemy,
        }

        def transport(args, **_kwargs):
            self.assertEqual(args[:2], ["railway", "ssh"])
            interpreter, flag, script = shlex.split(args[-1])
            self.assertEqual(interpreter, "/app/apps/firstout/backend/.venv/bin/python")
            self.assertEqual(flag, "-c")
            self.assertIn("from app.database import engine", script)
            self.assertNotIn("os.environ", script)
            self.assertNotIn("asyncpg.connect", script)
            output = io.StringIO()
            with (
                patch.dict(sys.modules, modules),
                patch.object(sys, "path", list(sys.path)),
                redirect_stdout(output),
            ):
                # Exercise the fixed in-repository probe, never provider-supplied code.
                exec(compile(script, "<remote-api-schema-probe>", "exec"), {})  # noqa: S102
            return subprocess.CompletedProcess(args, 0, output.getvalue().encode(), b"")

        with (
            patch.dict(
                os.environ, {"DATABASE_URL": primary, "DIRECT_DATABASE_URL": direct}
            ),
            patch("subprocess.run", side_effect=transport),
        ):
            observed = release.api_schema()
        self.assertEqual(
            used, ["postgresql+asyncpg://runtime@direct.example/serving_database"]
        )
        self.assertEqual(
            options, [{"isolation_level": "SERIALIZABLE", "postgresql_readonly": True}]
        )
        self.assertEqual(observed["schema_revision"], "087_cin7_archive_provenance")
        self.assertNotIn(primary, json.dumps(observed))
        self.assertNotIn(direct, json.dumps(observed))

    def test_closed_profiles_and_legacy_frontend_compatibility(self):
        manifest, run = evidence()
        release.validate_manifest(manifest, run)
        manifest["component"] = "frontend"
        release.validate_manifest(manifest, run, release.FRONTEND)
        self.assertEqual(release.profile_for("api"), release.API)
        with self.assertRaises(release.ReleaseError):
            release.profile_for("marrow")
        with self.assertRaises(release.ReleaseError):
            release.provider_state(release.API._replace(service="arbitrary-target"))

    def test_api_manifest_and_cross_component_substitution(self):
        manifest, run = evidence(release.API)
        release.validate_manifest(manifest, run, release.API)
        for field, value in (
            ("component", None),
            ("component", "frontend"),
            ("image", release.FRONTEND.image + "@" + manifest["digest"]),
            ("release_tag", "release/firstout-frontend/railway/20261114T180000Z"),
            (
                "target",
                {
                    "project": release.PROJECT,
                    "environment": release.ENVIRONMENT,
                    "service": release.FRONTEND.service,
                },
            ),
            ("schema_revision", None),
            ("schema_revision", "unverified head"),
            ("checks", {"unit": True, "lint": True, "container_smoke": True}),
        ):
            with self.subTest(field=field, value=value):
                altered = {**manifest, field: value}
                with self.assertRaises(release.ReleaseError):
                    release.validate_manifest(altered, run, release.API)
        with self.assertRaises(release.ReleaseError):
            release.validate_manifest(manifest, run)

    def test_api_artifact_uses_distinct_archive_and_authenticated_source_checks(self):
        boundary = RemoteBoundary(release.API)
        with patch("subprocess.run", side_effect=boundary):
            trusted = release.verified_artifact(12, release.API)
        self.assertEqual(trusted["manifest"]["component"], "api")
        self.assertEqual(trusted["artifact_digest"], boundary.archive_digest)
        with (
            patch("subprocess.run", side_effect=boundary),
            self.assertRaises(release.ReleaseError),
        ):
            release.verified_artifact(12)

    def test_only_reviewed_api_hook_removals_are_promoted(self):
        boundary = RemoteBoundary(release.API)
        before = copy.deepcopy(boundary.active["config"])
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("subprocess.run", side_effect=boundary),
        ):
            path = Path(directory) / "api.json"
            receipt = release.promote(
                12, path, "explicit API release consent", release.API
            )
        self.assertEqual(boundary.mutation_count, 1)
        self.assertEqual(boundary.schema_reads, 1)
        self.assertEqual(receipt["component"], "api")
        self.assertEqual(receipt["schema_before"], boundary.schema)
        self.assertEqual(set(boundary.last_patch["services"]), {release.API.service})
        promoted = boundary.last_patch["services"][release.API.service]
        self.assertEqual(
            promoted["deploy"], {"preDeployCommand": None, "startCommand": None}
        )
        self.assertEqual(set(promoted), {"source", "deploy"})
        self.assertEqual(
            boundary.active["config"]["deploy"]["numReplicas"],
            before["deploy"]["numReplicas"],
        )

    def test_unknown_commands_missing_schema_or_bypass_role_block_before_mutation(self):
        for failure in (
            "migration_hook",
            "start_command",
            "schema",
            "superuser",
            "bypass",
            "owner",
            "inherited_bypass",
        ):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory() as directory,
            ):
                boundary = RemoteBoundary(release.API)
                if failure == "migration_hook":
                    boundary.active["config"]["deploy"]["preDeployCommand"] = [
                        "unreviewed mutation"
                    ]
                elif failure == "start_command":
                    boundary.active["config"]["deploy"]["startCommand"] = (
                        "unreviewed server"
                    )
                elif failure == "schema":
                    boundary.schema["schema_revision"] = "083_portal_clerk_identity"
                else:
                    boundary.schema["runtime_role"][
                        {
                            "superuser": "rolsuper",
                            "bypass": "rolbypassrls",
                            "owner": "owns_public_tables",
                            "inherited_bypass": "can_assume_bypass_role",
                        }[failure]
                    ] = True
                with (
                    patch("subprocess.run", side_effect=boundary),
                    self.assertRaises(release.ReleaseError),
                ):
                    release.promote(
                        12,
                        Path(directory) / "receipt.json",
                        "explicit API consent",
                        release.API,
                    )
                self.assertEqual(boundary.mutation_count, 0)

    def test_only_api_command_removals_are_allowed_during_readback(self):
        before = state(release.API)
        before["config"]["deploy"].update(
            preDeployCommand=release.API_LEGACY_PREDEPLOY,
            startCommand=release.API_LEGACY_START,
        )
        after = copy.deepcopy(before)
        after["config"]["deploy"].pop("preDeployCommand")
        after["config"]["deploy"].pop("startCommand")
        release.unchanged_runtime(before, after, release.API)
        for key, value in (
            ("numReplicas", 2),
            ("startCommand", "new command"),
            ("preDeployCommand", ["new command"]),
        ):
            changed = copy.deepcopy(after)
            changed["config"]["deploy"][key] = value
            with self.subTest(key=key), self.assertRaises(release.ReleaseError):
                release.unchanged_runtime(before, changed, release.API)
        with self.assertRaises(release.ReleaseError):
            release.unchanged_runtime(before, after)

    def test_api_database_metadata_shape_is_validated_before_promotion(self):
        for failure in (
            "missing_identity",
            "address",
            "port",
            "database_name",
            "role_name",
            "extra_field",
        ):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory() as directory,
            ):
                boundary = RemoteBoundary(release.API)
                if failure == "missing_identity":
                    boundary.schema.pop("database_identity")
                elif failure == "role_name":
                    boundary.schema["runtime_role"].pop("role")
                elif failure == "extra_field":
                    boundary.schema["unexpected"] = "not part of the metadata contract"
                else:
                    key, value = {
                        "address": ("server_address", "untrusted-hostname"),
                        "port": ("server_port", "5432"),
                        "database_name": ("database_name", ""),
                    }[failure]
                    boundary.schema["database_identity"][key] = value
                with (
                    patch("subprocess.run", side_effect=boundary),
                    self.assertRaises(release.ReleaseError),
                ):
                    release.promote(
                        12,
                        Path(directory) / "receipt.json",
                        "explicit API consent",
                        release.API,
                    )
                self.assertEqual(boundary.mutation_count, 0)

    def test_api_health_schema_and_running_instance_are_verified(self):
        class Response:
            status = 200

            def __init__(self):
                self.headers = {"Cache-Control": "no-store"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def geturl(self):
                return release.API.health

            def read(self, _limit):
                return b'{"status":"ok"}'

        for failure in (
            None,
            "health",
            "schema",
            "schema_drift",
            "replacement",
            "component",
            "database",
            "server_address",
            "server_port",
            "role",
            "missing_binding",
        ):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory() as directory,
            ):
                boundary = RemoteBoundary(release.API)
                path = Path(directory) / "api.json"
                with patch("subprocess.run", side_effect=boundary):
                    release.promote(12, path, "explicit API consent", release.API)
                    deployment = "11111111-1111-4111-8111-111111111111"
                    boundary.active["active_deployments"][0]["id"] = deployment
                    boundary.provider_reads = 0
                    boundary.change_instance = failure == "replacement"
                    boundary.schema_reads = 0
                    boundary.change_schema = failure == "schema_drift"
                    response = Response()
                    if failure == "health":
                        response.headers = {}
                    if failure == "schema":
                        boundary.schema["schema_revision"] = "086_cin7_sellability"
                    if failure in ("database", "server_address", "server_port"):
                        key, value = {
                            "database": ("database_name", "another_database"),
                            "server_address": ("server_address", "10.0.0.3"),
                            "server_port": ("server_port", 5433),
                        }[failure]
                        boundary.schema["database_identity"][key] = value
                    if failure == "role":
                        boundary.schema["runtime_role"]["role"] = "another_runtime_role"
                    if failure == "component":
                        receipt = json.loads(path.read_text())
                        receipt["component"] = "frontend"
                        path.write_text(json.dumps(receipt))
                    if failure == "missing_binding":
                        receipt = json.loads(path.read_text())
                        receipt.pop("schema_before")
                        path.write_text(json.dumps(receipt))
                    with patch(
                        "urllib.request.urlopen", return_value=response
                    ) as outbound:
                        if failure:
                            with self.assertRaises(release.ReleaseError):
                                release.verify(path, deployment, release.API)
                            saved = json.loads(path.read_text())
                            self.assertEqual(saved["state"], "submitted")
                            self.assertNotIn("schema_after", saved)
                            if failure in (
                                "database",
                                "server_address",
                                "server_port",
                                "role",
                                "missing_binding",
                            ):
                                outbound.assert_not_called()
                        else:
                            receipt = release.verify(path, deployment, release.API)
                            self.assertEqual(receipt["state"], "verified")
                            self.assertEqual(
                                receipt["health"]["url"], release.API.health
                            )
                            self.assertEqual(receipt["schema_after"], boundary.schema)
                            self.assertEqual(
                                outbound.call_args.args[0].full_url, release.API.health
                            )

    def test_lost_api_submission_is_journaled_and_cannot_replay(self):
        boundary = RemoteBoundary(release.API)
        boundary.lose_submission_response = True
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("subprocess.run", side_effect=boundary),
        ):
            path = Path(directory) / "api.json"
            with self.assertRaises(subprocess.TimeoutExpired):
                release.promote(12, path, "explicit API consent", release.API)
            self.assertEqual(
                json.loads(path.read_text())["state"], "submission_outcome_unknown"
            )
            with self.assertRaises(FileExistsError):
                release.promote(12, path, "explicit API consent", release.API)
            self.assertEqual(boundary.mutation_count, 1)


if __name__ == "__main__":
    unittest.main()
