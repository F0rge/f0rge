"""Fixture checks for the approval harness. No network and no provider calls."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import approval_harness

NOW = datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc)
SHA = "a" * 40
DIGEST = "sha256:" + "ab" * 32
RUN_ID = 42382614400
ATTEMPT = 1


class Sink:
    def deploy(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("deploy")

    def change_config(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("config")

    def read_or_write_credential(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("credential")


def _boundary(**overrides: object) -> dict:
    boundary = {
        "kind": "simulated",
        "receipt_source": approval_harness.TRUSTED_RECEIPT_SOURCE,
        "receipt_credential_is_approver_user": False,
        "receipt_credential_is_agent_held_user_token": False,
        "consumed_approval_ids": (),
    }
    boundary.update(overrides)
    return boundary


def _receipt(**overrides: object) -> dict:
    receipt = {
        "repository": "F0rge/f0rge",
        "head_repository": "F0rge/f0rge",
        "ref": "refs/heads/main",
        "deployment_branch_policy": "main",
        "sha": SHA,
        "built_from_sha": SHA,
        "ci_workflow_path": ".github/workflows/ci.yml",
        "workflow_path": ".github/workflows/ci.yml",
        "event_name": "workflow_dispatch",
        "fork": False,
        "ci_run_id": RUN_ID,
        "ci_run_attempt": ATTEMPT,
        "checks": {
            "ci": {"conclusion": "success", "run_id": RUN_ID, "attempt": ATTEMPT},
            "playwright smoke": {"conclusion": "success", "run_id": RUN_ID, "attempt": ATTEMPT},
        },
        "artifact_sha256": DIGEST,
        "approved_artifact_sha256": DIGEST,
        "github_environment_name": "Marrow / production",
        "github_environment_id": 19158860710,
        "service": "marrow-api",
        "railway_project_id": "a633a271-5bb0-461e-8eb5-1acb9e126a59",
        "railway_environment_id": "ff59293a-ac24-4e1c-8d19-0756bc577016",
        "service_id": "e4b05e39-4717-45fc-9df5-e86e3113422f",
        "deployment_id": "dep-fixture-not-a-live-deploy",
        "approved_deployment_id": "dep-fixture-not-a-live-deploy",
        "promotion": "railway_existing_deployment_reuse",
        "approver_user_id": 38779415,
        "approver_kind": "human_user",
        "requester_kind": "github_app",
        "requester_id": 9001,
        "prevent_self_review": True,
        "can_admins_bypass": False,
        "admin_bypass_used": False,
        "rebuild": False,
        "ref_kind": "sha",
        "expires_at": (NOW + timedelta(minutes=30)).isoformat(),
    }
    receipt["approval_tuple"] = approval_harness.tuple_digest(receipt)
    receipt["approval_id"] = "approval-fixture-1"
    receipt.update(overrides)
    if "approval_tuple" not in overrides and any(
        key in overrides
        for key in (
            "sha",
            "built_from_sha",
            "artifact_sha256",
            "approved_artifact_sha256",
            "deployment_id",
            "ci_run_id",
            "ci_run_attempt",
            "checks",
            "service",
            "github_environment_name",
            "promotion",
        )
    ):
        receipt["approval_tuple"] = approval_harness.tuple_digest(receipt)
    return receipt


class ApprovalHarnessTest(unittest.TestCase):
    def assert_denied(self, receipt: dict, reason: str, boundary: dict | None = None) -> None:
        result = approval_harness.evaluate(receipt, boundary if boundary is not None else _boundary(), now=NOW)
        self.assertFalse(result["permit"])
        self.assertIn(reason, result["reasons"])
        self.assertFalse(result["live_human_approval_proved"])
        effect = approval_harness.execute(result, Sink())
        self.assertFalse(effect["executed"])

    def test_simulated_matching_tuple_permits_without_effects(self) -> None:
        result = approval_harness.evaluate(_receipt(), _boundary(), now=NOW)
        self.assertTrue(result["permit"])
        self.assertEqual(result["reasons"], [])
        self.assertFalse(result["live_human_approval_proved"])
        self.assertFalse(result["provider_digest_proved"])
        self.assertFalse(approval_harness.EFFECTS_ENABLED)
        effect = approval_harness.execute(result, Sink())
        self.assertFalse(effect["executed"])
        self.assertEqual(effect["reason"], "live_promotion_disabled")

    def test_storefront_uses_its_github_environment_not_the_das_kasas_name(self) -> None:
        receipt = _receipt(
            github_environment_name="storefront / production",
            github_environment_id=23387956905,
            service="storefront",
            railway_project_id="d58a2884-d366-4230-9555-8b7bb4e42d4f",
            railway_environment_id="d73ff2d5-816d-4bc8-85b4-71a85b0398fa",
            service_id="6fc1e3ee-4c61-49f7-8533-d2ce975df5a4",
        )
        result = approval_harness.evaluate(receipt, _boundary(), now=NOW)
        self.assertTrue(result["permit"])
        swapped = _receipt(
            github_environment_name="DasKasas / production",
            github_environment_id=24635670941,
            service="storefront",
            railway_project_id="d58a2884-d366-4230-9555-8b7bb4e42d4f",
            railway_environment_id="d73ff2d5-816d-4bc8-85b4-71a85b0398fa",
            service_id="6fc1e3ee-4c61-49f7-8533-d2ce975df5a4",
        )
        self.assert_denied(swapped, "target_unmapped")

    def test_missing_and_untrusted_and_agent_receipts(self) -> None:
        self.assert_denied(_receipt(), "live_receipt_not_fetched", {**_boundary(), "kind": "absent"})
        self.assert_denied(_receipt(), "receipt_source_untrusted", {**_boundary(), "receipt_source": "local_json"})
        self.assert_denied(
            _receipt(),
            "agent_held_approver_credential",
            {**_boundary(), "receipt_credential_is_approver_user": True},
        )
        self.assert_denied(
            _receipt(approved=True, signature_key_holder="agent"),
            "agent_minted_approval",
            {**_boundary(), "kind": "agent_session", "receipt_source": "agent_session"},
        )

    def test_wrong_requester_reviewer_self_approval_and_admin_bypass(self) -> None:
        self.assert_denied(_receipt(approver_user_id=1), "reviewer_not_required_human")
        self.assert_denied(_receipt(requester_kind="user", requester_id=50), "requester_not_separate_app")
        self.assert_denied(_receipt(requester_id=38779415), "requester_is_approver")
        self.assert_denied(_receipt(prevent_self_review=False), "self_review_not_prevented")
        self.assert_denied(_receipt(can_admins_bypass=True), "admin_bypass")
        self.assert_denied(_receipt(admin_bypass_used=True), "admin_bypass")

    def test_stale_replay_and_tuple_mismatch(self) -> None:
        self.assert_denied(_receipt(expires_at=(NOW - timedelta(seconds=1)).isoformat()), "approval_expired")
        self.assert_denied(
            _receipt(),
            "approval_replayed",
            {**_boundary(), "consumed_approval_ids": ("approval-fixture-1",)},
        )
        self.assert_denied(_receipt(approval_tuple="0" * 64), "approval_tuple_mismatch")

    def test_mismatched_tuple_fields(self) -> None:
        self.assert_denied(_receipt(repository="fork/f0rge"), "untrusted_repository")
        self.assert_denied(_receipt(sha="b" * 40), "sha_not_exact")
        self.assert_denied(_receipt(ci_workflow_path=".github/workflows/evil.yml"), "ci_workflow_untrusted")
        self.assert_denied(_receipt(ci_run_id=1), "check_not_success")
        self.assert_denied(_receipt(ci_run_attempt=2), "check_not_success")
        failed = _receipt()
        failed["checks"] = {
            "ci": {"conclusion": "failure", "run_id": RUN_ID, "attempt": ATTEMPT},
            "playwright smoke": {"conclusion": "success", "run_id": RUN_ID, "attempt": ATTEMPT},
        }
        failed["approval_tuple"] = approval_harness.tuple_digest(failed)
        self.assert_denied(failed, "check_not_success")
        self.assert_denied(_receipt(artifact_sha256="sha256:" + "cd" * 32), "artifact_mismatch")
        self.assert_denied(_receipt(railway_project_id="0" * 8), "provider_tuple_mismatch")
        self.assert_denied(_receipt(deployment_id="other-deployment"), "deployment_id_mismatch")

    def test_untrusted_event_and_rebuild(self) -> None:
        self.assert_denied(_receipt(fork=True), "untrusted_workflow")
        self.assert_denied(_receipt(event_name="pull_request"), "event_untrusted")
        self.assert_denied(_receipt(workflow_path=".github/workflows/deploy.yml"), "untrusted_workflow")
        self.assert_denied(_receipt(rebuild=True), "rebuild_or_mutable_tag")
        self.assert_denied(_receipt(tag="latest", ref_kind="tag"), "rebuild_or_mutable_tag")
        self.assert_denied(_receipt(promotion="oci_digest"), "oci_digest_receipt_unverified")

    def test_unmapped_targets_and_generic_environment(self) -> None:
        for service in ("dk-tag-printer-backend", "buycycle", "environment-monitor-backend"):
            self.assert_denied(_receipt(service=service), "target_unmapped")
        self.assert_denied(
            _receipt(github_environment_name="production", github_environment_id=17911756005),
            "environment_not_candidate",
        )

    def test_negative_paths_do_not_touch_the_sink(self) -> None:
        sink = Sink()
        result = approval_harness.evaluate({}, {}, now=NOW)
        self.assertFalse(result["permit"])
        approval_harness.execute(result, sink)


if __name__ == "__main__":
    unittest.main()
