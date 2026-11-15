#!/usr/bin/env python3
"""Narrow mTLS transport for the fixed, verified Buycycle promotion helper.

No image, command, environment, path or receipt is accepted from a caller.
Installation/credentials and production use require the release authorization.
"""

from __future__ import annotations

import argparse
import http.server
import importlib.util
import ipaddress
import json
import os
import ssl
import stat
import subprocess
import sys
import threading
import uuid
from pathlib import Path


class ReleaseServer(http.server.ThreadingHTTPServer):
    """Keep unauthenticated TLS/slow headers out of the accepting thread."""

    daemon_threads = True

    def __init__(self, address, request_handler, context, *, io_timeout=10, max_clients=8):
        self.context = context
        self.io_timeout = io_timeout
        self.clients = threading.BoundedSemaphore(max_clients)
        super().__init__(address, request_handler)

    def process_request(self, request, client_address):
        if not self.clients.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except (OSError, RuntimeError):
            self.clients.release()
            self.shutdown_request(request)
            raise

    def process_request_thread(self, request, client_address):
        try:
            request.settimeout(self.io_timeout)
            # Handshake happens only in this bounded worker, never in accept().
            with self.context.wrap_socket(request, server_side=True) as secured:
                super().process_request_thread(secured, client_address)
        except OSError:
            self.shutdown_request(request)
        finally:
            self.clients.release()


def trusted_file(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("An absolute, non-symlink managed file is required")
    for parent in [path, *path.parents]:
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ValueError("Managed release files and ancestors must be root-owned and protected")


def request_identity(payload: object) -> tuple[int, str]:
    if not isinstance(payload, dict) or set(payload) != {"release_run_id", "request_id"}:
        raise ValueError("Only a GitHub run ID and request UUID are accepted")
    run_id, request_id = payload["release_run_id"], payload["request_id"]
    if type(run_id) is not int or run_id < 1 or not isinstance(request_id, str):
        raise ValueError("Invalid release identity")
    if str(uuid.UUID(request_id)) != request_id:
        raise ValueError("A canonical request UUID is required")
    return run_id, request_id


def handler(policy: dict, apply):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "BuycycleReleaseAgent"
        sys_version = ""

        def log_message(self, *_args):
            pass

        def respond(self, status: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            request_id = "unparsed"
            try:
                peer = self.connection.getpeercert()
                if ("URI", policy["client_identity"]) not in peer.get("subjectAltName", []):
                    self.respond(403, {"error": "release identity denied"})
                    return
                if self.path != "/v1/releases" or self.headers.get("Content-Type") != "application/json":
                    self.respond(400, {"error": "release request denied"})
                    return
                if len(self.headers.get_all("Content-Length", [])) != 1 or self.headers.get("Transfer-Encoding"):
                    self.respond(400, {"error": "request framing denied"})
                    return
                length = int(self.headers["Content-Length"])
                if not 1 <= length <= 2048:
                    raise ValueError("Invalid body length")
                self.connection.settimeout(10)
                run_id, request_id = request_identity(json.loads(self.rfile.read(length)))
                receipt = apply(run_id, request_id, policy)
                self.respond(200, receipt)
                print(json.dumps({"event": "release_verified", "request_id": request_id}), flush=True)
            except (ValueError, TypeError, KeyError, OSError, RuntimeError, subprocess.SubprocessError):
                self.respond(409, {"error": "release verification failed", "request_id": request_id})
                print(json.dumps({"event": "release_refused", "request_id": request_id}), flush=True)

        def do_GET(self) -> None:
            self.respond(405, {"error": "release requests require POST and mTLS identity"})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    trusted_file(args.policy)
    policy = json.loads(args.policy.read_text())
    credential_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    if not credential_dir:
        raise ValueError("A managed short-lived GitHub read credential is required")
    github_token = Path(credential_dir) / "github_token"
    trusted_file(github_token)
    os.environ["GH_TOKEN"] = github_token.read_text().strip()
    if not os.environ["GH_TOKEN"]:
        raise ValueError("GitHub credential is empty")
    bind = ipaddress.ip_address(policy["agent_bind"])
    if not (bind.is_loopback or bind in ipaddress.ip_network("100.64.0.0/10")):
        raise ValueError("Release agent must bind loopback or its tailnet address")
    helper = Path("/opt/f0rge/.github/deploy/buycycle_release.py")
    trusted_file(helper)
    for key in ["server_cert", "server_key", "client_ca"]:
        trusted_file(Path(policy[key]))
    if Path(policy["server_key"]).stat().st_mode & 0o077:
        raise ValueError("Server private key must be readable only by its owner")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(policy["server_cert"], policy["server_key"])
    context.load_verify_locations(cafile=policy["client_ca"])
    spec = importlib.util.spec_from_file_location("buycycle_release", helper)
    sys.path.insert(0, str(helper.parent))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    server = ReleaseServer((str(bind), 8675), handler(policy, module.agent_apply), context)
    server.serve_forever()


if __name__ == "__main__":
    main()
