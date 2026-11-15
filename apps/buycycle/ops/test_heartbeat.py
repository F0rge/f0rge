"""Synthetic lifecycle and real loopback TLS; never contacts a notification service."""

from __future__ import annotations

import contextlib
import http.client
import http.server
import importlib.util
import io
import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import heartbeat
from ops_common import OpsError

OPS = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("buycycle_job_status", OPS / "job-status.py")
WRAPPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WRAPPER)
NOW = 1_800_000_000_000_000_000
SECOND = 1_000_000_000


class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.uid = os.getuid()
        self.source = self.root / "signals"
        self.state = self.root / "state"
        self.credentials = self.root / "credentials"
        for path in (self.source, self.state, self.credentials):
            path.mkdir(mode=0o700)
        self.config = {"schema_version": 1, "checks": {job: {"max_age_seconds": 1200, "runtime_seconds": 300} for job in heartbeat.JOBS}}
        for index, job in enumerate(heartbeat.JOBS):
            self.file(self.credentials / job, f"https://hc-ping.com/{index:08x}-aaaa-bbbb-cccc-dddddddddddd\n")
            self.record(job)
        self.sent = []

    def file(self, path, value):
        path.write_text(value)
        path.chmod(0o600)
        return path

    def record(self, job="monitor", stage="success", now_ns=NOW, run_id="a" * 32):
        heartbeat.record_status(self.source, job, run_id, stage, uid=self.uid, now_ns=now_ns)

    def send(self, path, stage):
        self.sent.append((path, stage))

    def dispatch(self, now_ns=NOW):
        with patch("heartbeat.post_signal", self.send):
            return heartbeat.courier(self.config, self.credentials, self.source, self.state, uid=self.uid, source_uid=self.uid, now_ns=now_ns)

    def test_new_events_only_and_durable_restart_deduplication(self):
        self.assertTrue(self.dispatch())
        self.assertEqual([stage for _, stage in self.sent], ["success"] * 4)
        self.dispatch(NOW + SECOND)
        self.assertEqual(len(self.sent), 4)
        state = (self.state / "delivered.json").read_text()
        self.assertNotIn("https", state)
        self.assertNotIn("dddddddddddd", state)
        self.record(now_ns=NOW + SECOND, run_id="b" * 32)
        self.dispatch(NOW + SECOND)
        self.assertEqual(len(self.sent), 5)

    def test_start_failure_and_new_success_are_distinct(self):
        self.dispatch()
        for index, stage in enumerate(("start", "failure", "success"), 1):
            self.record(stage=stage, now_ns=NOW + index * SECOND, run_id="b" * 32)
            self.dispatch(NOW + index * SECOND)
            self.assertEqual(self.sent[-1][1], stage)
        self.assertEqual(len(self.sent), 7)

    def test_stale_success_or_overdue_start_reports_failure_once(self):
        self.dispatch()
        self.record("collector", "start")
        self.dispatch()
        self.dispatch(NOW + 301 * SECOND)
        self.assertEqual(self.sent[-1][1], "failure")
        count = len(self.sent)
        self.dispatch(NOW + 302 * SECOND)
        self.assertEqual(len(self.sent), count)
        self.dispatch(NOW + 1201 * SECOND)
        self.assertEqual([stage for _, stage in self.sent[-3:]], ["failure"] * 3)

    def test_clock_reversal_never_repings_old_success_as_recovery(self):
        self.dispatch()
        self.dispatch(NOW + 1201 * SECOND)
        self.assertEqual(len(self.sent), 8)
        self.dispatch(NOW + SECOND)
        self.assertEqual(len(self.sent), 8)

    def test_missing_restored_old_success_does_not_claim_recovery(self):
        self.dispatch()
        path = self.source / "monitor.json"
        original = path.read_bytes()
        path.unlink()
        self.dispatch()
        self.assertEqual(self.sent[-1][1], "failure")
        path.write_bytes(original)
        path.chmod(0o640)
        self.dispatch()
        self.assertEqual(len(self.sent), 5)
        self.record(now_ns=NOW + SECOND, run_id="b" * 32)
        self.dispatch(NOW + SECOND)
        self.assertEqual(self.sent[-1][1], "success")

    def test_missing_corrupt_large_future_replayed_or_symlink_records_fail_closed(self):
        self.dispatch()
        path = self.source / "monitor.json"
        mutations = [None, "{", "x" * (heartbeat.MAX_BYTES + 1)]
        for value in mutations:
            path.unlink(missing_ok=True)
            if value is not None:
                self.file(path, value)
            self.dispatch()
            self.assertEqual(self.sent[-1][1], "failure")
        count = len(self.sent)
        for instant in (NOW + SECOND, NOW - SECOND):
            self.record(now_ns=instant)
            self.dispatch()
            self.assertEqual(len(self.sent), count)
        path.unlink()
        path.symlink_to(self.source / "backup.json")
        self.dispatch()
        self.assertEqual(len(self.sent), count)

    def test_failure_of_one_transport_preserves_other_deliveries_and_is_retried_next_tick(self):
        def fail_first(path, stage):
            if path.startswith("/00000000"):
                raise OpsError("synthetic failure")
            self.send(path, stage)

        with patch("heartbeat.post_signal", fail_first):
            self.assertFalse(heartbeat.courier(self.config, self.credentials, self.source, self.state, uid=self.uid, source_uid=self.uid, now_ns=NOW))
        self.assertEqual(len(self.sent), 3)
        self.dispatch()
        self.assertEqual(len(self.sent), 4)
        self.dispatch()
        self.assertEqual(len(self.sent), 4)

    def test_credentials_reject_other_hosts_queries_project_keys_http_symlinks_or_public_modes(self):
        path = self.credentials / "monitor"
        values = [
            "http://hc-ping.com/00000000-aaaa-bbbb-cccc-dddddddddddd",
            "https://example.org/00000000-aaaa-bbbb-cccc-dddddddddddd",
            "https://hc-ping.com/project-key/job",
            "https://hc-ping.com/00000000-aaaa-bbbb-cccc-dddddddddddd?secret=1",
            "https://hc-ping.com/00000000-aaaa-bbbb-cccc-dddddddddddd\r\nX-Key: value",
            "x" * 200,
        ]
        for value in values:
            self.file(path, value)
            with self.subTest(value=value), self.assertRaises(OpsError):
                heartbeat.credential(path, uid=self.uid)
        self.file(path, "https://hc-ping.com/00000000-aaaa-bbbb-cccc-dddddddddddd")
        path.chmod(0o644)
        with self.assertRaises(OpsError):
            heartbeat.credential(path, uid=self.uid)
        path.unlink()
        path.symlink_to(self.credentials / "backup")
        with self.assertRaises(OpsError):
            heartbeat.credential(path, uid=self.uid)

    def test_policy_requires_four_separate_checks_and_bounded_deadlines(self):
        with self.assertRaises(OpsError):
            heartbeat.check_policy({"schema_version": 1, "checks": {}})
        self.config["checks"]["monitor"]["runtime_seconds"] = True
        with self.assertRaises(OpsError):
            self.dispatch()
        self.config["checks"]["monitor"]["runtime_seconds"] = 300
        (self.credentials / "monitor").write_text((self.credentials / "backup").read_text())
        with self.assertRaises(OpsError):
            self.dispatch()
        self.assertEqual(self.sent, [])

    def test_wrapper_runs_job_once_and_preserves_exit_when_status_recording_fails(self):
        missing = self.root / "missing"
        output = io.StringIO()
        for code in (0, 7, -15):
            with patch.object(WRAPPER.subprocess, "run", return_value=subprocess.CompletedProcess(["fixture"], code)) as run, contextlib.redirect_stderr(output):
                result = WRAPPER.run_job("collector", ["/synthetic/job"], missing, uid=self.uid)
            self.assertEqual(result, code if code >= 0 else 128 - code)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.kwargs, {"check": False})
        self.assertNotIn("/synthetic", output.getvalue())

    def test_wrapper_real_process_success_failure_and_missing_executable(self):
        for code in (0, 23):
            self.assertEqual(WRAPPER.run_job("backup", [sys.executable, "-c", f"raise SystemExit({code})"], self.source, uid=self.uid), code)
            status = json.loads((self.source / "backup.json").read_text())
            self.assertEqual(status["stage"], "success" if code == 0 else "failure")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(WRAPPER.run_job("offhost", ["/nonexistent/synthetic-copy"], self.source, uid=self.uid), 127)
        self.assertEqual(json.loads((self.source / "offhost.json").read_text())["stage"], "failure")

    def test_atomic_status_has_only_generic_lifecycle_fields_and_read_group(self):
        path = self.source / "monitor.json"
        value = json.loads(path.read_text())
        self.assertEqual(set(value), {"schema_version", "job", "run_id", "stage", "recorded_ns"})
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(self.source.glob(".*")), [])

    def test_existing_job_sandboxes_are_preserved_and_courier_has_no_origin_grants(self):
        for job in ("monitor", "backup"):
            unit = (OPS / f"buycycle-{job}.service").read_text()
            self.assertIn("IPAddressDeny=any", unit)
            self.assertIn("IPAddressAllow=localhost", unit)
            self.assertIn("job-status.py --job", unit)
        self.assertIn("RestrictAddressFamilies=AF_UNIX\n", (OPS / "buycycle-collect.service").read_text())
        unit = (OPS / "buycycle-heartbeat.service").read_text()
        self.assertIn("User=buycycle-heartbeat", unit)
        self.assertEqual(unit.count("LoadCredential="), 5)
        self.assertNotIn("Environment=", unit)
        self.assertNotIn("SupplementaryGroups=", unit)


