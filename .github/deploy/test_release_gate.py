"""Offline denials for the fail-closed release gate. No network and no deploy."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import release_gate

HERE = Path(__file__).resolve().parent
SHA_A = "a" * 40
SHA_B = "b" * 40
DIGEST_A = "sha256:" + "ab" * 32
DIGEST_B = "sha256:" + "cd" * 32


def _base(**overrides: object) -> dict:
    evidence = {
        "event_name": "workflow_dispatch",
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

    def test_complete_looking_record_still_denies(self) -> None:
        result = release_gate.decide(_base())
        self.assertEqual(result["decision"], "deny")
        self.assertEqual(result["reasons"][-1], release_gate.BINDING)

    def test_mismatched_sha_and_digest_and_target(self) -> None:
        self.assert_denied(_base(ci_head_sha=SHA_B), "sha_mismatch")
        self.assert_denied(_base(ci_artifact_digest=DIGEST_B), "digest_mismatch")
        self.assert_denied(_base(approved_target="marrow-api"), "target_mismatch")

    def test_sha_and_digest_must_be_exact(self) -> None:
        self.assert_denied(_base(sha="main"), "sha_not_exact")
        self.assert_denied(_base(digest="latest"), "digest_not_exact")
        self.assert_denied(_base(target=""), "target_unknown")

    def test_ci_states_cannot_authorize(self) -> None:
        for conclusion in ("", "pending", "failure", "skipped", "cancelled", "stale"):
            self.assert_denied(_base(ci_conclusion=conclusion), "ci_not_success")
        for event in ("pull_request", "workflow_dispatch", "schedule", "check_suite"):
            self.assert_denied(_base(ci_event=event), "ci_event_not_trusted")

    def test_untrusted_event_ref_and_actor(self) -> None:
        self.assert_denied(_base(event_name="pull_request"), "event_cannot_authorize")
        self.assert_denied(_base(event_name="pull_request_target"), "event_cannot_authorize")
        self.assert_denied(_base(event_name="push"), "event_cannot_authorize")
        self.assert_denied(_base(ref_kind="tag", mutable_tag=True), "mutable_ref")
        self.assert_denied(_base(actor="", untrusted_actor=True), "actor_untrusted")
        self.assert_denied(_base(ci_workflow_path=".github/workflows/evil.yml"), "ci_workflow_untrusted")

    def test_manual_rerun_text_and_self_approval(self) -> None:
        self.assert_denied(_base(rerun=True), "manual_or_rerun_cannot_authorize")
        self.assert_denied(_base(pr_body="Leo approved"), "pr_text_cannot_approve")
        self.assert_denied(_base(approval_text="approved"), "pr_text_cannot_approve")
        self.assert_denied(_base(approval_file=True), "repo_file_cannot_approve")
        self.assert_denied(_base(allow=True, approved=True), "self_approval_rejected")

    def test_rebuild_and_invalidation(self) -> None:
        self.assert_denied(_base(rebuild=True), "rebuild_not_promotion")
        self.assert_denied(_base(artifact_changed_after_ci=True), "artifact_invalidated")

    def test_cli_exits_denied(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HERE / "release_gate.py")],
            input=json.dumps(_base()),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["decision"], "deny")

    def test_source_has_no_allow_return(self) -> None:
        text = (HERE / "release_gate.py").read_text(encoding="utf-8")
        self.assertNotIn('return {"decision": "allow"', text)
        self.assertNotIn("decision\": \"allow\"", text)


if __name__ == "__main__":
    unittest.main()
