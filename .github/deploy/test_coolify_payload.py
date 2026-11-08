"""Dry-run tests for the Coolify push payload.

    python3 -m unittest test_coolify_payload.py

from `.github/deploy` (that directory is not importable as `.github`).
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path

import coolify_payload as payload


@contextmanager
def _stdin(text: str):
    old = sys.stdin
    sys.stdin = io.StringIO(text)
    try:
        yield
    finally:
        sys.stdin = old


class DiffBaseTests(unittest.TestCase):
    def test_parent_when_nx_base_collapsed_to_head(self) -> None:
        self.assertEqual(payload.coolify_diff_base("abc", "abc", "parent"), "parent")

    def test_nx_base_when_range_is_real(self) -> None:
        self.assertEqual(payload.coolify_diff_base("base", "head", "parent"), "base")

    def test_nx_base_when_parent_missing(self) -> None:
        self.assertEqual(payload.coolify_diff_base("abc", "abc", ""), "abc")


class NameStatusTests(unittest.TestCase):
    def test_added_modified_removed(self) -> None:
        raw = b"A\0apps/buycycle/README.md\0M\0apps/dk/tag-printer/backend/app/main.py\0D\0old.txt\0"
        self.assertEqual(
            payload.parse_name_status_z(raw),
            {
                "added": ["apps/buycycle/README.md"],
                "modified": ["apps/dk/tag-printer/backend/app/main.py"],
                "removed": ["old.txt"],
            },
        )

    def test_rename_is_removed_and_added(self) -> None:
        raw = b"R100\0sub/old.txt\0sub/new.txt\0"
        parsed = payload.parse_name_status_z(raw)
        self.assertEqual(parsed["removed"], ["sub/old.txt"])
        self.assertEqual(parsed["added"], ["sub/new.txt"])
        self.assertEqual(parsed["modified"], [])

    def test_copy_is_added(self) -> None:
        raw = b"C075\0sub/old.txt\0sub/copy.txt\0"
        self.assertEqual(payload.parse_name_status_z(raw)["added"], ["sub/copy.txt"])

    def test_type_change_is_modified(self) -> None:
        raw = b"T\0apps/buycycle/bin\0"
        self.assertEqual(payload.parse_name_status_z(raw)["modified"], ["apps/buycycle/bin"])

    def test_path_with_spaces(self) -> None:
        raw = b"A\0apps/buycycle/two words.md\0"
        self.assertEqual(payload.parse_name_status_z(raw)["added"], ["apps/buycycle/two words.md"])

    def test_unknown_status_fails(self) -> None:
        with self.assertRaises(ValueError):
            payload.parse_name_status_z(b"U\0conflict.txt\0")


class PayloadShapeTests(unittest.TestCase):
    def test_one_commit_keeps_repo_and_ref(self) -> None:
        body = payload.build_push_payload(
            "abc123",
            "main",
            ["apps/buycycle/deploy/PI_CUTOVER.md"],
            ["apps/dk/tag-printer/backend/README.md"],
            [],
        )
        encoded = payload.payload_json(body)
        self.assertEqual(
            json.loads(encoded),
            {
                "ref": "refs/heads/main",
                "after": "abc123",
                "commits": [
                    {
                        "id": "abc123",
                        "added": ["apps/buycycle/deploy/PI_CUTOVER.md"],
                        "modified": ["apps/dk/tag-printer/backend/README.md"],
                        "removed": [],
                    }
                ],
                "repository": {"full_name": "F0rge/f0rge", "name": "f0rge"},
            },
        )
        self.assertNotIn(" ", encoded)

    def test_empty_diff_still_sends_commits_key(self) -> None:
        body = payload.build_push_payload("abc", "main", [], [], [])
        self.assertEqual(len(body["commits"]), 1)
        self.assertIn('"commits":[', payload.payload_json(body))


class GitDiffTests(unittest.TestCase):
    def test_real_diff_matches_name_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._git(root, "init", "-q")
            self._git(root, "config", "user.email", "t@example.com")
            self._git(root, "config", "user.name", "t")
            app = root / "apps" / "buycycle"
            app.mkdir(parents=True)
            (app / "note.md").write_text("one\n")
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "base")
            base = self._git(root, "rev-parse", "HEAD").strip()
            (app / "note.md").write_text("two\n")
            (app / "new file.md").write_text("added\n")
            (app / "gone.md").write_text("x\n")
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "mid")
            (app / "gone.md").unlink()
            self._git(root, "add", "-A")
            self._git(root, "commit", "-qm", "head")
            head = self._git(root, "rev-parse", "HEAD").strip()
            files = payload.diff_name_status(str(root), base, head)
            self.assertEqual(files["added"], ["apps/buycycle/new file.md"])
            self.assertEqual(files["modified"], ["apps/buycycle/note.md"])
            self.assertEqual(files["removed"], [])
            # gone.md was added and removed inside the range; net diff omits it.
            built = payload.build_push_payload(head, "main", files["added"], files["modified"], files["removed"])
            self.assertEqual(built["commits"][0]["id"], head)
            self.assertIn("apps/buycycle/note.md", built["commits"][0]["modified"])

    def _git(self, root: Path, *args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=root, text=True)


class QueuedResponseTests(unittest.TestCase):
    UUID = "xi0qwpbyl2d8gf8u3xl13jkv"

    def test_watch_path_ignore_is_not_queued(self) -> None:
        body = json.dumps(
            [
                {
                    "status": "failed",
                    "message": "Changed files do not match watch paths. Ignoring deployment.",
                    "application_uuid": self.UUID,
                    "application_name": "buycycle",
                    "details": {"changed_files": [], "watch_paths": ["apps/buycycle/**"]},
                },
                {"application": "daskasas-backend", "status": "failed", "message": "Invalid signature."},
                {"application": "daskasas-frontend", "status": "failed", "message": "Invalid signature."},
            ]
        )
        self.assertFalse(payload.response_queues_app(body, self.UUID))

    def test_success_message_is_queued(self) -> None:
        body = json.dumps(
            [
                {
                    "application": "buycycle",
                    "status": "success",
                    "message": "Deployment queued.",
                    "application_uuid": self.UUID,
                    "application_name": "buycycle",
                    "deployment_uuid": "dep123",
                },
                {"application": "daskasas-backend", "status": "failed", "message": "Invalid signature."},
            ]
        )
        self.assertTrue(payload.response_queues_app(body, self.UUID))

    def test_status_queued_and_root_object(self) -> None:
        self.assertTrue(
            payload.response_queues_app(
                json.dumps([{"application_uuid": self.UUID, "status": "queued"}]),
                self.UUID,
            )
        )
        self.assertTrue(payload.response_queues_app(json.dumps({"status": "queued"}), self.UUID))

    def test_other_app_success_does_not_count(self) -> None:
        body = json.dumps(
            [{"application_uuid": "someone-else", "status": "success", "message": "Deployment queued."}]
        )
        self.assertFalse(payload.response_queues_app(body, self.UUID))

    def test_sibling_invalid_signature_does_not_fail(self) -> None:
        # Body from the buycycle deploy: this app queued, dk apps rejected the HMAC.
        body = json.dumps(
            [
                {
                    "application": "buycycle",
                    "status": "success",
                    "message": "Deployment queued.",
                    "application_uuid": self.UUID,
                    "application_name": "buycycle",
                    "deployment_uuid": "dep",
                },
                {"application": "daskasas-frontend", "status": "failed", "message": "Invalid signature."},
                {"application": "daskasas-backend", "status": "failed", "message": "Invalid signature."},
            ]
        )
        self.assertTrue(payload.response_queues_app(body, self.UUID))

    def test_this_app_invalid_signature_is_not_queued(self) -> None:
        backend = "pskswsc8c0044ggo40go4og0"
        body = json.dumps(
            [
                {
                    "application": "daskasas-backend",
                    "status": "failed",
                    "message": "Invalid signature.",
                    "application_uuid": backend,
                },
                {
                    "application": "buycycle",
                    "status": "success",
                    "message": "Deployment queued.",
                    "application_uuid": self.UUID,
                },
            ]
        )
        self.assertFalse(payload.response_queues_app(body, backend))
        self.assertTrue(payload.response_queues_app(body, self.UUID))


class ClassifyCoolifyResponseTests(unittest.TestCase):
    """HTTP status + this app's message → success / skipped / failed."""

    UUID = "xi0qwpbyl2d8gf8u3xl13jkv"
    OTHER = "other-app"
    IGNORE = "Changed files do not match watch paths. Ignoring deployment."

    def _body(self, message: str, app_uuid: str | None = None, **extra: object) -> str:
        entry: dict[str, object] = {
            "status": "failed",
            "message": message,
            "application_uuid": self.UUID if app_uuid is None else app_uuid,
            "application_name": "buycycle",
            "details": {
                "changed_files": ["package-lock.json"],
                "watch_paths": ["apps/buycycle/**"],
            },
        }
        entry.update(extra)
        return json.dumps(
            [
                entry,
                {"application": "daskasas-backend", "status": "failed", "message": "Invalid signature."},
            ]
        )

    def _classify(self, http_status: int, body: str, app_uuid: str | None = None) -> str:
        app = self.UUID if app_uuid is None else app_uuid
        outcome = payload.classify_coolify_response(http_status, body, app)
        stdout = io.StringIO()
        with _stdin(body), redirect_stdout(stdout):
            code = payload.main(
                ["--classify", "--http-status", str(http_status), "--app-uuid", app]
            )
        self.assertEqual(stdout.getvalue().strip(), outcome)
        self.assertEqual(code, 0 if outcome in {"success", "skipped"} else 1)
        return outcome

    def test_queued_is_success(self) -> None:
        body = json.dumps(
            [
                {
                    "application": "buycycle",
                    "status": "success",
                    "message": "Deployment queued.",
                    "application_uuid": self.UUID,
                    "application_name": "buycycle",
                    "deployment_uuid": "dep123",
                },
                {"application": "daskasas-backend", "status": "failed", "message": "Invalid signature."},
            ]
        )
        self.assertEqual(self._classify(200, body), "success")
        self.assertEqual(
            self._classify(200, json.dumps([{"application_uuid": self.UUID, "status": "queued", "deployment_uuid": "dep"}])),
            "success",
        )

    def test_watch_path_ignore_is_skipped(self) -> None:
        # Shape from Deploy run 39547607493 (buycycle / envmon): HTTP 200,
        # status failed, exact ignore sentence, no deployment uuid.
        body = self._body(self.IGNORE)
        self.assertEqual(self._classify(200, body), "skipped")
        self.assertEqual(self._classify(201, body), "skipped")
        # Same body, different app: the sentence belongs to UUID, not OTHER.
        self.assertEqual(self._classify(200, body, self.OTHER), "failed")

    def test_other_ignore_or_unknown_message_is_failed(self) -> None:
        messages = [
            "Ignoring",
            "Ignoring deployment.",
            "Ignoring deployment",
            "Changed files do not match watch paths. Ignoring deployment",
            "Changed files do not match watch paths. Ignoring deployment. ",
            "changed files do not match watch paths. Ignoring deployment.",
            "Changed files do not match watch paths. Ignoring deployment. extra",
            "Invalid signature.",
            "Deployments disabled",
            "deployments disabled.",
            "Deployments disabled. ",
            "Deployments disabled. extra",
            "No deployment was queued.",
        ]
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(self._classify(200, self._body(message)), "failed")
        self.assertEqual(self._classify(200, json.dumps({"status": "failed"})), "failed")
        self.assertEqual(self._classify(200, "not-json"), "failed")

    def test_deployments_disabled_is_failure(self) -> None:
        # Shape from Deploy run 40820662158 (dk-tag-printer-backend): HTTP 200,
        # selected app message is exactly "Deployments disabled.", siblings are
        # "Invalid signature." with no uuid. classify returns failed (CLI exit 1).
        backend = "pskswsc8c0044ggo40go4og0"
        body = json.dumps(
            [
                {"application": "buycycle", "status": "failed", "message": "Invalid signature."},
                {"application": "daskasas-frontend", "status": "failed", "message": "Invalid signature."},
                {
                    "application": "environment-monitor-backend",
                    "status": "failed",
                    "message": "Invalid signature.",
                },
                {
                    "status": "failed",
                    "message": "Deployments disabled.",
                    "application_uuid": backend,
                    "application_name": "daskasas-backend",
                },
                {
                    "application": "environment-monitor-frontend",
                    "status": "failed",
                    "message": "Invalid signature.",
                },
            ]
        )
        self.assertTrue(payload.response_deployments_disabled(body, backend))
        self.assertFalse(payload.response_deployments_disabled(body, self.UUID))
        self.assertEqual(self._classify(200, body, backend), "failed")
        self.assertEqual(self._classify(201, body, backend), "failed")
        disabled_out = io.StringIO()
        with _stdin(body), redirect_stdout(disabled_out):
            disabled_code = payload.main(["--deployments-disabled", "--app-uuid", backend])
        self.assertEqual(disabled_code, 0)
        self.assertEqual(disabled_out.getvalue(), "")
        with _stdin(body), redirect_stdout(io.StringIO()):
            other_code = payload.main(["--deployments-disabled", "--app-uuid", self.UUID])
        self.assertEqual(other_code, 1)
        # Sentence belongs to the backend uuid, not to some other selected app.
        self.assertEqual(self._classify(200, body, self.UUID), "failed")
        # No uuid on the object: not this app, so a plain failure (still not a skip).
        bare = json.dumps({"status": "failed", "message": "Deployments disabled."})
        self.assertEqual(self._classify(200, bare), "failed")
        self.assertEqual(self._classify(500, body, backend), "failed")

    def test_sibling_disabled_does_not_change_selected_outcome(self) -> None:
        disabled_sibling = {
            "status": "failed",
            "message": "Deployments disabled.",
            "application_uuid": "pskswsc8c0044ggo40go4og0",
            "application_name": "daskasas-backend",
        }
        queued = {
            "application": "buycycle",
            "status": "success",
            "message": "Deployment queued.",
            "application_uuid": self.UUID,
            "deployment_uuid": "dep123",
        }
        self.assertEqual(self._classify(200, json.dumps([queued, disabled_sibling])), "success")
        ignored = {
            "status": "failed",
            "message": self.IGNORE,
            "application_uuid": self.UUID,
            "application_name": "buycycle",
        }
        self.assertEqual(self._classify(200, json.dumps([ignored, disabled_sibling])), "skipped")
        # Selected app's own Invalid signature fails. The sibling's disabled
        # sentence does not reclassify it, and does not skip the job.
        invalid = {
            "application": "buycycle",
            "status": "failed",
            "message": "Invalid signature.",
            "application_uuid": self.UUID,
        }
        self.assertEqual(self._classify(200, json.dumps([invalid, disabled_sibling])), "failed")

    def test_non_2xx_is_failed(self) -> None:
        ignore = self._body(self.IGNORE)
        queued = json.dumps(
            {
                "status": "success",
                "message": "Deployment queued.",
                "application_uuid": self.UUID,
                "deployment_uuid": "dep123",
            }
        )
        for status in (199, 300, 404, 500):
            with self.subTest(status=status):
                self.assertEqual(self._classify(status, ignore), "failed")
                self.assertEqual(self._classify(status, queued), "failed")


