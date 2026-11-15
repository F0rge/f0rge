"""Exercise release gates with a real loopback GitHub API and fake Docker boundary.

No production endpoints or credentials are used. Managed-root ownership is an
OS-metadata fixture; these tests do not certify installation of a real Pi agent.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import threading
import unittest
import urllib.request
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import buycycle_release as release
import firstout_release
import yaml


def archive(name: str, value: dict) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as zipped:
        zipped.writestr(name, json.dumps(value))
    return stream.getvalue()


def image_evidence() -> dict:
    return {
        "version": 1,
        "repository": release.REPOSITORY,
        "commit": "b" * 40,
        "platform": "linux/arm64",
        "image_id": "sha256:" + "c" * 64,
        "config_digest": "sha256:" + "9" * 64,
        "archive_sha256": "d" * 64,
        "tested": True,
        "dirty": False,
        "tests": dict.fromkeys(release.TESTS, True),
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "postgres_major": 15,
        "postgres_server_version_num": 150019,
        "harness_commit": "a" * 40,
    }


def publication() -> tuple[dict, dict]:
    run = {
        "id": 77,
        "run_attempt": 1,
        "head_sha": "a" * 40,
        "head_branch": "main",
        "event": "issue_comment",
        "path": release.WORKFLOW,
        "status": "completed",
        "conclusion": "success",
        "repository": {"full_name": release.REPOSITORY, "id": release.REPOSITORY_ID},
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "actor": {"id": 123, "login": "release-bot[bot]", "type": "Bot"},
        "triggering_actor": {"id": 123, "login": "release-bot[bot]", "type": "Bot"},
    }
    manifest = {
        "version": 1,
        "repository": release.REPOSITORY,
        "commit": "b" * 40,
        "release_tag": "release/buycycle/pi/20261115T090000Z",
        "digest": "sha256:" + "e" * 64,
        "image": release.IMAGE + "@sha256:" + "e" * 64,
        "target": {"host": "pi", "app": release.APP},
        "image_evidence": image_evidence(),
        "workflow_run_id": 77,
        "workflow_attempt": 1,
        "workflow_commit": "a" * 40,
        "postgres_major": 15,
        "release_request": {"comment_id": 31},
    }
    return manifest, run


class ContractTests(unittest.TestCase):
    def test_closed_request_json_rejects_extra_duplicate_ambiguous_and_malformed_values(
        self,
    ):
        request = {
            "version": 1,
            "source_commit": "b" * 40,
            "ci_run_id": 44,
            "release_tag": "release/buycycle/pi/20261115T090000Z",
            "receipt_hashes": dict.fromkeys(release.RECEIPTS, "c" * 64),
            "request_id": str(uuid.uuid4()),
            "postgres_major": 15,
        }
        release.validate_request_body(json.dumps(request))
        for changes in (
            {"extra": "command"},
            {"ci_run_id": True},
            {"postgres_major": True},
            {"postgres_major": 16},
            {"source_commit": "b" * 39},
            {"receipt_hashes": {"provider": "c" * 64}},
            {"request_id": "not-a-uuid"},
            {"release_tag": "release/other/pi/20261115T090000Z"},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises((release.ReleaseError, ValueError)),
            ):
                release.validate_request_body(json.dumps({**request, **changes}))
        for text in (
            json.dumps(request)[:-1] + ',"ci_run_id":44}',
            "[]",
            "{",
            " " * 4097,
        ):
            with (
                self.subTest(text=text[:20]),
                self.assertRaises((release.ReleaseError, ValueError)),
            ):
                release.validate_request_body(text)

    def test_archive_config_digest_hashes_bytes_not_docker_index_identity(self):
        content = json.dumps(
            {
                "architecture": "arm64",
                "os": "linux",
                "config": {"Labels": {"org.opencontainers.image.revision": "b" * 40}},
            }
        ).encode()
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "image.tar"
            with tarfile.open(saved, "w") as archive_file:
                for name, raw in {
                    "manifest.json": json.dumps(
                        [
                            {
                                "Config": "blobs/sha256/" + expected,
                                "RepoTags": ["f0rge-buycycle:tested-bbbbbbbbbbbb"],
                            }
                        ]
                    ).encode(),
                    "blobs/sha256/" + expected: content,
                    "index.json": b'{"manifests":[{"digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]}',
                }.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(raw)
                    archive_file.addfile(member, io.BytesIO(raw))
            self.assertEqual(
                release.archive_config(saved, "b" * 40),
                ("sha256:" + expected, "f0rge-buycycle:tested-bbbbbbbbbbbb"),
            )
            with self.assertRaises(release.ReleaseError):
                release.archive_config(saved, "a" * 40)

    def test_registry_platform_selection_ignores_attestations_and_rejects_ambiguity(
        self,
    ):
        image = release.IMAGE + "@sha256:" + "e" * 64
        child = "sha256:" + "f" * 64
        descriptor = {
            "digest": child,
            "platform": {"os": "linux", "architecture": "arm64", "variant": "v8"},
        }
        index = {
            "manifests": [
                descriptor,
                {
                    "digest": "sha256:" + "a" * 64,
                    "platform": {"os": "unknown", "architecture": "unknown"},
                },
            ]
        }
        calls = []

        def docker(args):
            calls.append(args)
            return json.dumps(
                index
                if args[-1] == image
                else {"config": {"digest": "sha256:" + "9" * 64}}
            )

        self.assertEqual(
            release.registry_config_digest(image, docker), "sha256:" + "9" * 64
        )
        self.assertEqual(
            calls,
            [
                ["manifest", "inspect", image],
                ["manifest", "inspect", release.IMAGE + "@" + child],
            ],
        )
        index["manifests"].append(descriptor)
        with self.assertRaises(release.ReleaseError):
            release.registry_config_digest(image, docker)

    def test_exact_immutable_publication_passes(self):
        release.validate_publication(*publication())

    def test_wrong_source_target_platform_checks_dirty_and_attempt_refused(self):
        mutations = [
            lambda m, r: m.update(repository="another/repo"),
            lambda m, r: m.update(image=release.IMAGE + ":latest"),
            lambda m, r: m.update(target={"host": "railway", "app": release.APP}),
            lambda m, r: m["image_evidence"].update(platform="linux/amd64"),
            lambda m, r: m["image_evidence"].update(dirty=True),
            lambda m, r: m["image_evidence"].pop("config_digest"),
            lambda m, r: m["image_evidence"]["tests"].update(
                origin_bypass_denied=False
            ),
            lambda m, r: m["image_evidence"].update(tests={}),
            lambda m, r: r.update(event="pull_request"),
            lambda m, r: r.update(head_branch="feature"),
            lambda m, r: r.update(conclusion="failure"),
            lambda m, r: r.update(run_attempt=2),
            lambda m, r: m.update(workflow_attempt=2),
            lambda m, r: m.update(workflow_commit="f" * 40),
            lambda m, r: m.pop("postgres_major"),
            lambda m, r: m.update(postgres_major=True),
            lambda m, r: m["image_evidence"].update(postgres_major=17),
            lambda m, r: m["image_evidence"].update(harness_commit="b" * 40),
            lambda m, r: m["image_evidence"].update(
                created_at=(dt.datetime.now(dt.UTC) - dt.timedelta(days=8)).isoformat()
            ),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                manifest, run = publication()
                mutate(manifest, run)
                with self.assertRaises(release.ReleaseError):
                    release.validate_publication(manifest, run)

    def test_ci_requires_successful_main_push(self):
        _, run = publication()
        run.update(path=".github/workflows/ci.yml", event="push", head_sha="b" * 40)
        release.validate_ci_run(run, "b" * 40)
        for field, value in [
            ("event", "workflow_dispatch"),
            ("event", "pull_request"),
            ("head_sha", "c" * 40),
            ("status", "in_progress"),
        ]:
            bad = dict(run, **{field: value})
            with self.assertRaises(release.ReleaseError):
                release.validate_ci_run(bad, "b" * 40)

    def test_durable_exclusive_journal_blocks_replay_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release.json"
            release.write_journal(path, {"state": "submission_started"}, exclusive=True)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                release.write_journal(path, {"state": "replayed"}, exclusive=True)
            self.assertEqual(
                json.loads(path.read_text()), {"state": "submission_started"}
            )

    def test_untrusted_managed_paths_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text("{}")
            with self.assertRaises(release.ReleaseError):
                release.trusted_file(str(path))
            linked = Path(directory) / "symlink"
            linked.symlink_to(path)
            with self.assertRaises(release.ReleaseError):
                release.trusted_file(str(linked))


class LoopbackReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.manifest, self.run = publication()
        self.policy = {
            "app": release.APP,
            "project_name": "buycycle",
            "requester_app_slug": "release-bot",
            "requester_app_id": 9,
            "requester_bot_id": 123,
            "request_pr_number": 900,
            "postgres_major": 15,
            "max_age_seconds": 3600,
            "compose_path": str(self.root / "compose.yml"),
            "managed_env_file": str(self.root / "managed.env"),
            "journal_dir": str(self.root),
            "active_release_receipt": str(self.root / "active.json"),
            "expected_docker_engine_id": "synthetic-pi-engine",
        }
        Path(self.policy["compose_path"]).write_text("services: {}\n")
        Path(self.policy["managed_env_file"]).write_text("# synthetic configuration\n")
        Path(self.policy["managed_env_file"]).chmod(0o600)
        self.policy["compose_sha256"] = hashlib.sha256(
            Path(self.policy["compose_path"]).read_bytes()
        ).hexdigest()
        self.policy["managed_env_sha256"] = hashlib.sha256(
            Path(self.policy["managed_env_file"]).read_bytes()
        ).hexdigest()
        self.manifest["receipt_hashes"] = {}
        for kind in release.RECEIPTS:
            path = self.root / (kind + ".json")
            data = {
                "passed": True,
                "commit": self.manifest["commit"],
                "target": self.manifest["target"],
                "created_at": dt.datetime.now(dt.UTC).isoformat(),
            }
            if kind == "provider":
                data.update(
                    docker_engine_id=self.policy["expected_docker_engine_id"],
                    compose_sha256=self.policy["compose_sha256"],
                    managed_env_sha256=self.policy["managed_env_sha256"],
                    postgres_major=15,
                    postgres_server_version_num=150019,
                )
                data.update(
                    dict.fromkeys(
                        [
                            "legacy_collector_fenced",
                            "source_builds_disabled",
                            "origin_unpublished",
                            "access_policy_verified",
                            "database_grants_verified",
                            "managed_secrets_verified",
                        ],
                        True,
                    )
                )
            path.write_text(json.dumps(data))
            self.policy[kind + "_receipt"] = str(path)
            self.manifest["receipt_hashes"][kind] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        self.environment = {
            "id": 15,
            "can_admins_bypass": False,
            "protection_rules": [
                {
                    "type": "required_reviewers",
                    "prevent_self_review": True,
                    "reviewers": [
                        {
                            "type": "User",
                            "reviewer": {
                                "login": release.OWNER,
                                "id": release.OWNER_ID,
                            },
                        }
                    ],
                }
            ],
        }
        self.approvals = [
            {
                "state": "approved",
                "user": {"login": release.OWNER, "id": release.OWNER_ID},
                "environments": [{"id": 15}],
            }
        ]
        self.api = {
            "": {"id": release.REPOSITORY_ID, "full_name": release.REPOSITORY},
            "public/apps/release-bot": {
                "id": 9,
                "slug": "release-bot",
                "permissions": dict(release.REQUEST_PERMISSIONS),
            },
            "public/users/release-bot%5Bbot%5D": {
                "id": 123,
                "type": "Bot",
                "login": "release-bot[bot]",
            },
            "pulls/900": {
                "number": 900,
                "merged": True,
                "base": {"ref": "main", "repo": {"id": release.REPOSITORY_ID}},
            },
            "rulesets?includes_parents=true&per_page=100": [
                {"id": 10, "target": "tag", "enforcement": "active"}
            ],
            "rulesets/10": {
                "conditions": {
                    "ref_name": {
                        "include": ["refs/tags/release/buycycle/pi/*"],
                        "exclude": [],
                    }
                },
                "bypass_actors": [],
                "rules": [{"type": "update"}, {"type": "deletion"}],
            },
            "actions/runs/77": self.run,
            "environments/production": self.environment,
            "environments/production/deployment-branch-policies": {
                "branch_policies": [{"name": "main", "type": "branch"}]
            },
            "actions/runs/77/approvals": self.approvals,
            "git/ref/tags/" + self.manifest["release_tag"]: {
                "object": {"type": "commit", "sha": "b" * 40}
            },
            "compare/" + "b" * 40 + "...main": {"status": "ahead"},
        }
        self.manifest.update(
            source_ci_run=44,
            source_ci_attempt=1,
            source_artifact={"id": 999, "digest": "sha256:" + "f" * 64},
        )
        self.request = {
            "version": 1,
            "source_commit": self.manifest["commit"],
            "ci_run_id": 44,
            "release_tag": self.manifest["release_tag"],
            "receipt_hashes": self.manifest["receipt_hashes"],
            "request_id": str(uuid.uuid4()),
            "postgres_major": 15,
        }
        timestamp = dt.datetime.now(dt.UTC).isoformat()
        self.comment = {
            "id": 31,
            "issue_url": "https://api.github.com/repos/F0rge/f0rge/issues/900",
            "user": dict(self.run["actor"]),
            "performed_via_github_app": {"id": 9, "slug": "release-bot"},
            "created_at": timestamp,
            "updated_at": timestamp,
            "body": json.dumps(self.request),
        }
        self.api["issues/comments/31"] = self.comment
        self.api["issues/900/comments?per_page=100&page=1"] = [self.comment]
        self.manifest["release_request"] = {
            "comment_id": 31,
            "body_sha256": hashlib.sha256(self.comment["body"].encode()).hexdigest(),
            "request_id": self.request["request_id"],
            "pull_request": 900,
            "repository_id": release.REPOSITORY_ID,
            "requester_app_id": 9,
            "requester_bot_id": 123,
            "created_at": timestamp,
        }
        self.api["actions/runs/44"] = {
            "id": 44,
            "run_attempt": 1,
            "head_sha": "b" * 40,
            "repository": {"full_name": release.REPOSITORY},
            "path": ".github/workflows/ci.yml",
            "head_branch": "main",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
        }
        self.api["actions/runs/44/artifacts?per_page=100"] = {
            "total_count": 1,
            "artifacts": [
                {
                    "id": 999,
                    "name": "ci-buycycle-push-44-1",
                    "digest": "sha256:" + "f" * 64,
                    "expired": False,
                }
            ],
        }
        checks = []
        for index, (name, workflow) in enumerate(
            [
                ("ci", ".github/workflows/ci.yml"),
                ("playwright smoke", ".github/workflows/e2e-smoke.yml"),
            ],
            1,
        ):
            checks.append(
                {
                    "id": index,
                    "name": name,
                    "app": {"slug": "github-actions"},
                    "head_sha": "b" * 40,
                    "status": "completed",
                    "conclusion": "success",
                    "details_url": f"https://github.com/F0rge/f0rge/actions/runs/{index}/job/{index}",
                }
            )
            self.api[f"actions/runs/{index}"] = {
                "repository": {"full_name": release.REPOSITORY},
                "id": index,
                "head_branch": "main",
                "event": "push",
                "head_sha": "b" * 40,
                "path": workflow,
                "status": "completed",
                "conclusion": "success",
                "run_attempt": 1,
            }
        self.api["commits/" + "b" * 40 + "/check-runs?per_page=100"] = {
            "total_count": 2,
            "check_runs": checks,
        }

        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler):
                data = self.api.get(handler.path[1:])
                handler.send_response(200 if data is not None else 404)
                handler.send_header("Content-Type", "application/json")
                handler.end_headers()
                handler.wfile.write(json.dumps(data).encode())

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        endpoint = f"http://127.0.0.1:{server.server_port}/"

        def api(path, **_kwargs):
            try:
                with urllib.request.urlopen(endpoint + path, timeout=2) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                raise release.ReleaseError("GitHub read rejected") from exc

        self.github_patch = patch.object(release, "github", api)
        self.addCleanup(self.github_patch.stop)
        self.github_patch.start()
        self.firstout_patch = patch.object(firstout_release, "github", api)
        self.addCleanup(self.firstout_patch.stop)
        self.firstout_patch.start()
        self.mutations = []
        self.engine_id = self.policy["expected_docker_engine_id"]
        self.docker_commands = []
        self.docker_environments = []
        self.docker_image = {
            "Id": self.manifest["image_evidence"]["image_id"],
            "Architecture": "arm64",
            "Os": "linux",
            "RepoDigests": [self.manifest["image"]],
            "Config": {"Labels": {"org.opencontainers.image.revision": "b" * 40}},
        }
        self.registry_config = self.manifest["image_evidence"]["config_digest"]
        self.running = {
            "Image": self.docker_image["Id"],
            "State": {"Running": True, "Health": {"Status": "healthy"}},
            "HostConfig": {"PortBindings": {}},
            "Config": {"Labels": {"org.opencontainers.image.revision": "b" * 40}},
        }
        original_run = subprocess.run

        def commands(args, **kwargs):
            if args[:3] == ["docker", "--host", "unix:///run/docker.sock"]:
                self.docker_commands.append(args)
                self.docker_environments.append(kwargs.get("env", {}))
                self.assertNotIn("DOCKER_CONTEXT", kwargs.get("env", {}))
                args = ["docker", *args[3:]]
            if args[:2] == ["docker", "info"]:
                return subprocess.CompletedProcess(
                    args, 0, self.engine_id.encode(), b""
                )
            if args[:2] == ["gh", "api"] and args[2] in {
                "apps/release-bot",
                "users/release-bot%5Bbot%5D",
            }:
                return subprocess.CompletedProcess(
                    args, 0, json.dumps(api("public/" + args[2])).encode(), b""
                )
            if args[:2] == ["gh", "api"] and args[2].endswith("/zip"):
                parts = args[2].split("/")
                archive_id = int(parts[-2])
                kwargs["stdout"].write(self.zips[archive_id])
                return subprocess.CompletedProcess(args, 0, None, b"")
            if args[:2] == ["docker", "compose"]:
                if "pull" in args or "up" in args:
                    self.mutations.append(args)
                    return subprocess.CompletedProcess(args, 0, b"", b"")
                return subprocess.CompletedProcess(
                    args, 0, ("f" * 64 + "\n").encode(), b""
                )
            if args[:3] == ["docker", "image", "inspect"]:
                return subprocess.CompletedProcess(
                    args, 0, json.dumps([self.docker_image]).encode(), b""
                )
            if args[:3] == ["docker", "manifest", "inspect"]:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    json.dumps({"config": {"digest": self.registry_config}}).encode(),
                    b"",
                )
            if args[:2] == ["docker", "inspect"]:
                return subprocess.CompletedProcess(
                    args, 0, json.dumps([self.running]).encode(), b""
                )
            return original_run(args, **kwargs)

        self.run_patch = patch.object(subprocess, "run", commands)
        self.addCleanup(self.run_patch.stop)
        self.run_patch.start()
        original_lstat = Path.lstat

        def managed_stat(path):
            values = list(original_lstat(path))
            values[0] &= ~0o022
            values[4] = 0
            return __import__("os").stat_result(values)

        self.stat_patch = patch.object(Path, "lstat", managed_stat)
        self.addCleanup(self.stat_patch.stop)
        self.stat_patch.start()
        self.refresh_archives()

    def refresh_archives(self):
        approval = {
            "version": 1,
            "run_id": 77,
            "run_attempt": 1,
            "release_request": self.manifest["release_request"],
            "postgres_major": self.manifest["postgres_major"],
            "publication_sha256": hashlib.sha256(
                json.dumps(
                    self.manifest, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
        }
        self.zips = {
            10: archive("buycycle-release.json", self.manifest),
            11: archive("approval.json", approval),
        }
        self.api["actions/runs/77/artifacts?per_page=100"] = {
            "total_count": 2,
            "artifacts": [
                {
                    "id": key,
                    "name": name,
                    "expired": False,
                    "size_in_bytes": len(self.zips[key]),
                    "digest": "sha256:" + hashlib.sha256(self.zips[key]).hexdigest(),
                }
                for key, name in [
                    (10, "buycycle-release-publication"),
                    (11, "buycycle-release-approval"),
                ]
            ],
        }

    def test_real_api_verification_applies_only_exact_image_and_journals(self):
        value = release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(value["state"], "verified")
        self.assertEqual(len(self.mutations), 2)
        active = json.loads((self.root / "active.json").read_text())
        self.assertEqual(active, value)
        self.assertEqual(active["receipt_hashes"], self.manifest["receipt_hashes"])
        self.assertEqual(active["compose_sha256"], self.policy["compose_sha256"])
        self.assertEqual(
            active["managed_env_sha256"], self.policy["managed_env_sha256"]
        )
        self.assertEqual((self.root / "active.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.root.glob(".active-*.tmp")), [])
        self.assertEqual(
            json.loads((self.root / "77-1.json").read_text())["image_id"],
            self.docker_image["Id"],
        )
        with self.assertRaises(FileExistsError):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(len(self.mutations), 2)

    def test_docker_engine_image_id_can_differ_from_ci_with_same_registry_config(self):
        self.docker_image["Id"] = "sha256:" + "1" * 64
        self.running["Image"] = self.docker_image["Id"]
        value = release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(value["image_id"], self.docker_image["Id"])
        self.assertEqual(
            value["config_digest"], self.manifest["image_evidence"]["config_digest"]
        )

    def test_wrong_registry_config_blocks_container_start(self):
        self.registry_config = "sha256:" + "2" * 64
        with self.assertRaises(release.ReleaseError):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(len(self.mutations), 1)
        self.assertIn("pull", self.mutations[0])
        self.assertNotIn("up", self.mutations[0])
        self.assertFalse((self.root / "active.json").exists())

    def test_active_receipt_cannot_escape_managed_journal_or_follow_symlinks(self):
        managed = self.root / "active.json"
        for invalid in [
            str(self.root.parent / "active.json"),
            str(self.root / "../active.json"),
            str(self.root / "migration.json"),
        ]:
            self.policy["active_release_receipt"] = invalid
            with self.assertRaises(release.ReleaseError):
                release.agent_apply(77, str(uuid.uuid4()), self.policy)
            self.assertEqual(self.mutations, [])
        self.policy["active_release_receipt"] = str(managed)
        managed.symlink_to(self.root / "migration.json")
        with self.assertRaises(release.ReleaseError):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(self.mutations, [])

    def test_active_publication_is_atomic_and_failure_retains_previous_receipt(self):
        active = self.root / "active.json"
        active.write_text('{"state":"previous"}')
        with (
            patch.object(
                release.os,
                "replace",
                side_effect=OSError("synthetic publication failure"),
            ),
            self.assertRaises(OSError),
        ):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(json.loads(active.read_text()), {"state": "previous"})
        self.assertEqual(list(self.root.glob(".active-*.tmp")), [])
        self.assertEqual(
            json.loads((self.root / "77-1.json").read_text())["state"],
            "submission_outcome_unknown",
        )

    def test_unapproved_identity_admin_bypass_expired_and_rerun_have_no_effect(self):
        changes = [
            lambda: self.approvals.clear(),
            lambda: self.approvals[0]["user"].update(login="someone-else"),
            lambda: self.approvals[0]["user"].update(id=12345),
            lambda: self.environment.update(can_admins_bypass=True),
            lambda: self.environment["protection_rules"][0].update(
                prevent_self_review=False
            ),
            lambda: self.run["actor"].update(type="User", login=release.OWNER),
            lambda: self.run["triggering_actor"].update(id=555),
            lambda: self.run.update(
                created_at=(dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)).isoformat()
            ),
            lambda: self.run.update(run_attempt=2),
            lambda: self.api["rulesets/10"].update(
                bypass_actors=[{"actor_type": "Integration", "actor_id": 123}]
            ),
            lambda: self.api["rulesets/10"]["rules"].clear(),
            lambda: self.api["git/ref/tags/" + self.manifest["release_tag"]][
                "object"
            ].update(sha="0" * 40),
        ]
        for change in changes:
            with self.subTest(change=change):
                baseline = copy.deepcopy(self.api)
                change()
                with self.assertRaises(release.ReleaseError):
                    release.agent_apply(77, str(uuid.uuid4()), self.policy)
                self.assertEqual(self.mutations, [])
                self.api.clear()
                self.api.update(baseline)
                self.run = self.api["actions/runs/77"]
                self.environment = self.api["environments/production"]
                self.approvals = self.api["actions/runs/77/approvals"]

    def test_changed_receipt_or_compose_refused_before_mutation(self):
        for name in [
            "migration_receipt",
            "restore_receipt",
            "provider_receipt",
            "compose_path",
            "managed_env_file",
        ]:
            path = Path(self.policy[name])
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.assertRaises(release.ReleaseError):
                release.agent_apply(77, str(uuid.uuid4()), self.policy)
            self.assertEqual(self.mutations, [])
            path.write_bytes(original)

    def test_wrong_engine_has_no_deployment_effect_and_inherited_context_is_ignored(
        self,
    ):
        self.engine_id = "wrong-host-engine"
        with (
            patch.dict(
                "os.environ",
                {"DOCKER_HOST": "ssh://wrong-host", "DOCKER_CONTEXT": "other-host"},
            ),
            self.assertRaises(release.ReleaseError),
        ):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(self.mutations, [])
        self.assertTrue(self.docker_commands)
        self.assertTrue(
            all(
                args[1:3] == ["--host", "unix:///run/docker.sock"]
                for args in self.docker_commands
            )
        )

    def test_ambient_compose_and_runtime_settings_cannot_override_approved_env_file(
        self,
    ):
        ambient = {
            "ACCESS_ISSUER": "https://malicious.example.test",
            "ACCESS_AUDIENCE": "wrong-audience",
            "ACCESS_ALLOWED_EMAILS": "intruder@example.test",
            "BUYCYCLE_SECRETS_DIR": "/tmp/hostile-secrets",
            "BUYCYCLE_DATABASE_NETWORK": "hostile-network",
            "BUYCYCLE_IMAGE": "unapproved:latest",
            "COMPOSE_PROFILES": "bootstrap-cluster,maintenance",
            "COMPOSE_FILE": "/tmp/hostile-compose.yml",
            "COMPOSE_PROJECT_NAME": "another-app",
            "DOCKER_CONTEXT": "another-host",
            "GH_TOKEN": "synthetic-private-token",
        }
        with patch.dict("os.environ", ambient):
            receipt = release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(receipt["state"], "verified")
        self.assertTrue(self.docker_environments)
        allowed = {"PATH", "DOCKER_CONFIG", "LANG", "DOCKER_HOST", "BUYCYCLE_IMAGE"}
        for selected in self.docker_environments:
            self.assertLessEqual(selected.keys(), allowed)
            self.assertEqual(selected["DOCKER_HOST"], "unix:///run/docker.sock")
            if "BUYCYCLE_IMAGE" in selected:
                self.assertEqual(selected["BUYCYCLE_IMAGE"], self.manifest["image"])
        for command in self.mutations:
            self.assertIn(self.policy["managed_env_file"], command)

    def test_runtime_credentials_readable_by_other_users_refuse_deployment(self):
        Path(self.policy["managed_env_file"]).chmod(0o644)
        with self.assertRaises(release.ReleaseError):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(self.mutations, [])

    def test_artifact_tampering_or_traversal_cannot_reach_deployment(self):
        listing = self.api["actions/runs/77/artifacts?per_page=100"]
        listing["artifacts"][0]["digest"] = "sha256:" + "0" * 64
        with self.assertRaises(release.ReleaseError):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(self.mutations, [])
        self.refresh_archives()
        self.zips[10] = archive("../buycycle-release.json", self.manifest)
        listing = self.api["actions/runs/77/artifacts?per_page=100"]
        listing["artifacts"][0]["digest"] = (
            "sha256:" + hashlib.sha256(self.zips[10]).hexdigest()
        )
        with self.assertRaises(release.ReleaseError):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(self.mutations, [])

    def test_fixed_mutual_tls_agent_url_is_required_before_any_network_effect(self):
        for url in [
            "http://127.0.0.1/v1/releases",
            "https://user:password@host/v1/releases",
            "https://host/commands",
            "https://host/v1/releases?command=shell",
        ]:
            with self.subTest(url=url):
                self.policy["agent_url"] = url
                with self.assertRaises(release.ReleaseError):
                    release.promote(77, self.policy)
                self.assertEqual(self.mutations, [])

    def test_global_lock_rejects_overlapping_different_release_ids(self):
        import fcntl
        import os

        fd = os.open(self.root / "deployment.lock", os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(release.ReleaseError):
                release.agent_apply(78, str(uuid.uuid4()), self.policy)
            self.assertEqual(self.mutations, [])
        finally:
            os.close(fd)

    def assert_failed_running_verification(self):
        with self.assertRaises(release.ReleaseError):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(
            json.loads((self.root / "77-1.json").read_text())["state"],
            "submission_outcome_unknown",
        )
        self.assertFalse((self.root / "active.json").exists())

    def test_wrong_running_digest_never_claims_success(self):
        self.running["Image"] = "sha256:" + "0" * 64
        self.assert_failed_running_verification()

    def test_public_origin_never_claims_success(self):
        self.running["HostConfig"] = {
            "PortBindings": {"8080/tcp": [{"HostPort": "8095"}]}
        }
        self.assert_failed_running_verification()

    def test_authoritative_comment_identity_edits_deletion_duplicates_and_scope_fail_closed(
        self,
    ):
        mutations = [
            lambda: self.api["issues/comments/31"].pop("performed_via_github_app"),
            lambda: self.api["issues/comments/31"]["performed_via_github_app"].update(
                id=10
            ),
            lambda: self.api["issues/comments/31"]["user"].update(id=456),
            lambda: self.api["issues/comments/31"].update(
                updated_at="2026-01-01T00:00:00Z"
            ),
            lambda: self.api["issues/comments/31"].update(
                body=self.comment["body"] + " "
            ),
            lambda: self.api.pop("issues/comments/31"),
            lambda: self.api["issues/comments/31"].update(
                issue_url="https://api.github.com/repos/F0rge/f0rge/issues/901"
            ),
            lambda: self.api["issues/900/comments?per_page=100&page=1"].append(
                dict(self.comment, id=32)
            ),
            lambda: self.api["pulls/900"].update(merged=False),
            lambda: self.api[""].update(id=1234),
            lambda: self.api["public/apps/release-bot"]["permissions"].update(
                actions="write"
            ),
            lambda: self.api["public/apps/release-bot"]["permissions"].update(
                contents="write"
            ),
            lambda: self.api["public/users/release-bot%5Bbot%5D"].update(id=456),
        ]
        for mutation in mutations:
            baseline = copy.deepcopy(self.api)
            mutation()
            with (
                self.subTest(mutation=mutation),
                self.assertRaises(release.ReleaseError),
            ):
                release.agent_apply(77, str(uuid.uuid4()), self.policy)
            self.assertEqual(self.mutations, [])
            self.api.clear()
            self.api.update(baseline)

    def test_comment_and_nonce_reservations_block_a_second_run_without_effects(self):
        binding = self.manifest["release_request"]
        for name in (
            f"comment-{binding['comment_id']}.json",
            f"request-{binding['request_id']}.json",
        ):
            path = self.root / name
            path.write_text('{"state":"previously_reserved"}')
            with self.subTest(journal=name), self.assertRaises(FileExistsError):
                release.agent_apply(77, str(uuid.uuid4()), self.policy)
            self.assertEqual(self.mutations, [])
            self.assertFalse((self.root / "77-1.json").exists())
            path.unlink()  # Separate synthetic pre-existing reservation scenarios.

    def test_target_major_must_match_policy_provider_and_actual_image_retest(self):
        for major in (None, True, 17):
            self.policy["postgres_major"] = major
            with self.subTest(policy=major), self.assertRaises(release.ReleaseError):
                release.agent_apply(77, str(uuid.uuid4()), self.policy)
            self.assertEqual(self.mutations, [])
        self.policy["postgres_major"] = 15
        self.manifest["image_evidence"]["postgres_major"] = 17
        self.refresh_archives()
        with self.assertRaises(release.ReleaseError):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(self.mutations, [])
        self.manifest["image_evidence"]["postgres_major"] = 15
        path = Path(self.policy["provider_receipt"])
        receipt = json.loads(path.read_text())
        receipt["postgres_major"] = 17
        path.write_text(json.dumps(receipt))
        self.manifest["receipt_hashes"]["provider"] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        with self.assertRaisesRegex(release.ReleaseError, "Provider PostgreSQL"):
            release.verify_receipts(self.manifest, self.policy)
        self.assertEqual(self.mutations, [])

    def test_comment_event_uses_rest_identity_fallback_and_rejects_untrusted_event_context(
        self,
    ):
        event = {
            "action": "created",
            "repository": {
                "id": release.REPOSITORY_ID,
                "full_name": release.REPOSITORY,
            },
            "issue": {"number": 900, "pull_request": {}},
            "sender": dict(self.run["actor"]),
            "comment": dict(self.comment),
        }
        event["comment"].pop("performed_via_github_app")
        context = {
            "GITHUB_REPOSITORY": release.REPOSITORY,
            "GITHUB_REPOSITORY_ID": str(release.REPOSITORY_ID),
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_EVENT_NAME": "issue_comment",
            "GITHUB_ACTOR": "release-bot[bot]",
            "GITHUB_TRIGGERING_ACTOR": "release-bot[bot]",
        }
        result = release.workflow_request(event, context, self.policy)
        self.assertEqual(result["release_request"], self.manifest["release_request"])
        for key, value in (
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_REF", "refs/pull/1/merge"),
            ("GITHUB_TRIGGERING_ACTOR", release.OWNER),
        ):
            with self.subTest(context=key), self.assertRaises(release.ReleaseError):
                release.workflow_request(event, {**context, key: value}, self.policy)
        event["action"] = "edited"
        with self.assertRaises(release.ReleaseError):
            release.workflow_request(event, context, self.policy)
        event["action"] = "created"
        event["comment"]["performed_via_github_app"] = {"id": 10, "slug": "wrong-app"}
        with self.assertRaisesRegex(release.ReleaseError, "Event App identity"):
            release.workflow_request(event, context, self.policy)

    def test_human_dispatch_is_publication_only_even_with_fake_approval_artifact(self):
        self.run.update(event="workflow_dispatch")
        self.manifest["release_request"] = None
        self.refresh_archives()
        release.validate_publication(self.manifest, self.run)
        with self.assertRaises(release.ReleaseError):
            release.agent_apply(77, str(uuid.uuid4()), self.policy)
        self.assertEqual(self.mutations, [])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).resolve().parents[1] / "workflows"
        self.workflow = yaml.safe_load((directory / "release-buycycle.yml").read_text())
        self.ci = yaml.safe_load((directory / "ci.yml").read_text())

    def test_only_trusted_main_comment_or_publication_dispatch_has_no_provider_mutation(
        self,
    ):
        trigger = self.workflow.get("on", self.workflow.get(True))
        self.assertEqual(set(trigger), {"workflow_dispatch", "issue_comment"})
        self.assertEqual(trigger["issue_comment"], {"types": ["created"]})
        self.assertNotIn("request_approval", trigger["workflow_dispatch"]["inputs"])
        request = self.workflow["jobs"]["request"]
        self.assertEqual(
            request["permissions"],
            {"contents": "read", "actions": "read", "pull-requests": "read"},
        )
        self.assertIn("github.ref == 'refs/heads/main'", request["if"])
        for job in self.workflow["jobs"].values():
            for step in job["steps"]:
                if step.get("uses", "").startswith("actions/checkout@"):
                    self.assertEqual(step["with"]["ref"], "${{ github.sha }}")
                    self.assertIs(step["with"]["persist-credentials"], False)
        publish = self.workflow["jobs"]["publish"]
        self.assertEqual(publish["runs-on"], "ubuntu-24.04-arm")
        self.assertIn("github.ref == 'refs/heads/main'", publish["if"])
        commands = "\n".join(
            step.get("run", "")
            for job in self.workflow["jobs"].values()
            for step in job["steps"]
        )
        for forbidden in [
            "docker build",
            "buildx build",
            "agent-apply",
            " promote ",
            "COOLIFY_",
            "railway up",
            "curl ",
        ]:
            self.assertNotIn(forbidden, commands)
        self.assertIn("buycycle_release.py prepare", commands)
        self.assertIn("image_rehearsal.py --image", commands)
        self.assertIn('--postgres-major "$POSTGRES_MAJOR"', commands)
        self.assertNotIn("${{ github.event.comment.body", commands)
        self.assertIn("docker pull --platform linux/arm64", commands)
        self.assertIn(
            'verify-registry --image "$PINNED_IMAGE" --config-digest "$CONFIG_DIGEST"',
            commands,
        )
        self.assertIn(
            "evidence['config_digest'] == candidate['image_evidence']['config_digest']",
            commands,
        )

    def test_protected_approval_cannot_be_confused_with_publication(self):
        approve = self.workflow["jobs"]["approve"]
        self.assertIn("github.event_name == 'issue_comment'", approve["if"])
        self.assertIn("needs.request.outputs.request_approval == 'true'", approve["if"])
        self.assertEqual(
            approve["environment"], {"name": "production", "deployment": False}
        )
        self.assertEqual(
            approve["permissions"],
            {"contents": "read", "actions": "read", "pull-requests": "read"},
        )
        commands = "\n".join(step.get("run", "") for step in approve["steps"])
        self.assertIn("revalidate-request", commands)
        self.assertIn("release_request", commands)
        self.assertIn("publication_sha256", commands)
        self.assertIn('test "$GITHUB_RUN_ATTEMPT" = 1', commands)

    def test_arm_image_job_is_a_required_uncached_nx_check(self):
        image = self.ci["jobs"]["buycycle-image"]
        self.assertNotIn("if", image)
        self.assertEqual(image["runs-on"], "ubuntu-24.04-arm")
        self.assertIn("buycycle-image", self.ci["jobs"]["ci"]["needs"])
        commands = "\n".join(step.get("run", "") for step in image["steps"])
        self.assertIn("npx nx affected -t=container-test", commands)
        self.assertIn('test -s "$BUYCYCLE_IMAGE_OUTPUT/image.tar"', commands)
        self.assertIn('test -s "$BUYCYCLE_IMAGE_OUTPUT/evidence.json"', commands)
        project = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "apps/buycycle/backend/project.json"
            ).read_text()
        )
        self.assertIs(project["targets"]["container-test"]["cache"], False)

    def test_every_workflow_shell_block_parses_without_executing_it(self):
        for workflow in [self.workflow, self.ci]:
            for job in workflow["jobs"].values():
                for step in job["steps"]:
                    if "run" in step:
                        result = subprocess.run(
                            ["bash", "-n"],
                            input=step["run"].encode(),
                            capture_output=True,
                            check=False,
                        )
                        self.assertEqual(result.returncode, 0, step.get("name"))


if __name__ == "__main__":
    unittest.main()
