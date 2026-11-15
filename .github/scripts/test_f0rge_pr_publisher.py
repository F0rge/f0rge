"""Publisher contract tests: fake GitHub/Keychain and a real ephemeral RSA key.

No live API, user Keychain, repository mutation or persistent private key is used.
"""

from __future__ import annotations

import base64
import copy
import datetime as dt
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import f0rge_pr_publisher as publisher

CONFIG = publisher.Config(123, "f0rge-publisher-test", 456, publisher.REPO_ID)
HEAD = "codex/publisher-proof"
COMMIT = "c" * 40
TOKEN = "synthetic-installation-token-not-a-secret"


class FakeKeychain:
    def __init__(self, secret):
        self.secret = secret
        self.calls = []

    def get_password(self, service, account):
        self.calls.append(("get", service, account))
        return self.secret

    def set_password(self, service, account, secret):
        self.calls.append(("set", service, account))
        self.secret = secret


class FakeGitHub:
    def __init__(self):
        repo = {
            "id": publisher.REPO_ID,
            "full_name": publisher.REPOSITORY,
            "default_branch": "main",
            "archived": False,
            "fork": False,
        }
        self.values = {
            ("GET", "/app"): {
                "id": CONFIG.app_id,
                "slug": CONFIG.slug,
                "permissions": dict(publisher.PERMISSIONS),
            },
            ("GET", f"/app/installations/{CONFIG.installation_id}"): {
                "id": CONFIG.installation_id,
                "app_id": CONFIG.app_id,
                "app_slug": CONFIG.slug,
                "account": {"login": "F0rge"},
                "target_type": "Organization",
                "repository_selection": "selected",
                "suspended_at": None,
                "permissions": dict(publisher.PERMISSIONS),
            },
            ("POST", f"/app/installations/{CONFIG.installation_id}/access_tokens"): {
                "token": TOKEN,
                "permissions": dict(publisher.PERMISSIONS),
                "expires_at": (
                    dt.datetime.now(dt.UTC) + dt.timedelta(minutes=59)
                ).isoformat(),
            },
            ("GET", "/installation/repositories?per_page=100"): {
                "total_count": 1,
                "repositories": [repo],
            },
            ("GET", "/repos/F0rge/f0rge"): repo,
            ("GET", "/users/f0rge-publisher-test%5Bbot%5D"): {
                "login": CONFIG.slug + "[bot]",
                "type": "Bot",
                "id": 987,
            },
            (
                "GET",
                "/repos/F0rge/f0rge/pulls?state=open&base=main&head=F0rge%3Acodex%2Fpublisher-proof&per_page=100",
            ): [],
            ("GET", "/repos/F0rge/f0rge/git/ref/heads/codex%2Fpublisher-proof"): {
                "ref": "refs/heads/" + HEAD,
                "object": {"type": "commit", "sha": COMMIT},
            },
            ("POST", "/repos/F0rge/f0rge/pulls"): {
                "number": 1,
                "html_url": "https://github.com/F0rge/f0rge/pull/1",
                "state": "open",
                "head": {"ref": HEAD, "sha": COMMIT, "repo": repo},
                "base": {"ref": "main", "repo": repo},
                "user": {"login": CONFIG.slug + "[bot]", "type": "Bot", "id": 987},
            },
            ("DELETE", "/installation/token"): {},
        }
        self.calls = []

    def request(self, method, path, token, body=None):
        self.calls.append((method, path, token, body))
        return copy.deepcopy(self.values[(method, path)])

    def pr_writes(self):
        return [
            call
            for call in self.calls
            if call[:2] == ("POST", "/repos/F0rge/f0rge/pulls")
        ]


class PublisherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
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
        )
        cls.pem = result.stdout.decode()

    def setUp(self):
        self.keychain = FakeKeychain(self.pem)
        self.api = FakeGitHub()
        backend = patch.object(publisher, "_mac_keyring", return_value=self.keychain)
        transport = patch.object(publisher, "GitHub", return_value=self.api)
        backend.start()
        transport.start()
        self.addCleanup(backend.stop)
        self.addCleanup(transport.stop)

    def test_real_rs256_signature_uses_anonymous_key_fd_and_clock_bound_claims(self):
        with patch.dict(
            os.environ,
            {"GH_TOKEN": "unrelated-human-token", "GITHUB_TOKEN": "another-user-token"},
        ):
            encoded = publisher.app_jwt(CONFIG)
        header, body, signature = encoded.split(".")
        decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        self.assertEqual(json.loads(decode(header)), {"alg": "RS256", "typ": "JWT"})
        claims = json.loads(decode(body))
        self.assertEqual(claims["iss"], str(CONFIG.app_id))
        self.assertEqual(claims["exp"] - claims["iat"], 360)
        self.assertLessEqual(abs(claims["iat"] - (int(publisher.time.time()) - 60)), 2)
        public = subprocess.run(
            ["/usr/bin/openssl", "pkey", "-pubout"],
            input=self.pem.encode(),
            capture_output=True,
            check=True,
            timeout=10,
        ).stdout
        with tempfile.TemporaryDirectory() as directory:
            key, sig = Path(directory) / "public.pem", Path(directory) / "signature.bin"
            key.write_bytes(public)
            sig.write_bytes(decode(signature))
            verified = subprocess.run(
                [
                    "/usr/bin/openssl",
                    "dgst",
                    "-sha256",
                    "-verify",
                    str(key),
                    "-signature",
                    str(sig),
                ],
                input=(header + "." + body).encode(),
                capture_output=True,
                check=False,
                timeout=10,
            )
            self.assertEqual(verified.returncode, 0)
        self.assertEqual(self.keychain.calls, [("get", publisher.SERVICE, CONFIG.slug)])

    def test_store_seam_uses_exact_service_and_account_without_output(self):
        captured = io.StringIO()
        with redirect_stdout(captured), redirect_stderr(captured):
            publisher.store_key(self.pem, CONFIG.slug)
        self.assertEqual(self.keychain.calls, [("set", publisher.SERVICE, CONFIG.slug)])
        self.assertEqual(captured.getvalue(), "")

    def test_missing_key_does_not_fall_back_to_environment_or_user_auth(self):
        self.keychain.secret = None
        with (
            patch.dict(os.environ, {"GH_TOKEN": TOKEN, "GITHUB_TOKEN": TOKEN}),
            self.assertRaises(publisher.PublisherError),
        ):
            publisher.inspect(CONFIG)
        self.assertEqual(self.api.calls, [])

    def test_inspect_verifies_scope_and_revokes_only_scoped_installation_token(self):
        facts = publisher.inspect(CONFIG)
        self.assertEqual(facts["repo_id"], publisher.REPO_ID)
        self.assertEqual(facts["permissions"], publisher.PERMISSIONS)
        self.assertNotIn(TOKEN, json.dumps(facts))
        mint = next(
            call
            for call in self.api.calls
            if call[:2] == ("POST", "/app/installations/456/access_tokens")
        )
        self.assertEqual(
            mint[3],
            {
                "repository_ids": [publisher.REPO_ID],
                "permissions": {"contents": "read", "pull_requests": "write"},
            },
        )
        self.assertEqual(
            self.api.calls[-1][:3], ("DELETE", "/installation/token", TOKEN)
        )
        self.assertEqual(self.api.pr_writes(), [])

    def test_wrong_app_installation_owner_scope_and_permissions_refuse_pr_creation(
        self,
    ):
        cases = [
            (("GET", "/app"), lambda value: value.update(id=789)),
            (
                ("GET", "/app"),
                lambda value: value["permissions"].update(contents="write"),
            ),
            (
                ("GET", "/app"),
                lambda value: value["permissions"].update(actions="write"),
            ),
            (("GET", "/app/installations/456"), lambda value: value.update(app_id=789)),
            (
                ("GET", "/app/installations/456"),
                lambda value: value["account"].update(login="another-org"),
            ),
            (
                ("GET", "/app/installations/456"),
                lambda value: value.update(repository_selection="all"),
            ),
            (
                ("GET", "/app/installations/456"),
                lambda value: value.update(suspended_at="2026-11-15T12:00:00Z"),
            ),
            (
                ("GET", "/installation/repositories?per_page=100"),
                lambda value: value.update(total_count=2),
            ),
            (
                ("GET", "/installation/repositories?per_page=100"),
                lambda value: value["repositories"][0].update(id=111),
            ),
            (
                ("POST", "/app/installations/456/access_tokens"),
                lambda value: value["permissions"].update(workflows="write"),
            ),
            (
                ("POST", "/app/installations/456/access_tokens"),
                lambda value: value.update(
                    expires_at=(
                        dt.datetime.now(dt.UTC) + dt.timedelta(hours=2)
                    ).isoformat()
                ),
            ),
        ]
        for endpoint, mutate in cases:
            with self.subTest(endpoint=endpoint):
                original = copy.deepcopy(self.api.values)
                mutate(self.api.values[endpoint])
                with self.assertRaises(publisher.PublisherError):
                    publisher.open_pr(
                        CONFIG, HEAD, COMMIT, "docs: safe proof", "Synthetic proof"
                    )
                self.assertEqual(self.api.pr_writes(), [])
                self.api.values = original

    def test_open_pr_checks_head_lease_and_verified_bot_author(self):
        value = publisher.open_pr(
            CONFIG, HEAD, COMMIT, "docs: safe proof", "Synthetic proof"
        )
        self.assertEqual(
            value,
            {
                "number": 1,
                "url": "https://github.com/F0rge/f0rge/pull/1",
                "head": HEAD,
                "head_sha": COMMIT,
                "author": CONFIG.slug + "[bot]",
                "existing": False,
            },
        )
        writes = self.api.pr_writes()
        self.assertEqual(len(writes), 1)
        self.assertEqual(
            writes[0][3],
            {
                "title": "docs: safe proof",
                "body": "Synthetic proof",
                "head": HEAD,
                "base": "main",
                "maintainer_can_modify": False,
            },
        )
        self.assertEqual(
            self.api.calls[-3][:2],
            ("GET", "/repos/F0rge/f0rge/git/ref/heads/codex%2Fpublisher-proof"),
        )

    def test_changed_head_has_no_pr_write(self):
        self.api.values[
            ("GET", "/repos/F0rge/f0rge/git/ref/heads/codex%2Fpublisher-proof")
        ]["object"]["sha"] = "d" * 40
        with self.assertRaises(publisher.PublisherError):
            publisher.open_pr(CONFIG, HEAD, COMMIT, "docs: proof", "Synthetic proof")
        self.assertEqual(self.api.pr_writes(), [])

    def test_post_create_head_race_is_reported_without_retry_or_cleanup_write(self):
        self.api.values[("POST", "/repos/F0rge/f0rge/pulls")]["head"]["sha"] = "d" * 40
        with self.assertRaisesRegex(publisher.PublisherError, "PR may exist"):
            publisher.open_pr(CONFIG, HEAD, COMMIT, "docs: proof", "Synthetic proof")
        self.assertEqual(len(self.api.pr_writes()), 1)
        self.assertEqual(
            [call[0] for call in self.api.calls if call[0] in {"PATCH", "PUT"}], []
        )

    def test_existing_matching_bot_pr_is_idempotent_but_human_pr_is_not_reused(self):
        endpoint = (
            "GET",
            "/repos/F0rge/f0rge/pulls?state=open&base=main&head=F0rge%3Acodex%2Fpublisher-proof&per_page=100",
        )
        self.api.values[endpoint] = [
            copy.deepcopy(self.api.values[("POST", "/repos/F0rge/f0rge/pulls")])
        ]
        self.assertTrue(
            publisher.open_pr(CONFIG, HEAD, COMMIT, "docs: proof", "Synthetic proof")[
                "existing"
            ]
        )
        self.assertEqual(self.api.pr_writes(), [])
        self.api.values[endpoint][0]["user"].update(type="User", login="human")
        with self.assertRaises(publisher.PublisherError):
            publisher.open_pr(CONFIG, HEAD, COMMIT, "docs: proof", "Synthetic proof")

    def test_non_codex_branches_or_invalid_input_are_refused_before_auth(self):
        for branch in (
            "main",
            "develop",
            "codex/a..b",
            "codex/a.lock",
            "codex/a/b",
            "other/branch",
        ):
            with (
                self.subTest(branch=branch),
                self.assertRaises(publisher.PublisherError),
            ):
                publisher.open_pr(
                    CONFIG, branch, COMMIT, "docs: proof", "Synthetic proof"
                )
        self.assertEqual(self.api.calls, [])