class ManifestSecretTests(unittest.TestCase):
    def test_each_coolify_app_has_its_own_secret(self) -> None:
        text = Path(__file__).with_name("manifest.yml").read_text()
        envs = re.findall(r"webhook_secret_env:\s*(\S+)", text)
        self.assertEqual(
            envs,
            [
                "COOLIFY_WEBHOOK_DASKASAS_BACKEND",
                "COOLIFY_WEBHOOK_DASKASAS_FRONTEND",
                "COOLIFY_WEBHOOK_BUYCYCLE",
                "COOLIFY_WEBHOOK_ENVMON_BACKEND",
                "COOLIFY_WEBHOOK_ENVMON_FRONTEND",
            ],
        )
        self.assertEqual(len(envs), len(set(envs)))

    def test_watch_paths_cover_coolify_app_dirs(self) -> None:
        text = Path(__file__).with_name("manifest.yml").read_text()
        # Component body is the following 4-space-indented lines (next key is at 2 spaces).
        coolify_names = []
        for match in re.finditer(r"^  ([a-z0-9-]+):\n((?:    .*\n)*)", text, re.MULTILINE):
            name, body = match.group(1), match.group(2)
            if "target: coolify" in body:
                coolify_names.append(name)
        self.assertEqual(sorted(coolify_names), sorted(payload.COOLIFY_WATCH_PATHS))
        covered = {
            "environment-monitor-backend": "apps/environment-monitor/backend/app.py",
            "environment-monitor-frontend": "apps/environment-monitor/frontend/Dockerfile",
        }
        for app, path in covered.items():
            globs = payload.COOLIFY_WATCH_PATHS[app]
            self.assertTrue(
                any(path.startswith(glob.removesuffix("/**") + "/") or path == glob.removesuffix("/**") for glob in globs),
                f"{path} not covered by {globs}",
            )


if __name__ == "__main__":
    unittest.main()
