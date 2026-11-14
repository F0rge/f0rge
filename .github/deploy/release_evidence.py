"""Offline consistency checks; input values are not trusted release evidence.

These helpers perform no provider calls, approval checks, replay protection or
deployment. They must not be used as a production authorization decision.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REQUIRED_CHECKS = frozenset({"ci", "playwright smoke"})
_TARGET_FIELDS = (
    "repository",
    "commit",
    "service",
    "destination",
    "architecture",
    "digest",
)


def compare_evidence(
    candidate: Mapping[str, Any],
    artifact: Mapping[str, Any],
    checks: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Report inconsistencies, never make an approval or deployment decision."""
    errors: list[str] = []
    if candidate.get("repository") != "F0rge/f0rge":
        errors.append("repository")
    commit = candidate.get("commit")
    if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
        errors.append("commit")
    digest = candidate.get("digest")
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        errors.append("digest")
    for field in ("service", "destination", "architecture"):
        if not isinstance(candidate.get(field), str) or not candidate[field].strip():
            errors.append(field)
    for field in _TARGET_FIELDS:
        if artifact.get(field) != candidate.get(field):
            errors.append(f"artifact_{field}")
    if artifact.get("tested") is not True:
        errors.append("artifact_not_tested")
    if artifact.get("rebuilt") is not False:
        errors.append("artifact_rebuilt")

    by_name: dict[str, Mapping[str, Any]] = {}
    for check in checks:
        name = check.get("name")
        if not isinstance(name, str) or name not in _REQUIRED_CHECKS or name in by_name:
            errors.append("unexpected_or_duplicate_check")
            continue
        by_name[name] = check
    for name in sorted(_REQUIRED_CHECKS):
        check = by_name.get(name)
        if check is None:
            errors.append(f"missing_{name}")
            continue
        if (
            check.get("repository") != candidate.get("repository")
            or check.get("commit") != commit
        ):
            errors.append(f"check_identity_{name}")
        if check.get("status") != "completed" or check.get("conclusion") != "success":
            errors.append(f"check_not_success_{name}")
        if any(
            type(check.get(key)) is not int or check[key] < 1
            for key in ("run_id", "attempt")
        ):
            errors.append(f"check_run_{name}")
    return errors
