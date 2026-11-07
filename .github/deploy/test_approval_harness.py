"""Fixture checks for the approval harness. No network and no provider calls.

A permit here is the validator result for a SimulatedBoundary. It is not a
person and not a provider digest. execute() is asserted separately: the
plan is nonempty on permit, and the sink is not called while EFFECTS_ENABLED
is false.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import approval_harness

NOW = datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc)
SHA = "a" * 40
DIGEST = "sha256:" + "ab" * 32
RUN_ID = 42382614400
ATTEMPT = 1


class CountingSink:
    def __init__(self) -> None:
        self.deploy_calls = 0

    def deploy(self, *_args: object, **_kwargs: object) -> None:
        self.deploy_calls += 1


def _stamp(receipt: dict) -> dict:
    reviewed = NOW - timedelta(minutes=1)
    receipt["reviewed_at"] = reviewed.isoformat()
    receipt["expires_at"] = (reviewed + approval_harness.MAX_REVIEW_AGE).isoformat()
    receipt["approval_tuple"] = approval_harness.tuple_digest(receipt)
    receipt["approval_id"] = "approval-fixture-1"
    return receipt


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
        "requester_id": 9001,
        "prevent_self_review": True,
        "can_admins_bypass": False,
        "admin_bypass_used": False,
        "rebuild": False,
        "ref_kind": "sha",
    }
    receipt.update(overrides)
    return _stamp(receipt)


class ApprovalHarnessTest(unittest.TestCase):
    def decide(self, receipt: dict, boundary: object | None = None, store: object | None = None):
        result = approval_harness.evaluate(
            receipt,
            approval_harness.SimulatedBoundary() if boundary is None else boundary,
            approval_harness.MemoryReplayStore() if store is None else store,
            now=NOW,
        )
        effect = approval_harness.execute(result, CountingSink())
        return result, effect

    def assert_denied(self, receipt: dict, reason: str, boundary: object | None = None, store: object | None = None) -> None:
        result, effect = self.decide(receipt, boundary, store)
        self.assertFalse(result["permit"])
        self.assertIn(reason, result["reasons"])
        self.assertFalse(result["live_human_approval_proved"])
        self.assertFalse(result["provider_digest_proved"])
        self.assertEqual(effect["planned"], [])
        self.assertFalse(effect["executed"])

    def test_simulated_matching_tuple_permits_and_plans_without_calling_sink(self) -> None:
        sink = CountingSink()
        result = approval_harness.evaluate(
            _receipt(),
            approval_harness.SimulatedBoundary(),
            approval_harness.MemoryReplayStore(),
            now=NOW,
        )
        self.assertTrue(result["permit"])
        self.assertEqual(result["reasons"], [])
        self.assertFalse(result["live_human_approval_proved"])
        self.assertFalse(result["provider_digest_proved"])
        self.assertFalse(approval_harness.EFFECTS_ENABLED)
        effect = approval_harness.execute(result, sink)
        self.assertEqual(effect["planned"], ["reuse_existing_deployment"])
        self.assertFalse(effect["executed"])
        self.assertEqual(sink.deploy_calls, 0)

    def test_firstout_and_storefront_commerce_bindings_permit(self) -> None:
        firstout = _receipt(
            service="firstout-api",
            github_environment_name="Firstout / production",
            github_environment_id=24561991680,
            railway_project_id="c76d8df1-d839-454c-a94a-79b930deaf38",
            railway_environment_id="9f7b0c34-bd95-442b-b746-a9791dcc2895",
            service_id="77a83033-b75e-4da1-88d0-b6db39bcedaf",
        )
        commerce = _receipt(
            service="storefront-commerce",
            github_environment_name="storefront / production",
            github_environment_id=23387956905,
            railway_project_id="d58a2884-d366-4230-9555-8b7bb4e42d4f",
            railway_environment_id="d73ff2d5-816d-4bc8-85b4-71a85b0398fa",
            service_id="bffcd9ce-09d8-4cff-948f-8f03c08ba8c0",
        )
        self.assertTrue(self.decide(firstout)[0]["permit"])
        self.assertTrue(self.decide(commerce)[0]["permit"])

    def test_storefront_refuses_the_das_kasas_github_environment(self) -> None:
        self.assert_denied(
            _receipt(
                github_environment_name="DasKasas / production",
                github_environment_id=24635670941,
                service="storefront",
                railway_project_id="d58a2884-d366-4230-9555-8b7bb4e42d4f",
                railway_environment_id="d73ff2d5-816d-4bc8-85b4-71a85b0398fa",
                service_id="6fc1e3ee-4c61-49f7-8533-d2ce975df5a4",
            ),
            "target_unmapped",
        )

    def test_json_boundary_and_string_ids_do_not_permit(self) -> None:
        self.assert_denied(
            _receipt(),
            "live_receipt_not_fetched",
            {"kind": "simulated", "receipt_source": "github_environment_api_read_by_non_approver_app"},
        )
        self.assert_denied(_receipt(requester_id="38779415"), "id_type_invalid")
        self.assert_denied(_receipt(approver_user_id="38779415"), "id_type_invalid")
        self.assert_denied(_receipt(requester_id=True), "id_type_invalid")
        self.assert_denied(_receipt(ci_run_id=True), "id_type_invalid")
        self.assert_denied(_receipt(github_environment_id="19158860710"), "id_type_invalid")
        self.assert_denied(_receipt(receipt_source="github_environment_api_read_by_non_approver_app"), "unexpected_field")
        self.assert_denied(_receipt(approved=True), "unexpected_field")
        self.assert_denied(_receipt(consumed_approval_ids=["approval-fixture-1"]), "unexpected_field")

    def test_missing_workflow_path_and_untrusted_event(self) -> None:
        self.assert_denied(_receipt(workflow_path=None), "workflow_path_missing")
        self.assert_denied(_receipt(event_name="push"), "event_untrusted")
        self.assert_denied(_receipt(event_name="workflow_run"), "event_untrusted")
        self.assert_denied(_receipt(event_name="pull_request"), "event_untrusted")
        self.assert_denied(_receipt(fork=True), "untrusted_workflow")
        self.assert_denied(_receipt(workflow_path=".github/workflows/deploy.yml"), "untrusted_workflow")

    def test_time_window_replay_and_identity_binding(self) -> None:
        far = _receipt()
        far["expires_at"] = (NOW + timedelta(days=3650)).isoformat()
        far["approval_tuple"] = approval_harness.tuple_digest(far)
        self.assert_denied(far, "expiry_window_too_long")
        stale = _receipt()
        stale["reviewed_at"] = (NOW - timedelta(hours=2)).isoformat()
        stale["expires_at"] = (NOW - timedelta(minutes=30)).isoformat()
        stale["approval_tuple"] = approval_harness.tuple_digest(stale)
        self.assert_denied(stale, "approval_expired")
        store = approval_harness.MemoryReplayStore()
        first, _ = self.decide(_receipt(), store=store)
        self.assertTrue(first["permit"])
        self.assert_denied(_receipt(), "approval_replayed", store=store)
        swapped = _receipt(approver_user_id=1)
        self.assert_denied(swapped, "reviewer_not_required_human")
        self.assertNotEqual(approval_harness.tuple_digest(_receipt()), approval_harness.tuple_digest(swapped))

    def test_substitutions_of_run_attempt_target_artifact_and_environment(self) -> None:
        self.assert_denied(_receipt(ci_run_id=1), "check_not_success")
        self.assert_denied(_receipt(ci_run_attempt=2), "check_not_success")
        self.assert_denied(_receipt(artifact_sha256="sha256:" + "cd" * 32), "artifact_mismatch")
        self.assert_denied(_receipt(service="marrow-worker"), "provider_tuple_mismatch")
        self.assert_denied(_receipt(github_environment_id=1), "environment_id_mismatch")
        self.assert_denied(_receipt(sha="b" * 40), "sha_not_exact")
        self.assert_denied(_receipt(deployment_id="other"), "deployment_id_mismatch")
        self.assert_denied(_receipt(promotion="oci_digest"), "oci_digest_receipt_unverified")
        self.assert_denied(_receipt(rebuild=True), "rebuild_or_mutable_tag")
        self.assert_denied(_receipt(requester_id=38779415), "requester_is_approver")
        self.assert_denied(_receipt(can_admins_bypass=True), "admin_bypass")
        self.assert_denied(_receipt(admin_bypass_used=True), "admin_bypass")
        self.assert_denied(_receipt(prevent_self_review=False), "self_review_not_prevented")

    def test_unmapped_and_generic_environment(self) -> None:
        for service in (
            "dk-tag-printer-backend",
            "dk-tag-printer-frontend",
            "buycycle",
            "environment-monitor-backend",
            "environment-monitor-frontend",
        ):
            self.assert_denied(_receipt(service=service), "target_unmapped")
        self.assert_denied(
            _receipt(github_environment_name="production", github_environment_id=17911756005),
            "environment_not_candidate",
        )

    def test_dict_replay_list_is_not_the_store(self) -> None:
        self.assert_denied(_receipt(), "replay_store_untrusted", store={"consumed_approval_ids": ()})

    def test_denied_decision_plans_nothing(self) -> None:
        result, effect = self.decide({})
        self.assertFalse(result["permit"])
        self.assertEqual(effect["planned"], [])
        self.assertFalse(effect["executed"])


if __name__ == "__main__":
    unittest.main()
