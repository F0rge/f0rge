"""Exercise the private operations boundary without production credentials.

TLS tests use the real HTTP handler and ephemeral certificates on loopback. Only
the final apply callback is a fake. Filesystem ownership fixtures represent an
installed root-managed tree; they are not evidence of installation on the Pi.
Compose config is parsed by Docker without starting containers or networks.
"""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import importlib.util
import io
import json
import os
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

OPS = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("buycycle_release_agent_ops_test", OPS / "release-agent.py")
AGENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AGENT)
IDENTITY = "spiffe://f0rge/buycycle/release-requester"


def run(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=30, **kwargs)


class RequestIdentityTests(unittest.TestCase):
    def test_only_positive_run_id_and_canonical_uuid_are_accepted(self):
        identity = "12345678-1234-4abc-8def-123456789abc"
        self.assertEqual(AGENT.request_identity({"release_run_id": 42, "request_id": identity}), (42, identity))
        for body in [
            None,
            [],
            {},
            {"release_run_id": True, "request_id": identity},
            {"release_run_id": 0, "request_id": identity},
            {"release_run_id": "42", "request_id": identity},
            {"release_run_id": 42, "request_id": identity.upper()},
            {"release_run_id": 42, "request_id": "not-a-uuid"},
        ]:
            with self.subTest(body=body), self.assertRaises((TypeError, ValueError)):
                AGENT.request_identity(body)
        for key in ("image", "path", "command", "env", "receipt", "policy"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                AGENT.request_identity({"release_run_id": 42, "request_id": identity, key: "forbidden"})

    def test_non_managed_user_path_and_relative_path_are_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text("{}")
            if os.getuid() != 0:
                with self.assertRaises(ValueError):
                    AGENT.trusted_file(path)
            with self.assertRaises(ValueError):
                AGENT.trusted_file(Path("relative-policy.json"))

    def test_managed_metadata_rejects_symlink_and_writable_ancestors(self):
        leaf = Path("/managed/policy.json")

        def metadata(path):
            mode = stat.S_IFREG | 0o600 if path == leaf else stat.S_IFDIR | 0o755
            return os.stat_result((mode, 1, 1, 1, 0, 0, 0, 0, 0, 0))

        with patch.object(Path, "lstat", metadata):
            AGENT.trusted_file(leaf)
        for bad_mode in (stat.S_IFLNK | 0o777, stat.S_IFDIR | 0o775, stat.S_IFDIR | 0o757):

            def bad_metadata(path, bad_mode=bad_mode):
                if path == Path("/managed"):
                    return os.stat_result((bad_mode, 1, 1, 1, 0, 0, 0, 0, 0, 0))
                return metadata(path)

            with self.subTest(mode=oct(bad_mode)), patch.object(Path, "lstat", bad_metadata), self.assertRaises(ValueError):
                AGENT.trusted_file(leaf)

    def test_root_managed_server_key_must_also_be_owner_only(self):
        # Main must stop before loading the module or opening a socket. Only
        # filesystem ownership metadata is substituted for this installation test.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            key, token, policy_path = root / "server.key", root / "github_token", root / "policy.json"
            key.write_text("synthetic-key-not-a-certificate")
            key.chmod(0o644)
            token.write_text("synthetic-read-token")
            token.chmod(0o600)
            policy_path.write_text(json.dumps({"agent_bind": "127.0.0.1", "server_key": str(key), "server_cert": str(key), "client_ca": str(key)}))
            actual_lstat = Path.lstat

            def metadata(path):
                try:
                    values = list(actual_lstat(path))
                except FileNotFoundError:
                    values = [stat.S_IFREG | 0o600, 1, 1, 1, 0, 0, 0, 0, 0, 0]
                values[0] &= ~0o022
                values[4] = 0
                return os.stat_result(values)

            with (
                patch.object(Path, "lstat", metadata),
                patch.object(sys, "argv", ["release-agent", "--policy", str(policy_path)]),
                patch.dict(os.environ, {"CREDENTIALS_DIRECTORY": str(root)}),
                patch.object(ssl, "SSLContext") as context,
                self.assertRaisesRegex(ValueError, "private key"),
            ):
                AGENT.main()
            context.assert_not_called()


class MutualTLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("openssl"):
            raise RuntimeError("OpenSSL is required for the mTLS boundary checks")
        cls.temp = tempfile.TemporaryDirectory(prefix="buycycle-mtls-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.root.chmod(0o700)
        previous = os.umask(0o077)
        try:
            for ca in ("trusted", "untrusted"):
                run(
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "ec",
                    "-pkeyopt",
                    "ec_paramgen_curve:P-256",
                    "-sha256",
                    "-nodes",
                    "-days",
                    "1",
                    "-subj",
                    "/CN=Buycycle ephemeral " + ca,
                    "-addext",
                    "basicConstraints=critical,CA:TRUE",
                    "-keyout",
                    str(cls.root / (ca + ".key")),
                    "-out",
                    str(cls.root / (ca + ".crt")),
                )
            cls.certificate("server", "trusted", "serverAuth", "IP:127.0.0.1")
            cls.certificate("allowed", "trusted", "clientAuth", "URI:" + IDENTITY)
            cls.certificate("wrong-identity", "trusted", "clientAuth", "URI:spiffe://f0rge/another-agent")
            cls.certificate("wrong-ca", "untrusted", "clientAuth", "URI:" + IDENTITY)
            for path in cls.root.iterdir():
                path.chmod(0o600)
        finally:
            os.umask(previous)

    @classmethod
    def certificate(cls, name, ca, usage, san):
        run(
            "openssl",
            "req",
            "-newkey",
            "ec",
            "-pkeyopt",
            "ec_paramgen_curve:P-256",
            "-nodes",
            "-subj",
            "/CN=" + name,
            "-keyout",
            str(cls.root / (name + ".key")),
            "-out",
            str(cls.root / (name + ".csr")),
        )
        ext = cls.root / (name + ".ext")
        ext.write_text("basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=" + usage + "\nsubjectAltName=" + san + "\n")
        run(
            "openssl",
            "x509",
            "-req",
            "-in",
            str(cls.root / (name + ".csr")),
            "-CA",
            str(cls.root / (ca + ".crt")),
            "-CAkey",
            str(cls.root / (ca + ".key")),
            "-CAcreateserial",
            "-days",
            "1",
            "-sha256",
            "-extfile",
            str(ext),
            "-out",
            str(cls.root / (name + ".crt")),
        )

    def setUp(self):
        self.calls = []
        self.failure = False
        self.logs = io.StringIO()
        self.log_capture = contextlib.redirect_stdout(self.logs)
        self.log_capture.__enter__()
        self.addCleanup(self.log_capture.__exit__, None, None, None)
        self.policy = {"client_identity": IDENTITY}

        def fake_apply(run_id, request_id, policy):
            self.calls.append((run_id, request_id, policy))
            if self.failure:
                raise RuntimeError("secret-do-not-disclose DATABASE_URL=synthetic")
            return {"state": "verified", "release_run_id": run_id, "request_id": request_id}

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_cert_chain(str(self.root / "server.crt"), str(self.root / "server.key"))
        context.load_verify_locations(cafile=str(self.root / "trusted.crt"))
        self.server = AGENT.ReleaseServer(("127.0.0.1", 0), AGENT.handler(self.policy, fake_apply), context, io_timeout=0.5)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def client_context(self, name="allowed"):
        context = ssl.create_default_context(cafile=str(self.root / "trusted.crt"))
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        if name:
            context.load_cert_chain(str(self.root / (name + ".crt")), str(self.root / (name + ".key")))
        return context

    def request(self, body, *, client="allowed", path="/v1/releases", method="POST"):
        connection = http.client.HTTPSConnection("127.0.0.1", self.server.server_port, context=self.client_context(client), timeout=3)
        try:
            connection.request(method, path, body=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def valid_body(self):
        return {"release_run_id": 42, "request_id": str(uuid.uuid4())}

    def test_exact_request_over_real_mutual_tls_invokes_apply_once(self):
        body = self.valid_body()
        status, response = self.request(body)
        self.assertEqual(status, 200)
        self.assertEqual(response, dict(body, state="verified"))
        self.assertEqual(self.calls, [(42, body["request_id"], self.policy)])

    def test_stalled_unauthenticated_tls_does_not_block_another_client(self):
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=2) as stalled:
            status, response = self.request(self.valid_body())
            self.assertEqual(status, 200)
            self.assertEqual(response["state"], "verified")
            stalled.settimeout(2)
            self.assertEqual(stalled.recv(1), b"")

    def test_stalled_headers_time_out_without_reaching_apply(self):
        with (
            socket.create_connection(("127.0.0.1", self.server.server_port), timeout=2) as plain,
            self.client_context().wrap_socket(plain, server_hostname="127.0.0.1") as secured,
        ):
            secured.sendall(b"POST /v1/releases HTTP/1.1\r\nHost: localhost\r\n")
            secured.settimeout(2)
            self.assertEqual(secured.recv(1), b"")
        self.assertEqual(self.calls, [])

    def test_missing_or_untrusted_client_certificate_never_reaches_apply(self):
        for client in (None, "wrong-ca"):
            with self.subTest(client=client), self.assertRaises((ssl.SSLError, ConnectionError, http.client.RemoteDisconnected)):
                self.request(self.valid_body(), client=client)
            self.assertEqual(self.calls, [])

    def test_trusted_certificate_with_wrong_uri_is_denied(self):
        status, response = self.request(self.valid_body(), client="wrong-identity")
        self.assertEqual((status, response), (403, {"error": "release identity denied"}))
        self.assertEqual(self.calls, [])

    def test_unknown_fields_paths_and_methods_never_reach_apply(self):
        for key in ("image", "path", "command", "environment", "receipt", "policy"):
            with self.subTest(key=key):
                status, _ = self.request(dict(self.valid_body(), **{key: "arbitrary"}))
                self.assertEqual(status, 409)
                self.assertEqual(self.calls, [])
        for path in ("/v1/releases?image=other", "/commands"):
            status, _ = self.request(self.valid_body(), path=path)
            self.assertEqual(status, 400)
        status, _ = self.request({}, method="GET")
        self.assertEqual(status, 405)
        self.assertEqual(self.calls, [])

    def test_duplicate_length_or_transfer_encoding_is_denied(self):
        body = json.dumps(self.valid_body()).encode()
        for extra in ("Content-Length: " + str(len(body)), "Transfer-Encoding: chunked"):
            with (
                self.subTest(header=extra),
                socket.create_connection(("127.0.0.1", self.server.server_port), timeout=3) as plain,
                self.client_context().wrap_socket(plain, server_hostname="127.0.0.1") as secured,
            ):
                headers = (
                    "POST /v1/releases HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n"
                    "Content-Length: " + str(len(body)) + "\r\n" + extra + "\r\nConnection: close\r\n\r\n"
                )
                secured.sendall(headers.encode() + body)
                response = http.client.HTTPResponse(secured)
                response.begin()
                self.assertEqual(response.status, 400)
                self.assertEqual(json.loads(response.read()), {"error": "request framing denied"})
        self.assertEqual(self.calls, [])

    def test_apply_failure_is_generic_in_response_and_logs(self):
        self.failure = True
        body = self.valid_body()
        status, response = self.request(body)
        self.assertEqual(status, 409)
        self.assertEqual(response, {"error": "release verification failed", "request_id": body["request_id"]})
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("secret-do-not-disclose", self.logs.getvalue())
        self.assertNotIn("DATABASE_URL", self.logs.getvalue())


class ComposeAndEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("docker"):
            raise RuntimeError("Docker Compose is required to parse the production configuration")
        cls.temp = tempfile.TemporaryDirectory(prefix="buycycle-compose-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        envfile = root / "fixture.env"
        cls.image = "ghcr.io/f0rge/buycycle@sha256:" + "a" * 64
        envfile.write_text(
            "BUYCYCLE_IMAGE=" + cls.image + "\nACCESS_ISSUER=https://synthetic.cloudflareaccess.com\n"
            "ACCESS_AUDIENCE=synthetic-audience\nACCESS_ALLOWED_EMAILS=owner@example.test\n"
            "BUYCYCLE_DATABASE_NETWORK=buycycle-synthetic-existing-network\nBUYCYCLE_SECRETS_DIR=" + str(root / "secrets") + "\n"
        )
        result = run(
            "docker",
            "compose",
            "--env-file",
            str(envfile),
            "--file",
            str(OPS / "compose.yml"),
            "--profile",
            "*",
            "config",
            "--format",
            "json",
            env={"PATH": os.environ["PATH"]},
        )
        cls.config = json.loads(result.stdout)

    def test_private_origin_and_application_credentials_are_separate(self):
        services = self.config["services"]
        self.assertLessEqual({"app", "postgres", "migrate", "tunnel"}, set(services))
        self.assertLessEqual(set(services), {"app", "postgres", "migrate", "tunnel", "collector"})
        for name, service in services.items():
            with self.subTest(service=name):
                ports = service.get("ports", [])
                if name == "postgres":
                    self.assertLessEqual(len(ports), 1)
                    for port in ports:
                        self.assertEqual(port["host_ip"], "127.0.0.1")
                        self.assertEqual(str(port["published"]), "5547")
                        self.assertEqual(port["target"], 5432)
                        self.assertEqual(port["protocol"], "tcp")
                else:
                    self.assertFalse(ports)
                self.assertNotIn("docker.sock", json.dumps(service))
        self.assertEqual(services["app"]["image"], self.image)
        self.assertEqual({s["source"] for s in services["app"]["secrets"]}, {"runtime_database_url"})
        self.assertEqual({s["source"] for s in services["migrate"]["secrets"]}, {"migrator_database_url"})
        self.assertEqual({s["source"] for s in services["tunnel"]["secrets"]}, {"tunnel_token"})
        environment = services["app"]["environment"]
        self.assertEqual(environment["BUYCYCLE_COLLECTION_ENABLED"], "0")
        self.assertNotIn("BUYCYCLE_ENV", environment)
        self.assertNotIn("MIGRATION_DATABASE_URL", environment)
        self.assertNotIn("DATABASE_URL", environment)
        self.assertTrue(environment["ACCESS_ISSUER"].startswith("https://"))
        self.assertTrue(self.config["networks"]["origin"]["internal"])
        self.assertTrue(self.config["networks"]["data"]["external"])

    def test_postgres_bootstrap_and_schema_migration_are_explicit_profiles(self):
        services = self.config["services"]
        self.assertEqual(services["postgres"]["profiles"], ["bootstrap-cluster"])
        self.assertEqual(services["migrate"]["profiles"], ["maintenance"])
        self.assertEqual(services["migrate"]["command"], ["migrate", "--grant-runtime"])
        self.assertFalse(services["app"].get("depends_on", {}).get("postgres"))
        for name in ("app", "migrate", "tunnel"):
            service = services[name]
            self.assertIs(service["read_only"], True)
            self.assertEqual(service["cap_drop"], ["ALL"])
            self.assertIn("no-new-privileges:true", service["security_opt"])

    def test_entrypoint_selects_secret_files_without_evaluating_or_logging_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, migrator = root / "runtime secret", root / "migrator secret"
            values = {
                "DATABASE_URL": "postgres://runtime:synthetic-$(touch SHOULD_NOT_EXIST)@db/app",
                "MIGRATION_DATABASE_URL": "postgres://migrator:synthetic-`touch SHOULD_NOT_EXIST`@db/app",
            }
            runtime.write_text(values["DATABASE_URL"])
            migrator.write_text(values["MIGRATION_DATABASE_URL"])
            probe = "import hashlib,json,os; print(json.dumps({k:hashlib.sha256(os.environ.get(k,'').encode()).hexdigest() for k in ('DATABASE_URL','MIGRATION_DATABASE_URL')}))"
            for selected in ("runtime", "migrator", "both"):
                environment = {"PATH": os.environ["PATH"]}
                expected = dict.fromkeys(values, hashlib.sha256(b"").hexdigest())
                if selected in ("runtime", "both"):
                    environment["BUYCYCLE_DATABASE_URL_FILE"] = str(runtime)
                    expected["DATABASE_URL"] = hashlib.sha256(values["DATABASE_URL"].encode()).hexdigest()
                if selected in ("migrator", "both"):
                    environment["BUYCYCLE_MIGRATION_DATABASE_URL_FILE"] = str(migrator)
                    expected["MIGRATION_DATABASE_URL"] = hashlib.sha256(values["MIGRATION_DATABASE_URL"].encode()).hexdigest()
                result = run("sh", str(OPS / "entrypoint.sh"), sys.executable, "-c", probe, env=environment, cwd=root)
                self.assertEqual(json.loads(result.stdout), expected)
                self.assertEqual(result.stderr, "")
                self.assertFalse((root / "SHOULD_NOT_EXIST").exists())
                self.assertNotIn("synthetic-", result.stdout)

    def test_missing_secret_fails_before_command_and_shell_scripts_parse(self):
        result = subprocess.run(
            ["sh", str(OPS / "entrypoint.sh"), "printf", "COMMAND_RAN"],
            env={"PATH": os.environ["PATH"], "BUYCYCLE_DATABASE_URL_FILE": "/not-a-buycycle-secret"},
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("COMMAND_RAN", result.stdout)
        run("sh", "-n", str(OPS / "entrypoint.sh"))
        run("bash", "-n", str(OPS / "init-db.sh"))


if __name__ == "__main__":
    unittest.main()
