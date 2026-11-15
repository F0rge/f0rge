"""Narrow comment requester contract; fake APIs/Keychain, real ephemeral RSA signing."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import f0rge_buycycle_requester as requester
import f0rge_pr_publisher as publisher
from test_f0rge_pr_publisher import CONFIG, TOKEN, FakeGitHub, FakeKeychain


class FakeRequesterGitHub(FakeGitHub):
    def __init__(self):
        super().__init__()
        for value in self.values.values():
            if isinstance(value, dict) and "permissions" in value:
                value["permissions"] = dict(requester.REQUEST_PERMISSIONS)
        self.values[("GET", "/repos/F0rge/f0rge/pulls/900")] = {
            "number": 900,
            "merged": True,
            "base": {"ref": "main", "repo": {"id": publisher.REPO_ID}},
        }
        self.values[("GET", "/repos/F0rge/f0rge/actions/runs/44")] = {
            "repository": {"full_name": publisher.REPOSITORY},
            "path": ".github/workflows/ci.yml",
            "head_sha": "b" * 40,
            "head_branch": "main",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
        }
        self.values[
            ("GET", "/repos/F0rge/f0rge/issues/900/comments?per_page=100&page=1")
        ] = []
        self.posted = []

    def request(self, method, path, token, body=None):
        if method == "POST" and path == "/repos/F0rge/f0rge/issues/900/comments":
            self.calls.append((method, path, token, body))
            self.posted.append(body)
            self.values[("GET", "/repos/F0rge/f0rge/issues/comments/31")] = {
                "id": 31,
                "body": body["body"],
                "issue_url": "https://api.github.com/repos/F0rge/f0rge/issues/900",
                "user": {"id": 987},
                "performed_via_github_app": {"id": CONFIG.app_id, "slug": CONFIG.slug},
            }
            return {"id": 31}
        return super().request(method, path, token, body)


class RequesterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pem = subprocess.run(
            [
                "/usr/bin/openssl",
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
            ],
            capture_output=True,
            check=True,
            timeout=30,
        ).stdout.decode()

    def setUp(self):
        self.config = requester.Config(CONFIG, 900)
        self.api = FakeRequesterGitHub()
        self.keychain = FakeKeychain(self.pem)
        for target, name, result in (
            (publisher, "_mac_keyring", self.keychain),
            (requester, "RequesterGitHub", self.api),
        ):
            boundary = patch.object(target, name, return_value=result)
            boundary.start()
            self.addCleanup(boundary.stop)
        self.request = {
            "version": 1,
            "source_commit": "b" * 40,
            "ci_run_id": 44,
            "release_tag": "release/buycycle/pi/20261115T090000Z",
            "postgres_major": 15,
            "receipt_hashes": dict.fromkeys(
                ("migration", "restore", "provider"), "c" * 64
            ),
            "request_id": str(uuid.uuid4()),
        }

    def test_posts_only_the_fixed_reviewed_pr_with_exact_scope_and_revokes_token(self):
        result = requester.post_request(self.config, json.dumps(self.request))
        self.assertEqual(result["comment_id"], 31)
        self.assertEqual(result["request_id"], self.request["request_id"])
        self.assertEqual(
            result["body_sha256"],
            hashlib.sha256(self.api.posted[0]["body"].encode()).hexdigest(),
        )
        self.assertEqual(json.loads(self.api.posted[0]["body"]), self.request)
        minted = next(
            call[3]
            for call in self.api.calls
            if call[0] == "POST" and call[1].endswith("/access_tokens")
        )
        self.assertEqual(
            minted,
            {
                "repository_ids": [publisher.REPO_ID],
                "permissions": {
                    "contents": "read",
                    "pull_requests": "write",
                    "actions": "read",
                },
            },
        )
        self.assertEqual(
            self.api.calls[-1][:3], ("DELETE", "/installation/token", TOKEN)
        )
        self.assertEqual(
            self.keychain.calls[0], ("get", publisher.SERVICE, CONFIG.slug)
        )

    def test_wrong_permissions_or_unreviewed_pr_never_posts(self):
        baseline = copy.deepcopy(self.api.values)
        for mutation in (
            lambda: self.api.values[("GET", "/app")]["permissions"].update(
                actions="write"
            ),
            lambda: self.api.values[("GET", "/app")].update(
                permissions=dict(publisher.PERMISSIONS)
            ),
            lambda: self.api.values[("GET", "/repos/F0rge/f0rge/pulls/900")].update(
                merged=False
            ),
            lambda: self.api.values[
                ("GET", "/repos/F0rge/f0rge/actions/runs/44")
            ].update(event="pull_request"),
        ):
            mutation()
            with (
                self.subTest(mutation=mutation),
                self.assertRaises((publisher.PublisherError, requester.ReleaseError)),
            ):
                requester.post_request(self.config, json.dumps(self.request))
            self.assertEqual(self.api.posted, [])
            self.api.values = copy.deepcopy(baseline)

    def test_invalid_schema_or_duplicate_nonce_never_posts(self):
        with self.assertRaises(requester.ReleaseError):
            requester.post_request(
                self.config, json.dumps({**self.request, "command": "arbitrary"})
            )
        self.assertEqual(self.keychain.calls, [])
        self.api.values[
            ("GET", "/repos/F0rge/f0rge/issues/900/comments?per_page=100&page=1")
        ] = [{"user": {"id": 987}, "body": json.dumps(self.request)}]
        with self.assertRaises(publisher.PublisherError):
            requester.post_request(self.config, json.dumps(self.request))
        self.assertEqual(self.api.posted, [])
        self.assertEqual(self.api.calls[-1][:2], ("DELETE", "/installation/token"))

    def test_private_config_requires_fixed_pr_and_does_not_expand_publisher_schema(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "requester.json"
            value = {
                "app_id": CONFIG.app_id,
                "slug": CONFIG.slug,
                "installation_id": CONFIG.installation_id,
                "repo_id": publisher.REPO_ID,
                "request_pr_number": 900,
            }
            path.write_text(json.dumps(value))
            path.chmod(0o600)
            self.assertEqual(requester.read_config(path), self.config)
            with self.assertRaises(publisher.PublisherError):
                publisher.read_config(path)
            path.chmod(0o644)
            with self.assertRaises(publisher.PublisherError):
                requester.read_config(path)

    def test_ambiguous_written_comment_is_not_retried_or_deleted_and_token_is_revoked(
        self,
    ):
        original = self.api.request

        def ambiguous(method, path, token, body=None):
            result = original(method, path, token, body)
            if method == "GET" and path == "/repos/F0rge/f0rge/issues/comments/31":
                result["performed_via_github_app"] = None
            return result

        with (
            patch.object(self.api, "request", side_effect=ambiguous),
            self.assertRaises(publisher.PublisherError),
        ):
            requester.post_request(self.config, json.dumps(self.request))
        self.assertEqual(len(self.api.posted), 1)
        self.assertEqual(self.api.calls[-1][:2], ("DELETE", "/installation/token"))
        self.assertFalse(
            any(
                method == "DELETE" and "comments" in path
                for method, path, *_ in self.api.calls
            )
        )


class ApiScopeTests(unittest.TestCase):
    def test_requester_cannot_dispatch_approve_merge_write_source_or_other_comments(
        self,
    ):
        api = requester.RequesterGitHub(900)
        for method, path in (
            (
                "POST",
                "/repos/F0rge/f0rge/actions/workflows/release-buycycle.yml/dispatches",
            ),
            ("PUT", "/repos/F0rge/f0rge/pulls/900/merge"),
            ("POST", "/repos/F0rge/f0rge/pulls/900/reviews"),
            ("POST", "/repos/F0rge/f0rge/issues/901/comments"),
            ("DELETE", "/repos/F0rge/f0rge/issues/comments/31"),
            ("PUT", "/repos/F0rge/f0rge/contents/README.md"),
        ):
            with (
                self.subTest(path=path),
                patch.object(api, "_request") as transport,
                self.assertRaises(publisher.PublisherError),
            ):
                api.request(method, path, TOKEN, {})
            transport.assert_not_called()
        with self.assertRaises(publisher.PublisherError):
            publisher.GitHub().request(
                "POST", "/repos/F0rge/f0rge/issues/900/comments", TOKEN, {}
            )


if __name__ == "__main__":
    unittest.main()
