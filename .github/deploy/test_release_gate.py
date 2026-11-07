"""Offline denials for the fail-closed release gate. No network and no deploy.

These tests show that decide() and the workflow env adapter return deny.
They do not show that an approved release can happen. There is no allow path,
no identity binding, and no digest promotion.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import release_gate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHA_A = "a" * 40
SHA_B = "b" * 40
DIGEST_A = "sha256:" + "ab" * 32
DIGEST_B = "sha256:" + "cd" * 32


def _filled(**overrides: object) -> dict:
    """A synthetic record that is not what either workflow sends.

    event_name is deliberately not a GitHub event these workflows emit, so
    the denial is the missing external binding rather than the event class.
    """
    evidence = {
        "event_name": "not-a-github-event",
        "ref_kind": "sha",
        "sha": SHA_A,
        "ci_head_sha": SHA_A,
        "digest": DIGEST_A,
        "ci_artifact_digest": DIGEST_A,
        "target": "dk-tag-printer-backend",
        "approved_target": "dk-tag-printer-backend",
        "ci_conclusion": "success",
        "ci_event": "push",
        "ci_head_branch": "main",
        "ci_workflow_path": ".github/workflows/ci.yml",
        "actor": "leothesouthafrican",
        "run_attempt": 1,
        "rerun": False,
        "rebuild": False,
        "mutable_tag": False,
        "artifact_changed_after_ci": False,
        "allow": False,
    }
    evidence.update(overrides)
    return evidence


class ReleaseGateTest(unittest.TestCase):
    def assert_denied(self, evidence: dict, reason: str) -> None:
        result = release_gate.decide(evidence)
        self.assertEqual(result["decision"], "deny")
        self.assertIn(release_gate.BINDING, result["reasons"])
        self.assertIn(reason, result["reasons"])

    def test_filled_synthetic_record_denies_only_for_missing_binding(self) -> None:
        result = release_gate.decide(_filled())
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["reasons"], [release_gate.BINDING])

    def test_decision_constant_stays_deny(self) -> None:
        self.assertEqual(release_gate.DECISION, "deny")
        result = release_gate.decide(_filled(allow=True))
        self.assertEqual(result["decision"], release_gate.DECISION)
        self.assertIn("self_approval_rejected", result["reasons"])

    def test_mismatched_sha_and_digest_and_target(self) -> None:
        self.assert_denied(_filled(ci_head_sha=SHA_B), "sha_mismatch")
        self.assert_denied(_filled(ci_artifact_digest=DIGEST_B), "digest_mismatch")
        self.assert_denied(_filled(approved_target="marrow-api"), "target_mismatch")

    def test_sha_and_digest_must_be_exact(self) -> None:
        self.assert_denied(_filled(sha="main"), "sha_not_exact")
        self.assert_denied(_filled(digest="latest"), "digest_not_exact")
        self.assert_denied(_filled(target=""), "target_unknown")
        for component in ("auto", "all", "api", "mcp", "frontend"):
            self.assert_denied(_filled(target=component), "target_unknown")

    def test_ci_states_cannot_authorize(self) -> None:
        for conclusion in ("", "pending", "failure", "skipped", "cancelled", "stale"):
            self.assert_denied(_filled(ci_conclusion=conclusion), "ci_not_success")
        for event in ("pull_request", "workflow_dispatch", "schedule", "check_suite"):
            self.assert_denied(_filled(ci_event=event), "ci_event_not_trusted")

    def test_untrusted_event_ref_and_actor(self) -> None:
        self.assert_denied(_filled(event_name="pull_request"), "event_cannot_authorize")
        self.assert_denied(_filled(event_name="pull_request_target"), "event_cannot_authorize")
        self.assert_denied(_filled(event_name="push"), "event_cannot_authorize")
        self.assert_denied(_filled(event_name="workflow_run"), "event_cannot_authorize")
        self.assert_denied(_filled(event_name="schedule"), "event_cannot_authorize")
        self.assert_denied(_filled(ref_kind="tag", mutable_tag=True), "mutable_ref")
        self.assert_denied(_filled(actor="", untrusted_actor=True), "actor_untrusted")
        self.assert_denied(_filled(ci_workflow_path=".github/workflows/evil.yml"), "ci_workflow_untrusted")

    def test_dispatch_and_rerun_are_not_approval(self) -> None:
        self.assert_denied(_filled(event_name="workflow_dispatch"), "manual_or_rerun_cannot_authorize")
        self.assert_denied(_filled(run_attempt=2), "run_attempt_cannot_authorize")
        self.assert_denied(_filled(rerun=True), "run_attempt_cannot_authorize")
        fictional = release_gate.decide(_filled(event_name="workflow_dispatch_rerun"))
        self.assertEqual(fictional["decision"], "deny")
        self.assertNotIn("manual_or_rerun_cannot_authorize", fictional["reasons"])
        self.assertEqual(fictional["reasons"], [release_gate.BINDING])

    def test_text_and_repo_flag_cannot_approve(self) -> None:
        self.assert_denied(_filled(pr_body="Leo approved"), "pr_text_cannot_approve")
        self.assert_denied(_filled(approval_text="approved"), "pr_text_cannot_approve")
        self.assert_denied(_filled(approval_file=True), "repo_file_cannot_approve")

    def test_rebuild_and_invalidation(self) -> None:
        self.assert_denied(_filled(rebuild=True), "rebuild_not_promotion")
        self.assert_denied(_filled(artifact_changed_after_ci=True), "artifact_invalidated")

    def test_deploy_workflow_run_env_records_upstream_and_still_denies(self) -> None:
        env = {
            "EVENT_NAME": "workflow_run",
            "SHA": SHA_A,
            "TARGET": "auto",
            "ACTOR": "leothesouthafrican",
            "RUN_ATTEMPT": "1",
            "CI_CONCLUSION": "success",
            "CI_EVENT": "push",
            "CI_HEAD_SHA": SHA_A,
            "CI_HEAD_BRANCH": "main",
            "CI_WORKFLOW_PATH": ".github/workflows/ci.yml",
        }
        evidence = release_gate.evidence_from_env(env)
        self.assertEqual(evidence["ci_conclusion"], "success")
        self.assertEqual(evidence["ci_event"], "push")
        self.assertNotIn("digest", evidence)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = release_gate.deny_from_env(env)
        self.assertEqual(code, 1)
        result = json.loads(buf.getvalue())
        self.assertEqual(result["decision"], "deny")
        for reason in (
            "event_cannot_authorize",
            "digest_not_exact",
            "target_unknown",
            release_gate.BINDING,
        ):
            self.assertIn(reason, result["reasons"])
        self.assertNotIn("ci_not_success", result["reasons"])

    def test_deploy_dispatch_env_does_not_invent_ci_success(self) -> None:
        env = {
            "EVENT_NAME": "workflow_dispatch",
            "SHA": "",
            "TARGET": "all",
            "ACTOR": "leothesouthafrican",
            "RUN_ATTEMPT": "1",
        }
        evidence = release_gate.evidence_from_env(env)
        self.assertNotIn("ci_conclusion", evidence)
        self.assert_denied(evidence, "manual_or_rerun_cannot_authorize")
        self.assert_denied(evidence, "ci_not_success")
        self.assert_denied(evidence, "target_unknown")

    def test_release_gate_dispatch_env_typed_digest_still_denies(self) -> None:
        env = {
            "EVENT_NAME": "workflow_dispatch",
            "SHA": SHA_A,
            "DIGEST": DIGEST_A,
            "TARGET": "marrow-api",
            "ACTOR": "leothesouthafrican",
            "RUN_ATTEMPT": "2",
            "REF_KIND": "sha",
        }
        evidence = release_gate.evidence_from_env(env)
        self.assertNotIn("ci_conclusion", evidence)
        result = release_gate.decide(evidence)
        self.assertEqual(result["decision"], "deny")
        for reason in (
            "manual_or_rerun_cannot_authorize",
            "run_attempt_cannot_authorize",
            "ci_not_success",
            release_gate.BINDING,
        ):
            self.assertIn(reason, result["reasons"])

    def test_cli_exits_denied(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HERE / "release_gate.py")],
            input=json.dumps(_filled()),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["decision"], "deny")

    def test_workflow_files_match_the_env_adapter(self) -> None:
        deploy = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        gate = (ROOT / ".github/workflows/release-gate.yml").read_text(encoding="utf-8")
        self.assertNotIn("deploy-reusable.yml", deploy)
        self.assertNotIn("secrets:", deploy)
        self.assertNotIn("COOLIFY_", deploy)
        self.assertNotIn("SMOKE_", deploy)
        self.assertNotIn('ci_conclusion":"success"', deploy)
        self.assertNotIn('actor":""', deploy)
        self.assertIn("CI_EVENT: ${{ github.event.workflow_run.event }}", deploy)
        self.assertIn("CI_CONCLUSION: ${{ github.event.workflow_run.conclusion }}", deploy)
        self.assertIn("release_gate.deny_from_env", deploy)
        self.assertIn("release_gate.deny_from_env", gate)
        self.assertNotIn("secrets:", gate)
        self.assertNotIn("workflow_run:", gate)
        self.assertNotIn("workflow_call:", gate)
        self.assertNotIn("\n          exit 1\n", gate)
        self.assertIn("workflow_dispatch:", gate)


if __name__ == "__main__":
    unittest.main()
