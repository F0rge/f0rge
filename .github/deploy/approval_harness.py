"""No-effect check of a release tuple.

evaluate() can return permit for one simulated receipt. That object is a
test stand-in for a GitHub environment review read by a credential that is
not user 38779415. Constructing it does not call GitHub and does not prove
a person acted.

execute() does not call a provider, read a secret, or change configuration.
EFFECTS_ENABLED is a constant False. A permit does not turn it on.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

APPROVER_USER_ID = 38779415
REPOSITORY = "F0rge/f0rge"
TRUSTED_CI_WORKFLOW = ".github/workflows/ci.yml"
TRUSTED_CHECKS = ("ci", "playwright smoke")
TRUSTED_RECEIPT_SOURCE = "github_environment_api_read_by_non_approver_app"
EFFECTS_ENABLED = False

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")

# GitHub environment ids from the 2026-11-07 15:57:28 box read. Names are exact.
GITHUB_ENVIRONMENT_IDS = {
    "Marrow / production": 19158860710,
    "Firstout / production": 24561991680,
    "storefront / production": 23387956905,
    "DasKasas / production": 24635670941,
}

# Railway project d58a2884 is named DasKasas and runs the storefront services.
# It is not GitHub environment "DasKasas / production", and it is not dk on Coolify.
RAILWAY_STOREFRONT_PROJECT = "d58a2884-d366-4230-9555-8b7bb4e42d4f"
RAILWAY_STOREFRONT_ENVIRONMENT = "d73ff2d5-816d-4bc8-85b4-71a85b0398fa"

# Service identity for a same-build reuse plan. Deployment ids of live builds
# are not an allow-list: those builds are ca3bc0fb, not a later commit.
BINDINGS: dict[tuple[str, str], dict[str, str]] = {
    ("Marrow / production", "marrow-api"): {
        "railway_project_id": "a633a271-5bb0-461e-8eb5-1acb9e126a59",
        "railway_environment_id": "ff59293a-ac24-4e1c-8d19-0756bc577016",
        "service_id": "e4b05e39-4717-45fc-9df5-e86e3113422f",
    },
    ("Marrow / production", "marrow-worker"): {
        "railway_project_id": "a633a271-5bb0-461e-8eb5-1acb9e126a59",
        "railway_environment_id": "ff59293a-ac24-4e1c-8d19-0756bc577016",
        "service_id": "9e92d7c3-a03c-40f6-ae67-b4bb54e8b127",
    },
    ("Marrow / production", "marrow-mcp"): {
        "railway_project_id": "a633a271-5bb0-461e-8eb5-1acb9e126a59",
        "railway_environment_id": "ff59293a-ac24-4e1c-8d19-0756bc577016",
        "service_id": "7b61e22e-47e8-4618-91d7-3661c111f372",
    },
    ("Marrow / production", "marrow-frontend"): {
        "railway_project_id": "a633a271-5bb0-461e-8eb5-1acb9e126a59",
        "railway_environment_id": "ff59293a-ac24-4e1c-8d19-0756bc577016",
        "service_id": "cd559aaf-a421-4d72-82de-0a1036e51ae7",
    },
    ("Firstout / production", "firstout-api"): {
        "railway_project_id": "c76d8df1-d839-454c-a94a-79b930deaf38",
        "railway_environment_id": "9f7b0c34-bd95-442b-b746-a9791dcc2895",
        "service_id": "77a83033-b75e-4da1-88d0-b6db39bcedaf",
    },
    ("Firstout / production", "firstout-frontend"): {
        "railway_project_id": "c76d8df1-d839-454c-a94a-79b930deaf38",
        "railway_environment_id": "9f7b0c34-bd95-442b-b746-a9791dcc2895",
        "service_id": "10838be1-7a37-4dfc-810a-8805d040d5d7",
    },
    ("storefront / production", "storefront"): {
        "railway_project_id": RAILWAY_STOREFRONT_PROJECT,
        "railway_environment_id": RAILWAY_STOREFRONT_ENVIRONMENT,
        "service_id": "6fc1e3ee-4c61-49f7-8533-d2ce975df5a4",
    },
    ("storefront / production", "storefront-commerce"): {
        "railway_project_id": RAILWAY_STOREFRONT_PROJECT,
        "railway_environment_id": RAILWAY_STOREFRONT_ENVIRONMENT,
        "service_id": "bffcd9ce-09d8-4cff-948f-8f03c08ba8c0",
    },
}

UNMAPPED_SERVICES = frozenset(
    {
        "dk-tag-printer-backend",
        "dk-tag-printer-frontend",
        "buycycle",
        "environment-monitor-backend",
        "environment-monitor-frontend",
    }
)


def _add(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def tuple_digest(receipt: dict[str, Any]) -> str:
    """Bind an approval id to the fields a later change must invalidate."""
    parts = [
        str(receipt.get("repository") or ""),
        str(receipt.get("sha") or ""),
        str(receipt.get("ci_workflow_path") or ""),
        str(receipt.get("ci_run_id") or ""),
        str(receipt.get("ci_run_attempt") or ""),
        str(receipt.get("artifact_sha256") or ""),
        str(receipt.get("github_environment_name") or ""),
        str(receipt.get("service") or ""),
        str(receipt.get("railway_project_id") or ""),
        str(receipt.get("railway_environment_id") or ""),
        str(receipt.get("service_id") or ""),
        str(receipt.get("deployment_id") or ""),
        str(receipt.get("promotion") or ""),
    ]
    checks = receipt.get("checks") or {}
    for name in TRUSTED_CHECKS:
        item = checks.get(name) or {}
        parts.append(name)
        parts.append(str(item.get("conclusion") or ""))
        parts.append(str(item.get("run_id") or ""))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def evaluate(receipt: dict[str, Any] | None, boundary: dict[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    """Return permit or deny. Neither result performs an effect."""
    data = receipt or {}
    trust = boundary or {}
    reasons: list[str] = []

    if trust.get("kind") != "simulated":
        _add(reasons, "live_receipt_not_fetched")
    if trust.get("receipt_source") != TRUSTED_RECEIPT_SOURCE:
        _add(reasons, "receipt_source_untrusted")
    if trust.get("receipt_credential_is_approver_user") is True:
        _add(reasons, "agent_held_approver_credential")
    if trust.get("receipt_credential_is_agent_held_user_token") is True:
        _add(reasons, "agent_held_approver_credential")
    if data.get("approved") is True and trust.get("kind") != "simulated":
        _add(reasons, "boolean_is_not_approval")
    if data.get("approval_file") or data.get("signature_key_holder") == "agent":
        _add(reasons, "agent_minted_approval")

    approver = data.get("approver_user_id")
    requester = data.get("requester_id")
    if approver != APPROVER_USER_ID:
        _add(reasons, "reviewer_not_required_human")
    if data.get("approver_kind") != "human_user":
        _add(reasons, "approver_not_human_user")
    if data.get("requester_kind") != "github_app":
        _add(reasons, "requester_not_separate_app")
    if requester in {None, "", APPROVER_USER_ID} or requester == approver:
        _add(reasons, "requester_is_approver")
    if data.get("prevent_self_review") is not True:
        _add(reasons, "self_review_not_prevented")
    if data.get("can_admins_bypass") is not False or data.get("admin_bypass_used") is True:
        _add(reasons, "admin_bypass")

    environment = str(data.get("github_environment_name") or "")
    service = str(data.get("service") or "")
    if environment not in GITHUB_ENVIRONMENT_IDS:
        _add(reasons, "environment_not_candidate")
    elif data.get("github_environment_id") != GITHUB_ENVIRONMENT_IDS[environment]:
        _add(reasons, "environment_id_mismatch")
    if service in UNMAPPED_SERVICES or environment == "DasKasas / production":
        _add(reasons, "target_unmapped")
    binding = BINDINGS.get((environment, service))
    if binding is None and "target_unmapped" not in reasons:
        _add(reasons, "target_unmapped")
    if binding is not None:
        for key in ("railway_project_id", "railway_environment_id", "service_id"):
            if data.get(key) != binding[key]:
                _add(reasons, "provider_tuple_mismatch")

    if data.get("repository") != REPOSITORY or data.get("head_repository") != REPOSITORY:
        _add(reasons, "untrusted_repository")
    if data.get("ref") != "refs/heads/main" or data.get("deployment_branch_policy") != "main":
        _add(reasons, "ref_not_main")
    sha = str(data.get("sha") or "")
    if not _SHA.fullmatch(sha) or data.get("built_from_sha") != sha:
        _add(reasons, "sha_not_exact")
    if data.get("ci_workflow_path") != TRUSTED_CI_WORKFLOW:
        _add(reasons, "ci_workflow_untrusted")
    if data.get("event_name") != "workflow_dispatch":
        _add(reasons, "event_untrusted")
    if data.get("fork") is True or data.get("workflow_path") not in {None, TRUSTED_CI_WORKFLOW}:
        _add(reasons, "untrusted_workflow")
    digest = str(data.get("artifact_sha256") or "")
    if not _DIGEST.fullmatch(digest) or data.get("approved_artifact_sha256") != digest:
        _add(reasons, "artifact_mismatch")
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    run_id = data.get("ci_run_id")
    attempt = data.get("ci_run_attempt")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or not isinstance(attempt, int) or isinstance(attempt, bool):
        _add(reasons, "ci_run_not_exact")
    for name in TRUSTED_CHECKS:
        item = checks.get(name) if isinstance(checks.get(name), dict) else {}
        if item.get("conclusion") != "success" or item.get("run_id") != run_id or item.get("attempt") != attempt:
            _add(reasons, "check_not_success")
    if data.get("promotion") != "railway_existing_deployment_reuse":
        _add(reasons, "promotion_not_same_build_reuse")
    if data.get("promotion") == "oci_digest":
        _add(reasons, "oci_digest_receipt_unverified")
    deployment_id = str(data.get("deployment_id") or "")
    if not deployment_id or data.get("approved_deployment_id") != deployment_id:
        _add(reasons, "deployment_id_mismatch")
    if data.get("rebuild") is True or data.get("tag") in {"latest", "main"} or data.get("ref_kind") == "tag":
        _add(reasons, "rebuild_or_mutable_tag")

    expires = _parse_time(data.get("expires_at"))
    moment = now.astimezone(timezone.utc)
    if expires is None or expires <= moment:
        _add(reasons, "approval_expired")
    approval_id = str(data.get("approval_id") or "")
    if not approval_id:
        _add(reasons, "approval_id_missing")
    consumed = trust.get("consumed_approval_ids") or ()
    if approval_id and approval_id in consumed:
        _add(reasons, "approval_replayed")
    if approval_id and data.get("approval_tuple") != tuple_digest(data):
        _add(reasons, "approval_tuple_mismatch")

    permit = not reasons
    return {
        "permit": permit,
        "reasons": reasons,
        "effects_enabled": EFFECTS_ENABLED,
        "live_human_approval_proved": False,
        "provider_digest_proved": False,
    }


def execute(decision: dict[str, Any], sink: Any | None = None) -> dict[str, Any]:
    """Record no provider call. The sink is accepted so tests can prove it stays unused."""
    del sink
    if EFFECTS_ENABLED:
        raise RuntimeError("live promotion is not part of this harness")
    return {
        "executed": False,
        "reason": "live_promotion_disabled",
        "permit": bool(decision.get("permit")),
    }
