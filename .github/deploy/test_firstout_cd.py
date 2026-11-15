"""Exercise the controller; substitute only external GitHub/Railway/HTTP boundaries."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import firstout_cd as cd

SHA = "a" * 40
OLD_SHA = "b" * 40
OLD = {
    name: f"{repo}@sha256:{'1' if name == 'backend' else '2':0>64}"
    for name, repo in cd.IMAGES.items()
}
NEW = {
    name: f"{repo}@sha256:{'3' if name == 'backend' else '4':0>64}"
    for name, repo in cd.IMAGES.items()
}


def manifest():
    return {
        "schema_version": 2,
        "repository": cd.REPOSITORY,
        "source_commit": SHA,
        "release_tag": f"release/firstout/railway/{SHA}",
        "platform": "linux/amd64",
        "database": {"schema_revision": "086", "policy_sha256": "d" * 64},
        "workflow_commit": SHA,
        "workflow_run_id": 103,
        "workflow_run_attempt": 1,
        "frontend_assets": [
            {
                "path": "/_next/static/test.js",
                "sha256": hashlib.sha256(b"js").hexdigest(),
            },
            {
                "path": "/_next/static/test.css",
                "sha256": hashlib.sha256(b"css").hexdigest(),
            },
        ],
        "previous_backend_image": OLD["backend"],
        "images": {
            name: {"image": image, "digest": image.split("@")[1], "source_commit": SHA}
            for name, image in NEW.items()
        },
        "checks": dict.fromkeys(cd.CHECKS, True),
    }


class Response:
    status = 200

    def __init__(self, data):
        self.headers = {"Cache-Control": "no-store"}
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.data[:size]


class World:
    def __init__(self):
        self.images = copy.deepcopy(OLD)
        self.issues = []
        self.calls = []
        self.mode = "ok"
        self.backup_age = 1
        self.backup_expired = False
        self.approved = True
        self.reviewer_permission = "write"
        self.merged = True
        self.ready_receipt = True
        self.database_head = "085"
        self.database_down = False
        self.health_paths = {"backend": "/api/v1/ready", "frontend": "/healthz"}
        self.pending = False
        self.monitor_health_calls = 0
        self.main_reads = 0
        self.superseded = False

    def github(self, path, method="GET", body=None):
        self.calls.append(("github", path, method))
        if path.startswith("collaborators/"):
            return {"permission": self.reviewer_permission}
        if path.startswith("issues?"):
            return copy.deepcopy(self.issues)
        if path == "issues" and method == "POST":
            issue = {
                "number": len(self.issues) + 1,
                "state": "open",
                "user": {"login": "github-actions[bot]", "type": "Bot"},
                **body,
            }
            self.issues.insert(0, issue)
            return copy.deepcopy(issue)
        if path.startswith("issues/"):
            number = int(path.split("/")[1])
            issue = next(item for item in self.issues if item["number"] == number)
            if method == "PATCH":
                if self.mode == "initial_checkpoint_lost":
                    self.mode = "ok"
                    raise OSError("Initial checkpoint response lost before write")
                issue.update(body)
            return copy.deepcopy(issue)
        if path.startswith(f"commits/{SHA}/pulls"):
            return [
                {
                    "number": 9,
                    "merged_at": "date" if self.merged else None,
                    "merge_commit_sha": SHA,
                    "base": {"ref": "main", "repo": {"full_name": cd.REPOSITORY}},
                    "head": {"sha": OLD_SHA},
                    "user": {"login": "author"},
                }
            ]
        if path == "pulls/9/reviews?per_page=100":
            return [
                {
                    "id": 2,
                    "state": "APPROVED" if self.approved else "CHANGES_REQUESTED",
                    "commit_id": OLD_SHA,
                    "user": {"login": "reviewer"},
                }
            ]
        if path.startswith(f"commits/{SHA}/check-runs"):
            return {
                "total_count": 2,
                "check_runs": [
                    {
                        "id": number,
                        "name": name,
                        "app": {"slug": "github-actions"},
                        "head_sha": SHA,
                        "status": "completed",
                        "conclusion": "success",
                        "details_url": f"https://github.com/F0rge/f0rge/actions/runs/{number}/job/1",
                    }
                    for number, name in ((101, "ci"), (102, "playwright smoke"))
                ],
            }
        if path.startswith("actions/runs/"):
            number = int(path.split("/")[2])
            return {
                "id": number,
                "repository": {"full_name": cd.REPOSITORY},
                "head_branch": "main",
                "head_sha": SHA,
                "event": "workflow_run" if number == 103 else "push",
                "run_attempt": 1,
                "status": "in_progress" if number == 103 else "completed",
                "conclusion": "success",
                "path": {
                    101: ".github/workflows/ci.yml",
                    102: ".github/workflows/e2e-smoke.yml",
                    103: ".github/workflows/cd-firstout.yml",
                }[number],
            }
        if path.startswith("git/ref/"):
            if path == "git/ref/heads/main":
                self.main_reads += 1
                if self.superseded and self.main_reads > 1:
                    return {"object": {"type": "commit", "sha": OLD_SHA}}
            return {"object": {"type": "commit", "sha": SHA}}
        if path.startswith("compare/"):
            return {"status": "identical"}
        raise AssertionError(path)

    def railway(self, query, variables):
        if "volumeInstances" in query:
            return {
                "environment": {
                    "id": cd.ENVIRONMENT,
                    "projectId": cd.PROJECT,
                    "volumeInstances": {
                        "pageInfo": {"hasNextPage": False},
                        "edges": [
                            {
                                "node": {
                                    "id": "volume",
                                    "serviceId": cd.DATABASE,
                                    "environmentId": cd.ENVIRONMENT,
                                    "deletedAt": None,
                                    "isPendingDeletion": False,
                                }
                            }
                        ],
                    },
                }
            }
        if "volumeInstanceBackupList" in query:
            current = dt.datetime.now(dt.UTC)
            return {
                "volumeInstanceBackupList": [
                    {
                        "id": "backup",
                        "createdAt": (
                            current - dt.timedelta(hours=self.backup_age)
                        ).isoformat(),
                        "expiresAt": (
                            current
                            + dt.timedelta(hours=-1 if self.backup_expired else 5)
                        ).isoformat(),
                        "externalId": "provider-id",
                        "usedMB": 123,
                    }
                ]
            }
        if "mutation" in query:
            service, value = next(iter(variables["patch"]["services"].items()))
            name = next(
                name
                for name, identifier in cd.SERVICES.items()
                if identifier == service
            )
            self.calls.append(("submit", name, value))
            if self.mode == "ambiguous" and name == "backend":
                raise OSError("Response lost")
            self.images[name] = value["source"]["image"]
            self.health_paths[name] = value["deploy"]["healthcheckPath"]
            if name == "backend" and self.images[name] == NEW["backend"]:
                self.database_head = "086"
            if (
                name == "backend"
                and self.images[name] == OLD["backend"]
                and self.mode == "database_down_on_recovery"
            ):
                self.database_down = True
            return {"environmentPatchCommit": "workflow"}
        service = variables["service"]
        name = next(
            name for name, identifier in cd.SERVICES.items() if identifier == service
        )
        image = self.images[name]
        deployment = {
            "id": f"00000000-0000-4000-8000-{int(image[-1]) + (10 if name == 'backend' else 20):012d}",
            "status": "SUCCESS",
            "projectId": cd.PROJECT,
            "environmentId": cd.ENVIRONMENT,
            "serviceId": service,
            "canRollback": True,
            "meta": {"image": image, "imageDigest": image.split("@")[1]},
            "instances": [
                {
                    "id": f"00000000-0000-4000-8000-{int(image[-1]) + (30 if name == 'backend' else 40):012d}",
                    "status": "RUNNING",
                }
            ],
        }
        config = {
            "source": {"image": image, "autoUpdates": {"type": "disabled"}},
            "deploy": {"healthcheckPath": self.health_paths[name]},
        }
        return {
            "project": {
                "id": cd.PROJECT,
                "deploymentTriggers": {"pageInfo": {"hasNextPage": False}, "edges": []},
            },
            "environment": {
                "id": cd.ENVIRONMENT,
                "projectId": cd.PROJECT,
                "config": {"services": {service: config}},
            },
            "serviceInstance": {
                "serviceId": service,
                "environmentId": cd.ENVIRONMENT,
                "serviceName": "firstout-api"
                if name == "backend"
                else "firstout-frontend",
                "source": {"image": image, "repo": None},
                "activeDeployments": [copy.deepcopy(deployment)],
                "latestDeployment": copy.deepcopy(deployment),
            },
            "environmentStagedChanges": {
                "patch": {"pending": True} if self.pending else {}
            },
        }

    def open(self, request, timeout):
        url = request.full_url
        if "/_next/static/" in url:
            content = b"js" if url.endswith(".js") else b"css"
            return Response(b"corrupt" if self.mode == "asset_bad" else content)
        return Response(json.dumps(self.http(url)).encode())

    def http(self, url):
        if url == cd.READY:
            candidate = self.images["backend"] == NEW["backend"]
            return {
                "status": "failed" if self.database_down else "ok",
                "source_commit": SHA if candidate else OLD_SHA,
                "migration_receipt": self.ready_receipt if candidate else True,
                "schema_revision": self.database_head,
                "image_schema_revision": "086" if candidate else "085",
                "receipt_schema_revision": "086" if candidate else "085",
                "policy_sha256": ("d" if candidate else "c") * 64,
            }
        if (
            url == cd.HEALTH["frontend"]
            and self.images["frontend"] == NEW["frontend"]
            and self.mode
            in ("frontend_bad", "rollback_bad", "database_down_on_recovery")
        ):
            return {"status": "failed"}
        if (
            url == cd.HEALTH["frontend"]
            and self.images["backend"] != OLD["backend"]
            and self.mode == "rollback_bad"
        ):
            return {"status": "failed"}
        return {"status": "ok"}


class CDTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "receipt.json"
        self.patches = [
            patch.object(cd, "github", self.world.github),
            patch.object(cd.legacy, "github", self.world.github),
            patch.object(cd.legacy, "railway", self.world.railway),
            patch.object(cd.urllib.request, "build_opener", lambda *args: self.world),
            patch.object(cd, "MAX_WAIT_SECONDS", 0),
            patch.object(cd.time, "sleep", lambda _: None),
        ]
        for replacement in self.patches:
            replacement.start()

    def tearDown(self):
        for replacement in reversed(self.patches):
            replacement.stop()
        self.temp.cleanup()

    def test_success_coordinates_images_and_durable_journal(self):
        result = cd.deploy(manifest(), self.path)
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(self.world.issues[0]["state"], "closed")
        self.assertEqual(self.world.images, NEW)
        submissions = [call for call in self.world.calls if call[0] == "submit"]
        self.assertEqual([call[1] for call in submissions], ["backend", "frontend"])
        self.assertEqual(submissions[0][2]["deploy"]["preDeployCommand"], [cd.MIGRATE])
        self.assertEqual(json.loads(self.path.read_text())["state"], "succeeded")

    def test_initial_issue_patch_failure_is_recoverable_without_provider_writes(self):
        self.world.mode = "initial_checkpoint_lost"
        with self.assertRaises(OSError):
            cd.deploy(manifest(), self.path)
        issue = self.world.github("issues/1")
        raw = json.loads(issue["body"].removeprefix("```json\n").removesuffix("\n```"))
        self.assertNotIn("issue_number", raw)
        self.assertEqual(raw["attempted"], [])
        restarted = cd.read_journal(issue)
        self.assertEqual(restarted["issue_number"], issue["number"])
        cd.recover(restarted, self.path)
        self.assertEqual(self.world.images, OLD)
        self.assertFalse(any(call[0] == "submit" for call in self.world.calls))
        self.assertEqual(cd.read_journal(self.world.issues[0])["state"], "rolled_back")
        self.assertEqual(self.world.issues[0]["state"], "open")

    def test_stored_journal_issue_number_must_match_github(self):
        cd.deploy(manifest(), self.path)
        issue = copy.deepcopy(self.world.issues[0])
        journal = cd.read_journal(issue)
        journal["issue_number"] += 1
        issue["body"] = "```json\n" + json.dumps(journal) + "\n```"
        with self.assertRaisesRegex(cd.ReleaseError, "issue number differs"):
            cd.read_journal(issue)

    def test_frontend_failure_restores_pair_in_reverse_order_and_pauses(self):
        self.world.mode = "frontend_bad"
        with self.assertRaises(cd.ReleaseError):
            cd.deploy(manifest(), self.path)
        self.assertEqual(self.world.images, OLD)
        self.assertEqual(cd.read_journal(self.world.issues[0])["state"], "rolled_back")
        self.assertEqual(self.world.issues[0]["state"], "open")
        submissions = [call for call in self.world.calls if call[0] == "submit"]
        self.assertEqual(
            [call[1] for call in submissions],
            ["backend", "frontend", "frontend", "backend"],
        )
        self.assertTrue(
            all(
                call[2]["deploy"]["preDeployCommand"] == [] for call in submissions[-2:]
            )
        )
        self.assertFalse(
            any(
                "downgrade" in json.dumps(call) or "Restore" in json.dumps(call)
                for call in submissions
            )
        )

    def test_missing_migration_receipt_never_deploys_frontend(self):
        self.world.ready_receipt = False
        with self.assertRaises(cd.ReleaseError):
            cd.deploy(manifest(), self.path)
        self.assertEqual(self.world.images, OLD)
        self.assertEqual(
            [call[1] for call in self.world.calls if call[0] == "submit"],
            ["backend", "backend"],
        )

    def test_lost_submission_response_does_not_compete_with_unknown_mutation(self):
        self.world.mode = "ambiguous"
        with self.assertRaises(cd.AmbiguousRelease):
            cd.deploy(manifest(), self.path)
        self.assertEqual(cd.read_journal(self.world.issues[0])["state"], "ambiguous")
        self.assertEqual(
            len([call for call in self.world.calls if call[0] == "submit"]), 1
        )
        with self.assertRaises(cd.ReleaseError):
            cd.recover(cd.read_journal(self.world.issues[0]), self.path)

    def test_open_incident_prevents_any_provider_mutation(self):
        self.world.issues.append(
            {"title": cd.PAUSE, "state": "open", "user": {"login": "owner"}}
        )
        with self.assertRaisesRegex(cd.ReleaseError, "paused"):
            cd.deploy(manifest(), self.path)
        self.assertFalse(any(call[0] == "submit" for call in self.world.calls))

    def test_same_successful_manifest_replays_without_deployment(self):
        first = cd.deploy(manifest(), self.path)
        calls = len(self.world.calls)
        second = cd.deploy(manifest(), self.path)
        self.assertEqual(first, second)
        self.assertFalse(any(call[0] == "submit" for call in self.world.calls[calls:]))

    def test_restart_after_lost_frontend_recovery_response_continues_backend(self):
        cd.deploy(manifest(), self.path)
        journal = cd.read_journal(self.world.issues[0])
        self.world.issues[0]["state"] = "open"
        journal["state"] = "ambiguous"
        journal["intent"] = {
            "phase": "recovery",
            "service": "frontend",
            "image": OLD["frontend"],
        }
        self.world.images = {"backend": NEW["backend"], "frontend": OLD["frontend"]}
        cd.checkpoint(journal, self.path, "ambiguous")
        # A fresh invocation reads the durable journal after the old frontend settled.
        restarted = cd.read_journal(self.world.github("issues/1"))
        calls = len(self.world.calls)
        cd.recover(restarted, self.path)
        submissions = [call for call in self.world.calls[calls:] if call[0] == "submit"]
        self.assertEqual([call[1] for call in submissions], ["backend"])
        self.assertEqual(self.world.images, OLD)
        self.assertEqual(cd.read_journal(self.world.issues[0])["state"], "rolled_back")
        self.assertNotIn("intent", cd.read_journal(self.world.issues[0]))

    def test_uncertain_release_intent_does_not_accept_previous_frontend_as_proof(self):
        cd.deploy(manifest(), self.path)
        journal = cd.read_journal(self.world.issues[0])
        journal.update(
            state="ambiguous",
            intent={
                "phase": "release",
                "service": "frontend",
                "image": NEW["frontend"],
            },
        )
        self.world.images = {"backend": NEW["backend"], "frontend": OLD["frontend"]}
        calls = len(self.world.calls)
        with self.assertRaisesRegex(cd.ReleaseError, "ambiguous provider"):
            cd.recover(journal, self.path)
        self.assertFalse(any(call[0] == "submit" for call in self.world.calls[calls:]))

    def test_superseded_candidate_stops_before_production_journal(self):
        self.world.superseded = True
        with self.assertRaisesRegex(cd.ReleaseError, "superseded"):
            cd.deploy(manifest(), self.path)
        self.assertFalse(self.world.issues)
        self.assertFalse(any(call[0] == "submit" for call in self.world.calls))

    def test_recovery_does_not_overwrite_an_unrelated_provider_change(self):
        cd.deploy(manifest(), self.path)
        journal = cd.read_journal(self.world.issues[0])
        self.world.images["frontend"] = cd.IMAGES["frontend"] + "@sha256:" + "9" * 64
        calls = len(self.world.calls)
        with self.assertRaisesRegex(cd.ReleaseError, "outside this release"):
            cd.recover(journal, self.path)
        self.assertFalse(any(call[0] == "submit" for call in self.world.calls[calls:]))

    def test_current_provider_must_match_tested_previous_binary(self):
        value = manifest()
        value["previous_backend_image"] = NEW["backend"]
        with self.assertRaisesRegex(cd.ReleaseError, "rollback baseline"):
            cd.deploy(value, self.path)
        self.assertFalse(self.world.issues)

    def test_backup_stale_or_expired_blocks_release(self):
        for age, expired in ((25, False), (1, True), (-1, False)):
            self.world.backup_age, self.world.backup_expired = age, expired
            with self.assertRaisesRegex(cd.ReleaseError, "backup"):
                cd.deploy(manifest(), self.path)
        self.assertFalse(self.world.issues)

    def test_unreviewed_or_unmerged_commit_blocks(self):
        self.world.approved = False
        with self.assertRaisesRegex(cd.ReleaseError, "independent approval"):
            cd.deploy(manifest(), self.path)
        self.world.approved, self.world.merged = True, False
        with self.assertRaisesRegex(cd.ReleaseError, "merged main PR"):
            cd.deploy(manifest(), self.path)
        self.assertFalse(self.world.issues)

    def test_outsider_approval_has_no_release_authority(self):
        self.world.reviewer_permission = "read"
        with self.assertRaisesRegex(cd.ReleaseError, "authorized reviewer"):
            cd.deploy(manifest(), self.path)
        self.assertFalse(self.world.issues)

    def test_cross_app_manifest_and_missing_checks_fail_closed(self):
        for update in (
            {"repository": "Other/app"},
            {"platform": "linux/arm64"},
            {"checks": {}},
        ):
            value = manifest()
            value.update(update)
            with self.assertRaises(cd.ReleaseError):
                cd.deploy(value, self.path)
        value = manifest()
        value["images"]["backend"]["image"] = "ghcr.io/other/backend@sha256:" + "3" * 64
        with self.assertRaises(cd.ReleaseError):
            cd.deploy(value, self.path)

    def test_pending_provider_patch_blocks_before_journal(self):
        self.world.pending = True
        with self.assertRaisesRegex(cd.ReleaseError, "Uncontained"):
            cd.deploy(manifest(), self.path)
        self.assertFalse(self.world.issues)

    def test_recovery_after_process_restart_uses_durable_previous_images(self):
        self.world.mode = "frontend_bad"
        with self.assertRaises(cd.ReleaseError):
            cd.deploy(manifest(), self.path)
        journal = cd.read_journal(self.world.issues[0])
        calls = len(self.world.calls)
        cd.recover(journal, self.path)
        self.assertFalse(any(call[0] == "submit" for call in self.world.calls[calls:]))
        self.assertEqual(self.world.images, OLD)

    def test_served_asset_corruption_rolls_back(self):
        self.world.mode = "asset_bad"
        with self.assertRaises(cd.ReleaseError):
            cd.deploy(manifest(), self.path)
        self.assertEqual(self.world.images, OLD)
        self.assertEqual(cd.read_journal(self.world.issues[0])["state"], "rolled_back")

    def test_database_outage_during_rollback_cannot_report_success(self):
        self.world.mode = "database_down_on_recovery"
        with self.assertRaises(cd.ReleaseError):
            cd.deploy(manifest(), self.path)
        self.assertTrue(self.world.database_down)
        self.assertEqual(
            cd.read_journal(self.world.issues[0])["state"], "recovery_failed"
        )
        self.assertEqual(self.world.issues[0]["state"], "open")

    def test_deploy_and_rollback_both_configure_database_readiness(self):
        self.world.mode = "frontend_bad"
        with self.assertRaises(cd.ReleaseError):
            cd.deploy(manifest(), self.path)
        mutations = [call for call in self.world.calls if call[0] == "submit"]
        for _, name, config in mutations:
            self.assertEqual(
                config["deploy"]["healthcheckPath"],
                "/api/v1/ready" if name == "backend" else "/healthz",
            )
        self.assertEqual(self.world.database_head, "086")
        old_ready = self.world.http(cd.READY)
        self.assertEqual(old_ready["source_commit"], OLD_SHA)
        self.assertEqual(old_ready["image_schema_revision"], "085")

    def test_failed_recovery_stays_open_and_pauses(self):
        self.world.mode = "rollback_bad"
        with self.assertRaises(cd.ReleaseError):
            cd.deploy(manifest(), self.path)
        self.assertEqual(
            cd.read_journal(self.world.issues[0])["state"], "recovery_failed"
        )
        self.assertEqual(self.world.issues[0]["state"], "open")

    def test_untrusted_public_issue_cannot_inject_recovery(self):
        result = cd.deploy(manifest(), self.path)
        issue = copy.deepcopy(self.world.issues[0])
        issue["user"] = {"login": "outsider", "type": "User"}
        with self.assertRaisesRegex(cd.ReleaseError, "bot-owned"):
            cd.read_journal(issue)
        result["before"]["backend"]["image"] = "ghcr.io/other/image@sha256:" + "0" * 64
        issue["user"] = {"login": "github-actions[bot]", "type": "Bot"}
        issue["body"] = "```json\n" + json.dumps(result) + "\n```"
        with self.assertRaisesRegex(cd.ReleaseError, "rollback image"):
            cd.read_journal(issue)

    def test_arbitrary_asset_url_or_traversal_is_rejected(self):
        for path in ("https://evil.invalid/a.js", "/_next/static/../secret.js"):
            value = manifest()
            value["frontend_assets"][0]["path"] = path
            with self.assertRaisesRegex(cd.ReleaseError, "asset"):
                cd.deploy(value, self.path)

    def test_successful_release_checks_both_health_and_asset_http(self):
        cd.deploy(manifest(), self.path)
        self.assertEqual(self.world.images, NEW)
        self.assertEqual(self.world.issues[0]["state"], "closed")


if __name__ == "__main__":
    unittest.main()
