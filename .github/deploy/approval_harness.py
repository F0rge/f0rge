"""No-effect check of a release tuple.

A permit is possible only for a SimulatedBoundary plus a MemoryReplayStore.
Those are test doubles. A dict, a JSON file, or a source-string cannot
become one. This module does not call GitHub or Railway.

execute() can name a planned reuse and still performs no provider call
while EFFECTS_ENABLED is false. A permit does not prove a person acted
and does not prove a running image digest.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

APPROVER_USER_ID = 38779415
REPOSITORY = "F0rge/f0rge"
TRUSTED_CI_WORKFLOW = ".github/workflows/ci.yml"
TRUSTED_CHECKS = ("ci", "playwright smoke")
EFFECTS_ENABLED = False

# GitHub environment reviews have no caller-chosen lifetime. This harness
# accepts a review only at evaluation time, inside a short clock window.
MAX_REVIEW_AGE = timedelta(minutes=15)
MAX_FUTURE_SKEW = timedelta(minutes=2)

GITHUB_ENVIRONMENT_IDS = {
    "Marrow / production": 19158860710,
    "Firstout / production": 24561991680,
    "storefront / production": 23387956905,
    "DasKasas / production": 24635670941,
}

RAILWAY_STOREFRONT_PROJECT = "d58a2884-d366-4230-9555-8b7bb4e42d4f"
RAILWAY_STOREFRONT_ENVIRONMENT = "d73ff2d5-816d-4bc8-85b4-71a85b0398fa"

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

RECEIPT_FIELDS = frozenset(
    {
        "repository",
        "head_repository",
        "ref",
        "deployment_branch_policy",
        "sha",
        "built_from_sha",
        "ci_workflow_path",
        "workflow_path",
        "event_name",
        "fork",
        "ci_run_id",
        "ci_run_attempt",
        "checks",
        "artifact_sha256",
        "approved_artifact_sha256",
        "github_environment_name",
        "github_environment_id",
        "service",
        "railway_project_id",
        "railway_environment_id",
        "service_id",
        "deployment_id",
        "approved_deployment_id",
        "promotion",
        "approver_user_id",
        "requester_id",
        "prevent_self_review",
        "can_admins_bypass",
        "admin_bypass_used",
        "rebuild",
        "ref_kind",
        "reviewed_at",
        "expires_at",
        "approval_id",
        "approval_tuple",
    }
)


class SimulatedBoundary:
    """Test double. Not a GitHub response and not a trust root."""


class MemoryReplayStore:
    """Fixture replay memory keyed by the canonical tuple digest.

    A new approval_id for the same tuple is still a replay. This object is
    process-local and is not a durable live replay proof.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def seen(self, tuple_identity: str) -> bool:
        return tuple_identity in self._seen

    def commit(self, tuple_identity: str) -> None:
        self._seen.add(tuple_identity)


class BoundCommand:
    """Immutable plan produced only by evaluate. Not a provider call."""

    __slots__ = (
        "repository",
        "sha",
        "artifact_sha256",
        "deployment_id",
        "railway_project_id",
        "railway_environment_id",
        "service",
        "service_id",
        "ci_run_id",
        "ci_run_attempt",
        "approval_tuple",
        "_token",
    )

    def __init__(self, token: object, **fields: object) -> None:
        if token is not _PLAN_TOKEN:
            raise RuntimeError("bound commands are minted only by evaluate")
        for name, value in fields.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_token", token)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("bound command is immutable")

    def as_dict(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__slots__ if name != "_token"}


_PLAN_TOKEN = object()


