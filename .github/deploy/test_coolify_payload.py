"""Dry-run tests for the Coolify push payload.

    python3 -m unittest test_coolify_payload.py

from `.github/deploy` (that directory is not importable as `.github`).
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import coolify_payload as payload


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
