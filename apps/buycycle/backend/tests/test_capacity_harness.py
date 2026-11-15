"""Offline failure-boundary checks; never invokes Docker or real services."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from capacity_api import Fixture


class FakeDocker:
    def __init__(self, failure, foreign=False):
        self.failure, self.foreign = failure, foreign
        self.labels, self.removed = {}, []

    def run(self, arguments, **kwargs):
        text = kwargs.get("text", False)

        def result(code=0, value=""):
            return subprocess.CompletedProcess(arguments, code, value if text else value.encode(), "" if text else b"")

        if arguments[1:3] == ["context", "inspect"]:
            return result(value="unix:///synthetic-docker.sock")
        command = arguments[3:]
        if command[:2] == ["image", "inspect"]:
            return result(value=json.dumps([{"Architecture": "arm64", "Os": "linux", "Config": {"User": "10001:10001"}, "Id": "synthetic-image"}]))
        if command[0] == "run":
            name = command[command.index("--name") + 1]
            label = command[command.index("--label") + 1].split("=", 1)[1]
            self.labels[name] = "foreign-task" if self.foreign else label
            if self.failure == "timeout":
                raise subprocess.TimeoutExpired(arguments, 1)
            return result(125)
        if command[0] == "inspect":
            name = command[-1]
            return result(value=self.labels[name]) if name in self.labels else result(1)
        if command[0] == "rm":
            name = command[-1]
            self.removed.append(name)
            self.labels.pop(name, None)
            return result()
        if command[:2] == ["network", "inspect"]:
            return result(1)
        raise AssertionError("Unexpected synthetic Docker operation")


class CapacityHarnessFailureTests(unittest.TestCase):
    def exercise(self, *, failure, foreground=False, foreign=False):
        docker = FakeDocker(failure, foreign)
        with tempfile.TemporaryDirectory() as temporary, patch("capacity_api.subprocess.run", docker.run):
            fixture = Fixture("synthetic-image", 15, Path(temporary))
            name = fixture.name + ("-migration" if foreground else "-server")
            error = subprocess.TimeoutExpired if failure == "timeout" else RuntimeError
            with self.assertRaises(error):
                if foreground:
                    fixture.foreground(name, "--network", "none", "synthetic-image", "migrate")
                else:
                    fixture.start(name, "--network", "none", "synthetic-image")
            fixture.cleanup()
        if foreign:
            self.assertNotIn(name, docker.removed)
            self.assertIn(name, docker.labels)
        else:
            self.assertIn(name, docker.removed)
            self.assertNotIn(name, docker.labels)

    def test_created_container_is_cleaned_after_run_error(self):
        self.exercise(failure="run-error")

    def test_created_container_is_cleaned_after_timeout(self):
        self.exercise(failure="timeout")

    def test_named_foreground_migration_is_cleaned_after_timeout(self):
        self.exercise(failure="timeout", foreground=True)

    def test_cleanup_preserves_mismatched_ownership_label(self):
        self.exercise(failure="timeout", foreign=True)

    def test_optimized_entrypoints_refuse_before_fixture_effects(self):
        for name in ("capacity_preview.py", "capacity_api.py"):
            for flag in ("-O", "-OO"):
                with self.subTest(name=name, flag=flag):
                    result = subprocess.run(
                        [sys.executable, flag, str(Path(__file__).with_name(name)), "--image", "not-an-image"], capture_output=True, text=True
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("optimized execution is refused", result.stderr)


if __name__ == "__main__":
    unittest.main()