def _add(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _exact_int(value: object) -> int | None:
    if type(value) is int:
        return value
    return None


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


def _canon(value: object) -> str:
    if type(value) is int:
        return f"int:{value}"
    if type(value) is str:
        return f"str:{value}"
    if type(value) is bool:
        return f"bool:{value}"
    return f"other:{type(value).__name__}"


def tuple_digest(receipt: dict[str, Any]) -> str:
    """Canonical binding. Identity, time, environment id, and check attempt are included."""
    checks = receipt.get("checks") if isinstance(receipt.get("checks"), dict) else {}
    parts = [
        _canon(receipt.get("repository")),
        _canon(receipt.get("head_repository")),
        _canon(receipt.get("sha")),
        _canon(receipt.get("built_from_sha")),
        _canon(receipt.get("ci_workflow_path")),
        _canon(receipt.get("workflow_path")),
        _canon(receipt.get("event_name")),
        _canon(receipt.get("fork")),
        _canon(receipt.get("ci_run_id")),
        _canon(receipt.get("ci_run_attempt")),
        _canon(receipt.get("artifact_sha256")),
        _canon(receipt.get("approved_artifact_sha256")),
        _canon(receipt.get("github_environment_name")),
        _canon(receipt.get("github_environment_id")),
        _canon(receipt.get("service")),
        _canon(receipt.get("railway_project_id")),
        _canon(receipt.get("railway_environment_id")),
        _canon(receipt.get("service_id")),
        _canon(receipt.get("deployment_id")),
        _canon(receipt.get("approved_deployment_id")),
        _canon(receipt.get("promotion")),
        _canon(receipt.get("approver_user_id")),
        _canon(receipt.get("requester_id")),
        _canon(receipt.get("prevent_self_review")),
        _canon(receipt.get("can_admins_bypass")),
        _canon(receipt.get("admin_bypass_used")),
        _canon(receipt.get("reviewed_at")),
        _canon(receipt.get("expires_at")),
        _canon(receipt.get("ref")),
        _canon(receipt.get("deployment_branch_policy")),
    ]
    for name in TRUSTED_CHECKS:
        item = checks.get(name) if isinstance(checks.get(name), dict) else {}
        parts.append(f"check:{name}")
        parts.append(_canon(item.get("conclusion")))
        parts.append(_canon(item.get("run_id")))
        parts.append(_canon(item.get("attempt")))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def evaluate(
    receipt: dict[str, Any] | None,
    boundary: object,
    store: object,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Return permit or deny. A permit also consumes the approval id in the store."""
    data = receipt or {}
    reasons: list[str] = []
    if type(boundary) is not SimulatedBoundary:
        _add(reasons, "live_receipt_not_fetched")
    if type(store) is not MemoryReplayStore:
        _add(reasons, "replay_store_untrusted")
    if not isinstance(data, dict):
        _add(reasons, "receipt_not_object")
        data = {}
    unknown = sorted(set(data) - RECEIPT_FIELDS)
    if unknown or "consumed_approval_ids" in data or "receipt_source" in data or "approved" in data:
        _add(reasons, "unexpected_field")

    approver = _exact_int(data.get("approver_user_id"))
    requester = _exact_int(data.get("requester_id"))
    if approver is None or requester is None or _exact_int(data.get("github_environment_id")) is None:
        _add(reasons, "id_type_invalid")
    if _exact_int(data.get("ci_run_id")) is None or _exact_int(data.get("ci_run_attempt")) is None:
        _add(reasons, "id_type_invalid")
    if approver != APPROVER_USER_ID:
        _add(reasons, "reviewer_not_required_human")
    if requester is None or requester == APPROVER_USER_ID or requester == approver:
        _add(reasons, "requester_is_approver")
    if data.get("prevent_self_review") is not True:
        _add(reasons, "self_review_not_prevented")
    if data.get("can_admins_bypass") is not False or data.get("admin_bypass_used") is True:
        _add(reasons, "admin_bypass")

    environment = data.get("github_environment_name")
    service = data.get("service")
    if not isinstance(environment, str) or environment not in GITHUB_ENVIRONMENT_IDS:
        _add(reasons, "environment_not_candidate")
    elif data.get("github_environment_id") != GITHUB_ENVIRONMENT_IDS.get(environment):
        _add(reasons, "environment_id_mismatch")
    if not isinstance(service, str) or service in UNMAPPED_SERVICES or environment == "DasKasas / production":
        _add(reasons, "target_unmapped")
    binding = BINDINGS.get((environment, service)) if isinstance(environment, str) and isinstance(service, str) else None
    if binding is None and "target_unmapped" not in reasons and "environment_not_candidate" not in reasons:
        _add(reasons, "target_unmapped")
    if binding is not None:
        for key in ("railway_project_id", "railway_environment_id", "service_id"):
            if data.get(key) != binding[key]:
                _add(reasons, "provider_tuple_mismatch")

    if data.get("repository") != REPOSITORY or data.get("head_repository") != REPOSITORY:
        _add(reasons, "untrusted_repository")
    if data.get("ref") != "refs/heads/main" or data.get("deployment_branch_policy") != "main":
        _add(reasons, "ref_not_main")
    sha = data.get("sha")
    if not isinstance(sha, str) or len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        _add(reasons, "sha_not_exact")
    elif data.get("built_from_sha") != sha:
        _add(reasons, "sha_not_exact")
    if data.get("ci_workflow_path") != TRUSTED_CI_WORKFLOW:
        _add(reasons, "ci_workflow_untrusted")
    if data.get("workflow_path") is None:
        _add(reasons, "workflow_path_missing")
    elif data.get("workflow_path") != TRUSTED_CI_WORKFLOW:
        _add(reasons, "untrusted_workflow")
    if data.get("event_name") != "workflow_dispatch":
        _add(reasons, "event_untrusted")
    if data.get("fork") is not False:
        _add(reasons, "untrusted_workflow")
    digest = data.get("artifact_sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 71
        or not digest.startswith("sha256:")
        or any(c not in "0123456789abcdef" for c in digest[7:])
        or data.get("approved_artifact_sha256") != digest
    ):
        _add(reasons, "artifact_mismatch")

    run_id = _exact_int(data.get("ci_run_id"))
    attempt = _exact_int(data.get("ci_run_attempt"))
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else None
    if checks is None or set(checks) != set(TRUSTED_CHECKS):
        _add(reasons, "check_not_success")
    else:
        for name in TRUSTED_CHECKS:
            item = checks.get(name)
            if not isinstance(item, dict):
                _add(reasons, "check_not_success")
                continue
            if set(item) != {"conclusion", "run_id", "attempt"}:
                _add(reasons, "check_not_success")
                continue
            if (
                item.get("conclusion") != "success"
                or item.get("run_id") != run_id
                or item.get("attempt") != attempt
            ):
                _add(reasons, "check_not_success")
    if data.get("promotion") == "oci_digest":
        _add(reasons, "oci_digest_receipt_unverified")
    elif data.get("promotion") != "railway_existing_deployment_reuse":
        _add(reasons, "promotion_not_same_build_reuse")
    deployment_id = data.get("deployment_id")
    if not isinstance(deployment_id, str) or not deployment_id or data.get("approved_deployment_id") != deployment_id:
        _add(reasons, "deployment_id_mismatch")
    if data.get("rebuild") is not False or data.get("ref_kind") != "sha":
        _add(reasons, "rebuild_or_mutable_tag")

    reviewed = _parse_time(data.get("reviewed_at"))
    expires = _parse_time(data.get("expires_at"))
    moment = now.astimezone(timezone.utc)
    if reviewed is None or expires is None:
        _add(reasons, "review_time_invalid")
    else:
        if expires <= reviewed or expires - reviewed > MAX_REVIEW_AGE:
            _add(reasons, "expiry_window_too_long")
        if moment < reviewed - MAX_FUTURE_SKEW or moment > expires:
            _add(reasons, "approval_expired")

    approval_id = data.get("approval_id")
    if not isinstance(approval_id, str) or not approval_id:
        _add(reasons, "approval_id_missing")
        approval_id = ""
    if data.get("approval_tuple") != tuple_digest(data):
        _add(reasons, "approval_tuple_mismatch")
    identity = data.get("approval_tuple")
    if (
        isinstance(store, MemoryReplayStore)
        and isinstance(identity, str)
        and identity
        and store.seen(identity)
    ):
        _add(reasons, "approval_replayed")

    permit = not reasons
    bound = None
    if permit and isinstance(store, MemoryReplayStore) and isinstance(identity, str):
        store.commit(identity)
        bound = BoundCommand(
            _PLAN_TOKEN,
            repository=data.get("repository"),
            sha=data.get("sha"),
            artifact_sha256=data.get("artifact_sha256"),
            deployment_id=data.get("deployment_id"),
            railway_project_id=data.get("railway_project_id"),
            railway_environment_id=data.get("railway_environment_id"),
            service=data.get("service"),
            service_id=data.get("service_id"),
            ci_run_id=data.get("ci_run_id"),
            ci_run_attempt=data.get("ci_run_attempt"),
            approval_tuple=identity,
        )
    return {
        "permit": permit,
        "reasons": reasons,
        "bound": bound,
        "effects_enabled": EFFECTS_ENABLED,
        "live_human_approval_proved": False,
        "provider_digest_proved": False,
        "replay_store_durable": False,
    }


def plan_effects(decision: object) -> BoundCommand | None:
    """Return the immutable command evaluate minted, or nothing.

    A bare {"permit": true} is not a plan. This does not call a provider.
    """
    if not isinstance(decision, dict):
        return None
    bound = decision.get("bound")
    if type(bound) is not BoundCommand:
        return None
    if decision.get("permit") is not True:
        return None
    return bound


def execute(decision: dict[str, Any], sink: Any) -> dict[str, Any]:
    """Call the sink only when the hard switch is on. That switch is off."""
    planned = plan_effects(decision)
    executed = False
    if EFFECTS_ENABLED and planned is not None:
        sink.deploy(planned)
        executed = True
    return {
        "executed": executed,
        "planned": None if planned is None else planned.as_dict(),
        "permit": isinstance(decision, dict) and decision.get("permit") is True,
        "reason": None if executed else "live_promotion_disabled",
    }
