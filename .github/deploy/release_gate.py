"""Fail-closed release decision.

A merge, tag, green CI run, manual dispatch, rerun, or pull-request sentence
cannot authorize a rollout. This module has no allow outcome. An external
approval that binds a person, a target, a commit, and an immutable digest is
not configured in this repository, and no file here can stand in for it.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

DECISION = "deny"
BINDING = "external_approval_binding_not_configured"

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")

# Names only. Listing a target does not authorize deploying it.
KNOWN_TARGETS = frozenset(
    {
        "marrow-api",
        "marrow-frontend",
        "marrow-mcp",
        "firstout-api",
        "firstout-frontend",
        "dk-tag-printer-backend",
        "dk-tag-printer-frontend",
        "buycycle",
        "environment-monitor-backend",
        "environment-monitor-frontend",
    }
)


def decide(evidence: dict[str, Any] | None) -> dict[str, Any]:
    """Return a denial. The binding reason is always present."""
    data = evidence or {}
    reasons: list[str] = []

    def add(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    event = str(data.get("event_name") or "")
    if event in {"pull_request", "pull_request_target", "workflow_run", "schedule", "push"}:
        add("event_cannot_authorize")
    if event in {"workflow_dispatch", "workflow_dispatch_rerun"} or data.get("rerun") is True:
        add("manual_or_rerun_cannot_authorize")
    if data.get("ref_kind") in {"branch", "tag"} or data.get("mutable_tag") is True:
        add("mutable_ref")

    sha = str(data.get("sha") or "")
    ci_sha = str(data.get("ci_head_sha") or "")
    if not _SHA.fullmatch(sha):
        add("sha_not_exact")
    if ci_sha and sha and sha != ci_sha:
        add("sha_mismatch")

    digest = str(data.get("digest") or "")
    ci_digest = str(data.get("ci_artifact_digest") or "")
    if not _DIGEST.fullmatch(digest):
        add("digest_not_exact")
    if ci_digest and digest and digest != ci_digest:
        add("digest_mismatch")
    if data.get("artifact_changed_after_ci") is True:
        add("artifact_invalidated")
    if data.get("rebuild") is True:
        add("rebuild_not_promotion")

    target = str(data.get("target") or "")
    approved_target = str(data.get("approved_target") or "")
    if target not in KNOWN_TARGETS:
        add("target_unknown")
    if approved_target and target and approved_target != target:
        add("target_mismatch")

    conclusion = str(data.get("ci_conclusion") or "")
    if conclusion != "success":
        add("ci_not_success")
    ci_event = str(data.get("ci_event") or "")
    if ci_event != "push":
        add("ci_event_not_trusted")
    if str(data.get("ci_head_branch") or "") not in {"", "main"}:
        add("ci_branch_not_main")
    if data.get("ci_head_branch") in {"", None} and ci_event == "push":
        add("ci_branch_missing")
    workflow = str(data.get("ci_workflow_path") or "")
    if workflow not in {"", ".github/workflows/ci.yml"}:
        add("ci_workflow_untrusted")
    if ci_event == "push" and not workflow:
        add("ci_workflow_missing")

    if data.get("pr_body") or data.get("approval_text"):
        add("pr_text_cannot_approve")
    if data.get("approval_file") is True:
        add("repo_file_cannot_approve")
    if data.get("allow") is True or data.get("approved") is True:
        add("self_approval_rejected")
    if str(data.get("actor") or "") == "" or data.get("untrusted_actor") is True:
        add("actor_untrusted")

    add(BINDING)
    if DECISION != "deny" or BINDING not in reasons:
        raise RuntimeError("release gate lost its fail-closed outcome")
    return {"decision": DECISION, "reasons": reasons}


def main() -> int:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    evidence = json.loads(raw) if raw.strip() else {}
    json.dump(decide(evidence), sys.stdout)
    sys.stdout.write("\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
