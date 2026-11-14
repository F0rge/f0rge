from __future__ import annotations

import copy
import importlib.util
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "firstout_release", Path(__file__).with_name("firstout_release.py")
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def evidence():
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
        "release_tag": "release/firstout-frontend/railway/20261114T180000Z",
        "platform": "linux/amd64",
        "digest": "sha256:" + "c" * 64,
        "target": {
            "project": release.PROJECT,
            "environment": release.ENVIRONMENT,
            "service": release.SERVICE,
        },
        "workflow_run_id": 12,
        "workflow_run_attempt": 2,
        "tested": True,
        "checks": dict.fromkeys(release.CHECKS, True),
    }
    manifest["image"] = release.IMAGE + "@" + manifest["digest"]
    return manifest, run


def state():
    digest = "sha256:" + "c" * 64
    image = release.IMAGE + "@" + digest
    return {
        "service": release.SERVICE,
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
                "serviceId": release.SERVICE,
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
            [{"id": "replica", "status": "STARTING"}],
            [
                {"id": "replica", "status": "RUNNING"},
                {"id": "other", "status": "RUNNING"},
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

    def __init__(self):
        self.manifest, self.run = evidence()
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("firstout-release.json", json.dumps(self.manifest))
        self.archive = archive.getvalue()
        self.archive_digest = "sha256:" + hashlib.sha256(self.archive).hexdigest()
        self.tag_commit = self.manifest["source_commit"]
        self.check_conclusion = "success"
        self.check_app = "github-actions"
        self.mutation_count = 0
        self.lose_submission_response = False
        self.active = state()
        self.active["active_deployments"][0]["canRollback"] = True
        self.promoted = False
        self.provider_reads = 0
        self.change_instance = False
        self.check_branch = "main"

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
                            "name": "firstout-release-evidence",
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
            self.assert_railway(args)
            if args[2].startswith("mutation"):
                self.mutation_count += 1
                if self.lose_submission_response:
                    raise subprocess.TimeoutExpired(args, 90)
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
                                "services": {release.SERVICE: current["config"]}
                            },
                        },
                        "serviceInstance": {
                            "serviceId": release.SERVICE,
                            "environmentId": release.ENVIRONMENT,
                            "serviceName": "firstout-frontend",
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
            headers = {"Cache-Control": "no-store"}
            body = b'{"status":"ok"}'

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


if __name__ == "__main__":
    unittest.main()
