"""Offline mismatch and workflow-hold tests; no live credentials or providers."""

from __future__ import annotations

import copy
import re
import unittest
from pathlib import Path

import yaml

from release_evidence import compare_evidence

SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64


def is_inert_script(script: str) -> bool:
    """Permit only literal single-quoted messages and an optional failure."""
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    return bool(lines) and all(
        line == "exit 1" or re.fullmatch(r"echo '[^'`$\\]*'", line) is not None
        for line in lines
    )


def fixture() -> tuple[dict, dict, list[dict]]:
    candidate = {
        "repository": "F0rge/f0rge",
        "commit": SHA,
        "service": "marrow-api",
        "destination": "railway",
        "architecture": "amd64",
        "digest": DIGEST,
    }
    artifact = {**candidate, "tested": True, "rebuilt": False}
    checks = [
        {
            "name": "ci",
            "repository": "F0rge/f0rge",
            "commit": SHA,
            "status": "completed",
            "conclusion": "success",
            "run_id": 10,
            "attempt": 1,
        },
        {
            "name": "playwright smoke",
            "repository": "F0rge/f0rge",
            "commit": SHA,
            "status": "completed",
            "conclusion": "success",
            "run_id": 20,
            "attempt": 2,
        },
    ]
    return candidate, artifact, checks


class EvidenceConsistencyTests(unittest.TestCase):
    def test_distinct_ci_runs_and_attempts_are_valid(self) -> None:
        self.assertEqual(compare_evidence(*fixture()), [])

    def test_artifact_mismatches_are_reported(self) -> None:
        for field, value in (
            ("repository", "other/repo"),
            ("commit", "c" * 40),
            ("service", "firstout-api"),
            ("destination", "pi"),
            ("architecture", "arm64"),
            ("digest", "sha256:" + "d" * 64),
            ("tested", False),
            ("rebuilt", True),
        ):
            with self.subTest(field=field):
                candidate, artifact, checks = fixture()
                artifact[field] = value
                self.assertTrue(compare_evidence(candidate, artifact, checks))

    def test_invalid_candidate_and_check_evidence_are_reported(self) -> None:
        for field, value in (
            ("repository", "other/repo"),
            ("commit", "main"),
            ("digest", "latest"),
            ("service", ""),
        ):
            with self.subTest(field=field):
                candidate, artifact, checks = fixture()
                candidate[field] = value
                self.assertTrue(compare_evidence(candidate, artifact, checks))
        for field, value in (
            ("commit", "c" * 40),
            ("repository", "other/repo"),
            ("status", "in_progress"),
            ("conclusion", "skipped"),
            ("run_id", True),
            ("attempt", 0),
        ):
            with self.subTest(check_field=field):
                candidate, artifact, checks = fixture()
                checks[1][field] = value
                self.assertTrue(compare_evidence(candidate, artifact, checks))

    def test_missing_and_duplicate_checks_are_reported(self) -> None:
        candidate, artifact, checks = fixture()
        self.assertTrue(compare_evidence(candidate, artifact, checks[:1]))
        self.assertTrue(
            compare_evidence(candidate, artifact, checks + [copy.deepcopy(checks[0])])
        )


class WorkflowHoldTests(unittest.TestCase):
    def test_inert_script_rejects_shell_control_and_substitution(self) -> None:
        self.assertTrue(is_inert_script("echo 'A literal message'\nexit 1\n"))
        for script in (
            "echo ok; curl https://example.com",
            "echo 'ok'; curl https://example.com",
            "echo 'ok' && curl https://example.com",
            "echo 'ok' | sh",
            "echo $(curl https://example.com)",
            "echo '$(curl https://example.com)'",
            "echo `id`",
            'echo "double quoted"',
            "exit 1; curl https://example.com",
            "",
        ):
            with self.subTest(script=script):
                self.assertFalse(is_inert_script(script))

    def test_only_manual_preparation_and_inert_reusable_entry_points_exist(
        self,
    ) -> None:
        workflows = Path(__file__).resolve().parent.parent / "workflows"
        for filename, trigger in (
            ("deploy.yml", "workflow_dispatch"),
            ("deploy-reusable.yml", "workflow_call"),
        ):
            with self.subTest(workflow=filename):
                data = yaml.load(
                    (workflows / filename).read_text(), Loader=yaml.BaseLoader
                )
                self.assertEqual(set(data), {"name", "on", "permissions", "jobs"})
                self.assertEqual(set(data["on"]), {trigger})
                self.assertEqual(data["permissions"], {"contents": "read"})
                self.assertEqual(len(data["jobs"]), 1)
                job = next(iter(data["jobs"].values()))
                self.assertEqual(
                    set(job),
                    {"name", "environment", "runs-on", "timeout-minutes", "steps"},
                )
                environment = job["environment"]
                self.assertEqual(
                    environment.get("name")
                    if isinstance(environment, dict)
                    else environment,
                    "production",
                )
                self.assertEqual(environment["deployment"], "false")
                self.assertNotIn("secrets", job)
                self.assertNotIn("uses", job)
                self.assertEqual(len(job["steps"]), 1)
                self.assertEqual(set(job["steps"][0]), {"name", "run"})
                script = job["steps"][0]["run"]
                self.assertTrue(is_inert_script(script))
                self.assertNotIn("${{", script)
                if filename == "deploy.yml":
                    self.assertIn("no production deployment", script)
                else:
                    self.assertIn("exit 1", script)


if __name__ == "__main__":
    unittest.main()