class TransportAndConfigTests(unittest.TestCase):
    def test_private_config_has_exact_nonsecret_fields_and_no_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "publisher.json"
            value = {
                "app_id": CONFIG.app_id,
                "slug": CONFIG.slug,
                "installation_id": CONFIG.installation_id,
                "repo_id": publisher.REPO_ID,
            }
            path.write_text(json.dumps(value))
            path.chmod(0o600)
            self.assertEqual(publisher.read_config(path), CONFIG)
            path.chmod(0o644)
            with self.assertRaises(publisher.PublisherError):
                publisher.read_config(path)
            path.chmod(0o600)
            path.write_text(json.dumps(dict(value, private_key="forbidden")))
            with self.assertRaises(publisher.PublisherError):
                publisher.read_config(path)
            linked = path.parent / "linked.json"
            linked.symlink_to(path)
            with self.assertRaises(publisher.PublisherError):
                publisher.read_config(linked)

    def test_explicit_mac_backend_ignores_generic_and_keychain_environment(self):
        fake_module = types.ModuleType("keyring.backends.macOS")
        backend = Mock()
        fake_module.Keyring = Mock(return_value=backend)
        modules = {
            "keyring": types.ModuleType("keyring"),
            "keyring.backends": types.ModuleType("keyring.backends"),
            "keyring.backends.macOS": fake_module,
        }
        with (
            patch.dict(sys.modules, modules),
            patch.object(sys, "platform", "darwin"),
            patch.object(
                publisher.importlib.metadata, "version", return_value="25.6.0"
            ),
            patch.dict(
                os.environ,
                {
                    "PYTHON_KEYRING_BACKEND": "plaintext.backend",
                    "KEYCHAIN_PATH": "/tmp/untrusted",
                },
            ),
        ):
            self.assertIs(publisher._mac_keyring(), backend)
        self.assertIsNone(backend.keychain)
        fake_module.Keyring.assert_called_once_with()

    def test_network_destination_and_methods_are_fixed_and_redirects_fail_closed(self):
        api = publisher.GitHub()
        api.opener = Mock()
        for method, path in (
            ("POST", "/repos/F0rge/f0rge/merges"),
            ("PUT", "/repos/F0rge/f0rge/pulls/1/merge"),
            ("POST", "/repos/F0rge/f0rge/pulls/1/reviews"),
            ("GET", "https://elsewhere.test/app"),
            ("GET", "/app/../evil"),
            ("PATCH", "/repos/F0rge/f0rge"),
        ):
            with self.subTest(path=path), self.assertRaises(publisher.PublisherError):
                api.request(method, path, TOKEN)
        api.opener.open.assert_not_called()
        api.opener.open.side_effect = urllib.error.HTTPError(
            publisher.API + "/app", 302, "secret-error-body", {}, None
        )
        with self.assertRaises(publisher.PublisherError):
            api.request("GET", "/app", TOKEN)
        request = api.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.github.com/app")
        self.assertIsNone(
            publisher.NoRedirect().redirect_request(
                None, None, 302, "", {}, "https://elsewhere.test"
            )
        )

    def test_cli_failure_redacts_exception_and_has_no_credential_flags(self):
        output, error = io.StringIO(), io.StringIO()
        with (
            patch.object(sys, "argv", ["publisher", "inspect", "--config", "/unused"]),
            patch.object(
                publisher,
                "read_config",
                side_effect=RuntimeError("PRIVATE-KEY SECRET-TOKEN"),
            ),
            redirect_stdout(output),
            redirect_stderr(error),
        ):
            self.assertEqual(publisher.main(), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertNotIn("PRIVATE-KEY", error.getvalue())
        self.assertNotIn("SECRET-TOKEN", error.getvalue())


if __name__ == "__main__":
    unittest.main()
