#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["keyring==25.6.0"]
# ///
"""Inspect a narrow GitHub App or publish an existing codex/* branch as a PR.

No push, merge, approval, settings change or deployment is exposed. The App key
stays in macOS Keychain; short-lived JWTs/tokens are never printed or persisted.
GitHub's create-PR API has no atomic expected-head parameter: check immediately
before creation, validate the result, and report ambiguous writes for inspection.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import importlib.metadata
import json
import os
import re
import ssl
import stat
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from keyring.errors import KeyringError

SERVICE = "org.f0rge.codex-pr-publisher"
REPOSITORY = "F0rge/f0rge"
REPO_ID = 1194719185
PERMISSIONS = {"contents": "read", "pull_requests": "write", "metadata": "read"}
API = "https://api.github.com"
SHA = re.compile(r"[0-9a-f]{40}\Z")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
BRANCH = re.compile(r"codex/[a-z0-9][a-z0-9._-]{0,180}\Z")


class PublisherError(RuntimeError):
    """Only fixed, credential-free operator messages belong in this exception."""


def require(condition: object, message: str) -> None:
    if not condition:
        raise PublisherError(message)


@dataclass(frozen=True)
class Config:
    app_id: int
    slug: str
    installation_id: int
    repo_id: int

    def __post_init__(self):
        require(type(self.app_id) is int and self.app_id > 0, "Invalid App ID")
        require(
            type(self.installation_id) is int and self.installation_id > 0,
            "Invalid installation ID",
        )
        require(
            type(self.repo_id) is int and self.repo_id == REPO_ID, "Wrong repository ID"
        )
        require(
            isinstance(self.slug, str)
            and len(self.slug) <= 100
            and SLUG.fullmatch(self.slug),
            "Invalid App slug",
        )


def read_config(path: Path) -> Config:
    require(
        path.is_absolute() and path == path.resolve(),
        "Use a canonical private config path",
    )
    info = path.stat()
    require(
        stat.S_ISREG(info.st_mode)
        and info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == 0o600,
        "Config must be a user-owned mode-0600 file",
    )
    for parent in path.parents:
        metadata = parent.stat()
        sticky_root = metadata.st_uid == 0 and metadata.st_mode & stat.S_ISVTX
        require(
            metadata.st_uid in (0, os.getuid())
            and (not metadata.st_mode & 0o022 or sticky_root),
            "Unsafe config parent directory",
        )
    require(info.st_size <= 4096, "Config is too large")
    value = json.loads(path.read_text())
    require(
        isinstance(value, dict)
        and set(value) == {"app_id", "slug", "installation_id", "repo_id"},
        "Unexpected config fields",
    )
    return Config(**value)


def _mac_keyring():
    require(sys.platform == "darwin", "The publisher requires macOS Keychain")
    try:
        require(
            importlib.metadata.version("keyring") == "25.6.0",
            "Use pinned keyring 25.6.0",
        )
        from keyring.backends.macOS import Keyring

        backend = Keyring()
        backend.keychain = None  # No KEYCHAIN_PATH or generic backend selection.
        return backend
    except PublisherError:
        raise
    except (ImportError, RuntimeError, KeyringError):
        raise PublisherError(
            "The pinned macOS Keychain backend is unavailable"
        ) from None


def _validate_key(secret: str) -> None:
    require(
        isinstance(secret, str) and 128 <= len(secret.encode()) <= 8192,
        "Invalid App key",
    )
    require(
        re.fullmatch(
            r"-----BEGIN (RSA PRIVATE KEY|PRIVATE KEY)-----\n[A-Za-z0-9+/=\n]+\n-----END \1-----\n?",
            secret,
        ),
        "Invalid App key PEM",
    )


def store_key(secret: str, account: str) -> None:
    """Registration callback seam; never supply the secret as a CLI argument."""
    require(
        isinstance(account, str) and SLUG.fullmatch(account) and len(account) <= 100,
        "Invalid Keychain account",
    )
    _validate_key(secret)
    try:
        _mac_keyring().set_password(SERVICE, account, secret)
    except (RuntimeError, KeyringError, OSError, ValueError):
        raise PublisherError("Could not store App key in macOS Keychain") from None


def _load_key(account: str) -> str:
    try:
        secret = _mac_keyring().get_password(SERVICE, account)
        _validate_key(secret)
        return secret
    except (RuntimeError, KeyringError, OSError, ValueError):
        raise PublisherError("App key is unavailable from macOS Keychain") from None


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def app_jwt(config: Config) -> str:
    secret = _load_key(config.slug)
    now = int(time.time())
    header = _b64(b'{"alg":"RS256","typ":"JWT"}')
    payload = _b64(
        json.dumps(
            {"iat": now - 60, "exp": now + 300, "iss": str(config.app_id)},
            separators=(",", ":"),
        ).encode()
    )
    unsigned = (header + "." + payload).encode()
    read_fd, write_fd = os.pipe()
    process = None

    def write_key():
        try:
            with os.fdopen(write_fd, "wb") as stream:
                stream.write(secret.encode())
        except OSError:
            pass  # Signing failure below is deliberately redacted.

    writer = threading.Thread(target=write_key, daemon=True)
    try:
        process = subprocess.Popen(
            ["/usr/bin/openssl", "dgst", "-sha256", "-sign", f"/dev/fd/{read_fd}"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(read_fd,),
            env={"PATH": "/usr/bin:/bin", "LANG": "C"},
        )
        os.close(read_fd)
        read_fd = -1
        writer.start()
        signature, _ = process.communicate(unsigned, timeout=15)
        require(
            process.returncode == 0 and 256 <= len(signature) <= 1024,
            "App JWT signing failed",
        )
        return header + "." + payload + "." + _b64(signature)
    except (OSError, subprocess.SubprocessError):
        raise PublisherError("App JWT signing failed") from None
    finally:
        if read_fd >= 0:
            os.close(read_fd)
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()
        if writer.ident is not None:
            writer.join(timeout=2)
        else:
            os.close(write_fd)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class GitHub:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            NoRedirect(),
        )

    def request(
        self, method: str, path: str, token: str, body: dict | None = None
    ) -> dict | list:
        reads = (
            r"/app",
            r"/app/installations/[1-9][0-9]*",
            r"/installation/repositories\?per_page=100",
            r"/users/[a-z0-9-]+%5Bbot%5D",
            r"/repos/F0rge/f0rge",
            r"/repos/F0rge/f0rge/git/ref/heads/codex%2F[a-z0-9._-]+",
            r"/repos/F0rge/f0rge/pulls\?state=open&base=main&head=F0rge%3Acodex%2F[a-z0-9._-]+&per_page=100",
        )
        allowed = (
            method == "GET"
            and any(re.fullmatch(pattern, path) for pattern in reads)
            or method == "POST"
            and (
                re.fullmatch(r"/app/installations/[1-9][0-9]*/access_tokens", path)
                or path == "/repos/F0rge/f0rge/pulls"
            )
            or method == "DELETE"
            and path == "/installation/token"
        )
        require(allowed, "API operation is outside the publisher scope")
        require(
            isinstance(token, str) and re.fullmatch(r"[A-Za-z0-9_.-]{20,4096}", token),
            "Invalid authentication material",
        )
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + token,
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "f0rge-pr-publisher",
                "Content-Type": "application/json",
            },
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                require(
                    response.status
                    == (
                        204 if method == "DELETE" else 201 if method == "POST" else 200
                    ),
                    "Unexpected GitHub status",
                )
                raw = response.read(2_000_001)
                require(len(raw) <= 2_000_000, "GitHub response is too large")
                return json.loads(raw) if raw else {}
        except (urllib.error.URLError, OSError, ValueError):
            raise PublisherError(
                "GitHub request failed; inspect state before retrying a write"
            ) from None


def _permissions(value: object) -> None:
    require(isinstance(value, dict), "Missing effective permissions")
    effective = dict(value)
    effective.setdefault("metadata", "read")
    require(
        effective == PERMISSIONS, "Permissions differ from the exact publisher scope"
    )


def _repository(value: object) -> None:
    require(
        isinstance(value, dict)
        and value.get("id") == REPO_ID
        and value.get("full_name") == REPOSITORY,
        "Wrong repository identity",
    )


@contextlib.contextmanager
def verified_session(config: Config):
    api = GitHub()
    jwt = app_jwt(config)
    app = api.request("GET", "/app", jwt)
    require(
        app.get("id") == config.app_id and app.get("slug") == config.slug,
        "App identity mismatch",
    )
    _permissions(app.get("permissions"))
    installation = api.request(
        "GET", f"/app/installations/{config.installation_id}", jwt
    )
    require(
        installation.get("id") == config.installation_id
        and installation.get("app_id") == config.app_id
        and installation.get("app_slug") == config.slug
        and installation.get("account", {}).get("login") == "F0rge"
        and installation.get("target_type") == "Organization"
        and installation.get("repository_selection") == "selected"
        and installation.get("suspended_at") is None,
        "Installation identity or selection mismatch",
    )
    _permissions(installation.get("permissions"))
    minted = api.request(
        "POST",
        f"/app/installations/{config.installation_id}/access_tokens",
        jwt,
        {
            "repository_ids": [REPO_ID],
            "permissions": {"contents": "read", "pull_requests": "write"},
        },
    )
    token = minted.get("token")
    require(
        isinstance(token, str) and re.fullmatch(r"[A-Za-z0-9_.-]{20,4096}", token),
        "Invalid installation token",
    )
    try:
        _permissions(minted.get("permissions"))
        expires = dt.datetime.fromisoformat(minted["expires_at"].replace("Z", "+00:00"))
        require(
            expires.tzinfo is not None
            and 0 < (expires - dt.datetime.now(dt.UTC)).total_seconds() <= 3660,
            "Invalid token expiry",
        )
        listing = api.request("GET", "/installation/repositories?per_page=100", token)
        repositories = listing.get("repositories", [])
        require(
            listing.get("total_count") == 1 and len(repositories) == 1,
            "Token must access exactly one repository",
        )
        _repository(repositories[0])
        repo = api.request("GET", "/repos/F0rge/f0rge", token)
        _repository(repo)
        require(
            repo.get("default_branch") == "main"
            and repo.get("archived") is False
            and repo.get("fork") is False,
            "Repository is not the expected active main repository",
        )
        bot = api.request(
            "GET", "/users/" + urllib.parse.quote(config.slug + "[bot]", safe=""), token
        )
        require(
            bot.get("login") == config.slug + "[bot]"
            and bot.get("type") == "Bot"
            and type(bot.get("id")) is int
            and bot["id"] > 0,
            "Bot identity mismatch",
        )
        facts = {
            "app_id": config.app_id,
            "slug": config.slug,
            "installation_id": config.installation_id,
            "repo_id": REPO_ID,
            "repository": REPOSITORY,
            "permissions": PERMISSIONS,
            "bot_login": bot["login"],
            "bot_id": bot["id"],
            "token_expires_at": minted["expires_at"],
        }
        yield api, token, facts
    finally:
        api.request("DELETE", "/installation/token", token)


def inspect(config: Config) -> dict:
    with verified_session(config) as (_api, _token, facts):
        return facts


def _validate_pr(value: dict, head: str, expected: str, facts: dict) -> dict:
    require(
        value.get("state") == "open"
        and value.get("head", {}).get("ref") == head
        and value.get("head", {}).get("sha") == expected
        and value.get("base", {}).get("ref") == "main",
        "PR may exist with a different head; inspect it before proceeding",
    )
    _repository(value.get("head", {}).get("repo"))
    _repository(value.get("base", {}).get("repo"))
    require(
        value.get("user", {}).get("type") == "Bot"
        and value.get("user", {}).get("id") == facts["bot_id"]
        and value.get("user", {}).get("login") == facts["bot_login"],
        "PR author is not the verified publisher bot",
    )
    number = value.get("number")
    require(
        type(number) is int
        and number > 0
        and value.get("html_url") == f"https://github.com/F0rge/f0rge/pull/{number}",
        "Unexpected PR identity",
    )
    return {
        "number": number,
        "url": value["html_url"],
        "head": head,
        "head_sha": expected,
        "author": facts["bot_login"],
    }


def open_pr(
    config: Config, head: str, expected_head: str, title: str, body: str
) -> dict:
    require(
        BRANCH.fullmatch(head)
        and ".." not in head
        and not head.endswith((".", ".lock")),
        "Only a simple existing codex/* branch is allowed",
    )
    require(SHA.fullmatch(expected_head), "An exact expected head commit is required")
    require(
        isinstance(title, str)
        and 0 < len(title.strip()) <= 256
        and all(ord(char) >= 32 for char in title),
        "Invalid PR title",
    )
    require(
        isinstance(body, str) and 0 < len(body.encode()) <= 60000, "Invalid PR body"
    )
    with verified_session(config) as (api, token, facts):
        query = urllib.parse.urlencode(
            {"state": "open", "base": "main", "head": "F0rge:" + head, "per_page": 100}
        )
        existing = api.request("GET", "/repos/F0rge/f0rge/pulls?" + query, token)
        require(
            isinstance(existing, list) and len(existing) <= 1, "Ambiguous existing PRs"
        )
        if existing:
            return dict(
                _validate_pr(existing[0], head, expected_head, facts), existing=True
            )
        # Last read before the only PR mutation. GitHub does not offer an atomic
        # branch-head lease on POST /pulls, so validate the returned head too.
        ref = api.request(
            "GET",
            "/repos/F0rge/f0rge/git/ref/heads/" + urllib.parse.quote(head, safe=""),
            token,
        )
        require(
            ref.get("ref") == "refs/heads/" + head
            and ref.get("object", {}).get("type") == "commit"
            and ref["object"].get("sha") == expected_head,
            "Branch head changed; no PR created",
        )
        value = api.request(
            "POST",
            "/repos/F0rge/f0rge/pulls",
            token,
            {
                "title": title,
                "body": body,
                "head": head,
                "base": "main",
                "maintainer_can_modify": False,
            },
        )
        return dict(_validate_pr(value, head, expected_head, facts), existing=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "open-pr"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        if name == "open-pr":
            command.add_argument("--head", required=True)
            command.add_argument("--expected-head", required=True)
            command.add_argument("--title", required=True)
            command.add_argument("--body-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = read_config(args.config)
        if args.command == "inspect":
            result = inspect(config)
        else:
            require(
                args.body_file.is_file() and args.body_file.stat().st_size <= 60000,
                "Invalid PR body file",
            )
            result = open_pr(
                config,
                args.head,
                args.expected_head,
                args.title,
                args.body_file.read_text(),
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (
        RuntimeError,
        KeyringError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        subprocess.SubprocessError,
    ):
        # API/keychain/process exceptions may embed credentials or private content.
        print(
            "Publisher refused or write outcome unknown; inspect GitHub state and the private configuration before retrying.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