class TransportTests(unittest.TestCase):
    def test_timeout_retries_are_bounded_and_proxy_environment_is_not_used(self):
        connections = []

        def connection(*args, **kwargs):
            self.assertEqual(args, ("hc-ping.com",))
            self.assertEqual(kwargs["timeout"], 5)
            value = unittest.mock.Mock()
            value.request.side_effect = TimeoutError("synthetic secret-url must not escape")
            connections.append(value)
            return value

        with patch("heartbeat.HTTPSConnection", connection), self.assertRaisesRegex(OpsError, "^Heartbeat transport unavailable$"):
            heartbeat.post_signal("/synthetic", "failure")
        self.assertEqual(len(connections), 2)
        self.assertTrue(all(value.close.called for value in connections))

    def test_real_loopback_tls_path_empty_body_and_redirect_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key, cert = root / "key.pem", root / "cert.pem"
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-keyout",
                    str(key),
                    "-out",
                    str(cert),
                    "-days",
                    "1",
                    "-subj",
                    "/CN=localhost",
                    "-addext",
                    "subjectAltName=DNS:localhost",
                ],
                capture_output=True,
                check=True,
                timeout=30,
            )
            received = []
            response_status = [200]

            class Handler(http.server.BaseHTTPRequestHandler):
                def do_POST(self):
                    received.append((self.path, self.rfile.read(int(self.headers.get("Content-Length", "0")))))
                    self.send_response(response_status[0])
                    self.send_header("Location", "https://must-never-contact.invalid/")
                    self.end_headers()
                    self.wfile.write(b"OK")

                def log_message(self, *args):
                    pass

            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            real_connection = http.client.HTTPSConnection

            def loopback(host, **kwargs):
                self.assertEqual(host, "hc-ping.com")
                self.assertEqual(kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
                return real_connection("localhost", server.server_port, timeout=kwargs["timeout"], context=ssl.create_default_context(cafile=str(cert)))

            try:
                with patch("heartbeat.HTTPSConnection", loopback):
                    heartbeat.post_signal("/fixture-check", "success")
                    heartbeat.post_signal("/fixture-check", "start")
                    heartbeat.post_signal("/fixture-check", "failure")
                    response_status[0] = 302
                    with self.assertRaisesRegex(OpsError, "not acknowledged"):
                        heartbeat.post_signal("/fixture-check", "success")
                self.assertEqual(received, [("/fixture-check", b""), ("/fixture-check/start", b""), ("/fixture-check/fail", b""), ("/fixture-check", b"")])
                # The default trust store must reject this synthetic self-signed
                # server; only the test's explicitly trusted CA succeeds above.
                with (
                    self.assertRaises(ssl.SSLCertVerificationError),
                    ssl.create_default_context().wrap_socket(socket.create_connection(("127.0.0.1", server.server_port)), server_hostname="localhost"),
                ):
                    pass
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
