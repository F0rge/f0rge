"""Firstout CD trust-boundary regressions. No provider or registry is contacted."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "cd_build", ROOT / ".github/scripts/firstout-cd.py"
)
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
COMMIT = "a" * 40


class PublicationBoundaryTests(unittest.TestCase):
    def shell(self, response):
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, json.dumps(response), "")

        return run

    def test_untrusted_trigger_rejected_before_any_outbound_request(self):
        for repository, event in (
            ("attacker/fork", "push"),
            ("F0rge/f0rge", "pull_request"),
        ):
            with (
                self.subTest(repository=repository, event=event),
                tempfile.TemporaryDirectory() as tmp,
            ):
                path = Path(tmp) / "event.json"
                path.write_text(
                    json.dumps(
                        {
                            "repository": {"full_name": repository},
                            "workflow_run": {
                                "head_repository": {"full_name": repository},
                                "event": event,
                                "head_branch": "main",
                                "conclusion": "success",
                                "head_sha": COMMIT,
                                "path": ".github/workflows/ci.yml",
                            },
                        }
                    )
                )
                with (
                    patch.dict(
                        os.environ,
                        {"SOURCE_COMMIT": COMMIT, "GITHUB_EVENT_PATH": str(path)},
                    ),
                    patch("subprocess.run") as outbound,
                ):
                    with self.assertRaisesRegex(RuntimeError, "Untrusted CD trigger"):
                        BUILD.gate()
                    outbound.assert_not_called()

    def test_superseded_publish_never_tags_or_pushes_an_image(self):
        with (
            patch.dict(os.environ, {"SOURCE_COMMIT": COMMIT}),
            patch(
                "subprocess.run", side_effect=self.shell({"object": {"sha": "b" * 40}})
            ) as outbound,
        ):
            with self.assertRaisesRegex(RuntimeError, "superseded"):
                BUILD.publish()
            self.assertEqual(outbound.call_count, 1)
            self.assertEqual(outbound.call_args.args[0][0], "gh")

    def test_open_trusted_journal_pauses_release(self):
        issue = {
            "title": "[Firstout CD] " + COMMIT,
            "state": "open",
            "user": {"login": "github-actions[bot]", "type": "Bot"},
            "body": '```json\n{"state":"ambiguous"}\n```',
        }
        with (
            patch("subprocess.run", side_effect=self.shell([issue])),
            self.assertRaisesRegex(RuntimeError, "paused"),
        ):
            BUILD.last_release()

    def test_untrusted_issue_cannot_supply_release_baseline(self):
        issue = {
            "title": "[Firstout CD] " + COMMIT,
            "state": "closed",
            "user": {"login": "attacker"},
            "body": '```json\n{"state":"succeeded","source_commit":"'
            + COMMIT
            + '"}\n```',
        }
        with patch("subprocess.run", side_effect=self.shell([issue])):
            self.assertIsNone(BUILD.last_release())

    def test_failed_commands_do_not_leak_registry_credentials(self):
        response = subprocess.CompletedProcess(
            ["docker"], 1, "private token", "secret password"
        )
        with patch("subprocess.run", return_value=response):
            with self.assertRaises(RuntimeError) as error:
                BUILD.command(["docker", "push"])
            self.assertNotIn("private token", str(error.exception))
            self.assertNotIn("secret password", str(error.exception))


class WorkflowBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / ".github/workflows/cd-firstout.yml").read_text()
        self.workflow = yaml.safe_load(self.text)

    def test_only_trusted_main_ci_can_start_the_pipeline(self):
        events = self.workflow.get("on", self.workflow.get(True))
        self.assertEqual(set(events), {"workflow_run"})
        self.assertEqual(events["workflow_run"]["workflows"], ["CI"])
        condition = self.workflow["jobs"]["tested-images"]["if"]
        for guard in (
            "conclusion == 'success'",
            "event == 'push'",
            "head_branch == 'main'",
            "head_repository.full_name == 'F0rge/f0rge'",
        ):
            self.assertIn(guard, condition)
        self.assertIs(self.workflow["concurrency"]["cancel-in-progress"], False)

    def test_provider_secret_is_only_in_fixed_deploy_environment(self):
        jobs = self.workflow["jobs"]
        self.assertNotIn("environment", jobs["tested-images"])
        self.assertEqual(jobs["deploy"]["environment"], "firstout-production")
        self.assertNotIn("RAILWAY", json.dumps(jobs["tested-images"]))
        provider_steps = [
            s
            for s in jobs["deploy"]["steps"]
            if "FIRSTOUT_RAILWAY_TOKEN" in json.dumps(s)
        ]
        self.assertEqual(len(provider_steps), 1)
        self.assertIn("test -n", provider_steps[0]["run"])

    def test_job_leaves_time_for_both_rollout_and_recovery(self):
        import ast

        tree = ast.parse((ROOT / ".github/deploy/firstout_cd.py").read_text())
        waits = [
            node.value.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "MAX_WAIT_SECONDS"
                for target in node.targets
            )
        ]
        self.assertEqual(len(waits), 1)
        # Two forward deployments plus two recoveries, with extra time for
        # verification, external requests and durable journal writes.
        self.assertGreaterEqual(
            self.workflow["jobs"]["deploy"]["timeout-minutes"] * 60, waits[0] * 4 + 600
        )

    def test_both_images_are_tested_before_publication(self):
        steps = self.workflow["jobs"]["tested-images"]["steps"]
        builds = [s for s in steps if s.get("uses") == "docker/build-push-action@v6"]
        self.assertEqual(len(builds), 2)
        for build in builds:
            self.assertEqual(build["with"]["platforms"], "linux/amd64")
            self.assertIs(build["with"]["load"], True)
            self.assertIs(build["with"]["push"], False)
        names = [s.get("name", "") for s in steps]
        self.assertLess(
            names.index(
                "Test exact images and database compatibility without external services"
            ),
            names.index("Authenticate publication only"),
        )
        self.assertIn("PREVIOUS_BACKEND_IMAGE", self.text)

    def test_backend_has_no_replica_start_migration_or_unreviewed_predeploy(self):
        import tomllib

        config = tomllib.loads(
            (ROOT / "apps/firstout/backend/railway.toml").read_text()
        )
        self.assertNotIn("alembic", config["deploy"]["startCommand"])
        self.assertEqual(
            config["deploy"]["preDeployCommand"],
            "uv run --no-sync python -m app.commands.release_migrate",
        )
        self.assertEqual(config["deploy"]["healthcheckPath"], "/api/v1/ready")
        dockerfile = (ROOT / "apps/firstout/backend/Dockerfile").read_text()
        self.assertIn("org.opencontainers.image.revision=$SOURCE_COMMIT", dockerfile)
        self.assertIn("ENV SOURCE_COMMIT=$SOURCE_COMMIT", dockerfile)

    def test_manual_and_automatic_release_probes_use_same_postgres_major(self):
        manual = (ROOT / ".github/scripts/firstout-api-container-smoke.py").read_text()
        automatic = (ROOT / ".github/scripts/firstout-cd-containers.mjs").read_text()
        # Both paths exercise production-shaped migrations. Catch independent
        # fixture-version drift; the live-version match still needs provider
        # inspection and an actual image/database compatibility rehearsal.
        image = r'"postgres:([0-9]+)"'
        manual_majors = set(re.findall(image, manual))
        automatic_majors = set(re.findall(image, automatic))
        self.assertEqual(len(manual_majors), 1)
        self.assertEqual(automatic_majors, manual_majors)


if __name__ == "__main__":
    unittest.main()
