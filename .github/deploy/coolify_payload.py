#!/usr/bin/env python3
"""GitHub push body for Coolify's manual webhook.

Coolify (v4.0.0-beta.473 manual handler) flattens ``commits.*.added``,
``commits.*.modified`` and ``commits.*.removed`` into the changed-file list
it matches against watch paths. An empty ``commits`` array passes the HMAC
check and then answers 200 with changed_files=[].
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

REPO_FULL_NAME = "F0rge/f0rge"
REPO_NAME = "f0rge"

# Globs configured on each Coolify app. The payload lists every path from
# git diff; Coolify deploys only when a path matches that app's watch paths.
# Keys are manifest component names.
COOLIFY_WATCH_PATHS: dict[str, tuple[str, ...]] = {
    "dk-tag-printer-backend": ("apps/dk/tag-printer/backend/**",),
    "dk-tag-printer-frontend": ("apps/dk/tag-printer/frontend/**",),
    "buycycle": ("apps/buycycle/**",),
    "environment-monitor-backend": ("apps/environment-monitor/backend/**",),
    "environment-monitor-frontend": ("apps/environment-monitor/frontend/**",),
}


def coolify_diff_base(nx_base: str, nx_head: str, nx_parent: str) -> str:
    """SHA ``plan_deploy`` diffs Coolify projects against.

    nx-set-shas often sets NX_BASE == NX_HEAD on the deploy run (CI just
    passed that SHA). Coolify selection then falls back to the parent commit.
    """
    if nx_base == nx_head and nx_parent:
        return nx_parent
    return nx_base


def parse_name_status_z(raw: bytes) -> dict[str, list[str]]:
    """Split ``git diff -z --name-status`` into added / modified / removed.

    Renames count as removed (old path) and added (new path) so a move into
    a watch path still matches. Copies count as added (the new path).
    """
    added: list[str] = []
    modified: list[str] = []
    removed: list[str] = []
    parts = raw.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    index = 0
    while index < len(parts):
        status = parts[index].decode()
        code = status[:1]
        if code in {"R", "C"}:
            if index + 2 >= len(parts):
                raise ValueError(f"truncated rename/copy record: {status!r}")
            old = parts[index + 1].decode()
            new = parts[index + 2].decode()
            index += 3
            if code == "R":
                removed.append(old)
                added.append(new)
            else:
                added.append(new)
            continue
        if index + 1 >= len(parts):
            raise ValueError(f"truncated name-status record: {status!r}")
        path = parts[index + 1].decode()
        index += 2
        if code == "A":
            added.append(path)
        elif code == "D":
            removed.append(path)
        elif code in {"M", "T"}:
            modified.append(path)
        else:
            raise ValueError(f"unrecognized name-status {status!r} for {path}")
    return {"added": added, "modified": modified, "removed": removed}


def diff_name_status(repo: str, base: str, head: str) -> dict[str, list[str]]:
    """Net path change between two commits (``git diff -z --name-status``)."""
    if not base or not head:
        raise ValueError("diff base and head are required")
    try:
        raw = subprocess.check_output(
            ["git", "diff", "-z", "--name-status", base, head],
            cwd=repo,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode(errors="replace").strip()
        raise RuntimeError(f"git diff --name-status {base} {head} failed: {detail}") from exc
    return parse_name_status_z(raw)


def build_push_payload(
    sha: str,
    branch: str,
    added: list[str],
    modified: list[str],
    removed: list[str],
) -> dict[str, Any]:
    """One synthetic commit covering the whole base..sha diff.

    ``commits`` is always present. Omitting the key makes this Coolify 500
    before it checks the signature.
    """
    return {
        "ref": f"refs/heads/{branch}",
        "after": sha,
        "commits": [
            {
                "id": sha,
                "added": added,
                "modified": modified,
                "removed": removed,
            }
        ],
        "repository": {"full_name": REPO_FULL_NAME, "name": REPO_NAME},
    }


def payload_json(payload: dict[str, Any]) -> str:
    """Compact JSON, raw UTF-8 paths (Coolify matches the decoded strings)."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _walk_objects(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        found.append(node)
        for value in node.values():
            found.extend(_walk_objects(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk_objects(item))
    return found


def _app_id(obj: dict[str, Any]) -> str:
    for key in ("uuid", "id", "application_id", "application_uuid"):
        value = obj.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


# Coolify's manual handler returns this sentence, verbatim, when the push
# changed files miss the app's watch paths. Match the whole message only.
WATCH_PATH_IGNORE_MESSAGE = "Changed files do not match watch paths. Ignoring deployment."


def response_queues_app(body: str, app_uuid: str) -> bool:
    """True when this Coolify app was actually queued.

    The manual push handler reports a queued deploy as ``status: success``
    and ``message: Deployment queued.`` (v4.0.0-beta.473). ``status: queued``
    on this same app counts too. The watch-path ignore sentence is not a
    queue (see ``classify_coolify_response``). An ``Invalid signature`` on
    this app is not a queue. Sibling apps are separate objects (often with
    no uuid) and their ``Invalid signature`` entries are ignored.
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False
    if isinstance(data, dict) and data.get("status") == "queued":
        return True
    for obj in _walk_objects(data):
        if _app_id(obj) != app_uuid:
            continue
        status = obj.get("status")
        message = obj.get("message") if isinstance(obj.get("message"), str) else ""
        if status == "queued":
            return True
        if status == "success" and "deployment queued" in message.lower():
            return True
    return False


def response_watch_path_ignored(body: str, app_uuid: str) -> bool:
    """True when this app's message is exactly the watch-path ignore sentence.

    Equality is case-sensitive and covers the whole message. A shorter
    string such as ``Ignoring`` does not match, and a sibling app's copy
    of the sentence does not count.
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False
    for obj in _walk_objects(data):
        if _app_id(obj) != app_uuid:
            continue
        if obj.get("message") == WATCH_PATH_IGNORE_MESSAGE:
            return True
    return False


def classify_coolify_response(http_status: int, body: str, app_uuid: str) -> str:
    """Classify one Coolify manual-webhook reply for this app.

    Returns ``success`` when the app was queued, ``skipped`` when the HTTP
    status is 2xx and this app's message equals ``WATCH_PATH_IGNORE_MESSAGE``,
    and ``failed`` otherwise. Non-2xx is ``failed`` even if the body contains
    that sentence. Any other 2xx that did not queue a deployment (no queued
    status, no deployment uuid, different message) is ``failed``.
    """
    if http_status < 200 or http_status >= 300:
        return "failed"
    if response_queues_app(body, app_uuid):
        return "success"
    if response_watch_path_ignored(body, app_uuid):
        return "skipped"
    return "failed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or check a Coolify GitHub push payload")
    parser.add_argument("--sha", help="Deployed commit (payload after / commits[0].id)")
    parser.add_argument("--base", help="Diff base (plan_deploy coolify_diff_base)")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--require-queued",
        action="store_true",
        help="Read a Coolify response on stdin and exit 0 only if --app-uuid was queued",
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Print success, skipped, or failed for the Coolify response on stdin",
    )
    parser.add_argument("--http-status", type=int)
    parser.add_argument("--app-uuid", default="")
    args = parser.parse_args(argv)
    if args.classify:
        if args.http_status is None or not args.app_uuid:
            parser.error("--classify requires --http-status and --app-uuid")
        body = sys.stdin.read()
        outcome = classify_coolify_response(args.http_status, body, args.app_uuid)
        sys.stdout.write(outcome + "\n")
        return 0 if outcome in {"success", "skipped"} else 1
    if args.require_queued:
        body = sys.stdin.read()
        return 0 if response_queues_app(body, args.app_uuid) else 1
    if not args.sha or not args.base:
        parser.error("--sha and --base are required")
    files = diff_name_status(args.repo, args.base, args.sha)
    payload = build_push_payload(
        args.sha,
        args.branch,
        files["added"],
        files["modified"],
        files["removed"],
    )
    sys.stderr.write(
        "coolify payload files:"
        f" added={len(files['added'])}"
        f" modified={len(files['modified'])}"
        f" removed={len(files['removed'])}\n"
    )
    sys.stdout.write(payload_json(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
