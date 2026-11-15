#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["keyring==25.6.0"]
# ///
"""Post one strict Buycycle release-request comment using its separate narrow App.

This helper cannot dispatch workflows, approve, merge, push, publish or deploy.
Private keys use the existing explicit macOS Keychain/JWT/session boundary.
Ambiguous writes are never retried or edited automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import f0rge_pr_publisher as auth

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy"))
from buycycle_release import (
    REQUEST_PERMISSIONS,
    ReleaseError,
    validate_ci_run,
    validate_request_body,
)

store_key = auth.store_key  # Registration callback only; never key bytes in argv.


@dataclass(frozen=True)
class Config:
    app: auth.Config
    request_pr_number: int

    def __post_init__(self):
        auth.require(
            type(self.request_pr_number) is int and self.request_pr_number > 0,
            "Invalid fixed release PR",
        )


def read_config(path: Path) -> Config:
    value = auth._read_private_config(path)
    auth.require(
        set(value)
        == {"app_id", "slug", "installation_id", "repo_id", "request_pr_number"},
        "Unexpected requester config fields",
    )
    number = value.pop("request_pr_number")
    return Config(auth.Config(**value), number)


class RequesterGitHub(auth.GitHub):
    def __init__(self, number: int):
        auth.require(type(number) is int and number > 0, "Invalid fixed release PR")
        self.number = number
        super().__init__()

    def request(self, method, path, token, body=None):
        base = "/repos/F0rge/f0rge"
        reads = (
            r"/app",
            r"/app/installations/[1-9][0-9]*",
            r"/installation/repositories\?per_page=100",
            r"/users/[a-z0-9-]+%5Bbot%5D",
            re.escape(base),
            re.escape(base + f"/pulls/{self.number}"),
            re.escape(base + f"/issues/{self.number}/comments")
            + r"\?per_page=100&page=[1-9][0-9]?",
            re.escape(base) + r"/issues/comments/[1-9][0-9]*",
            re.escape(base) + r"/actions/runs/[1-9][0-9]*",
        )
        allowed = (
            method == "GET"
            and any(re.fullmatch(pattern, path) for pattern in reads)
            or method == "POST"
            and (
                re.fullmatch(r"/app/installations/[1-9][0-9]*/access_tokens", path)
                or path == base + f"/issues/{self.number}/comments"
            )
            or method == "DELETE"
            and path == "/installation/token"
        )
        auth.require(
            allowed, "API operation is outside the fixed comment-request scope"
        )
        return self._request(method, path, token, body)


def inspect(config: Config) -> dict:
    with auth._verified_session(
        config.app, RequesterGitHub(config.request_pr_number), REQUEST_PERMISSIONS
    ) as (_api, _token, facts):
        return dict(facts, request_pr_number=config.request_pr_number)


def post_request(config: Config, body: str) -> dict:
    request = validate_request_body(body)
    # Canonical public body has only schema-checked code identities and hashes.
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
    base = "/repos/F0rge/f0rge"
    number = config.request_pr_number
    with auth._verified_session(
        config.app, RequesterGitHub(number), REQUEST_PERMISSIONS
    ) as (api, token, facts):
        pull = api.request("GET", base + f"/pulls/{number}", token)
        auth.require(
            pull.get("number") == number
            and pull.get("merged") is True
            and pull.get("base", {}).get("ref") == "main"
            and pull.get("base", {}).get("repo", {}).get("id") == auth.REPO_ID,
            "Release PR must be the configured reviewed, merged main PR",
        )
        validate_ci_run(
            api.request("GET", base + f"/actions/runs/{request['ci_run_id']}", token),
            request["source_commit"],
        )
        for page in range(1, 11):
            comments = api.request(
                "GET",
                base + f"/issues/{number}/comments?per_page=100&page={page}",
                token,
            )
            auth.require(
                isinstance(comments, list) and len(comments) <= 100,
                "Unexpected comment pagination",
            )
            for comment in comments:
                if comment.get("user", {}).get("id") == facts["bot_id"]:
                    try:
                        previous = validate_request_body(comment.get("body"))
                    except (ReleaseError, ValueError, TypeError):
                        continue
                    auth.require(
                        previous["request_id"] != request["request_id"],
                        "Request nonce already posted; inspect existing state",
                    )
            if len(comments) < 100:
                break
        else:
            raise auth.PublisherError("Comment inventory exceeds the verified bound")
        created = api.request(
            "POST", base + f"/issues/{number}/comments", token, {"body": canonical}
        )
        identifier = created.get("id")
        auth.require(
            type(identifier) is int and identifier > 0,
            "Comment write outcome unclear; inspect before retrying",
        )
        actual = api.request("GET", base + f"/issues/comments/{identifier}", token)
        auth.require(
            actual.get("id") == identifier
            and actual.get("body") == canonical
            and actual.get("issue_url")
            == f"https://api.github.com/repos/F0rge/f0rge/issues/{number}"
            and actual.get("user", {}).get("id") == facts["bot_id"]
            and (actual.get("performed_via_github_app") or {}).get("id")
            == config.app.app_id
            and (actual.get("performed_via_github_app") or {}).get("slug")
            == config.app.slug,
            "Authoritative posted-comment identity differs; inspect before retrying",
        )
        return {
            "comment_id": identifier,
            "body_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "request_id": request["request_id"],
            "request_pr_number": number,
            "app_id": config.app.app_id,
            "bot_id": facts["bot_id"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("--config", type=Path, required=True)
    post_parser = commands.add_parser("post-request")
    post_parser.add_argument("--config", type=Path, required=True)
    post_parser.add_argument("--request-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = read_config(args.config)
        if args.command == "inspect":
            result = inspect(config)
        else:
            auth.require(
                args.request_file.is_file()
                and not args.request_file.is_symlink()
                and args.request_file.stat().st_size <= 4096,
                "Request file is missing or unsafe",
            )
            result = post_request(config, args.request_file.read_text())
        print(json.dumps(result, sort_keys=True))
        return 0
    except (
        auth.PublisherError,
        ReleaseError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
    ):
        print(
            "Buycycle request refused or write outcome unclear; inspect state before retrying. No fallback identity is used.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
