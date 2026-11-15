#!/usr/bin/env python3
"""One-command local production build with disposable PG and synthetic Access."""

from __future__ import annotations

import os
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTAINER = "buycycle-local-postgres"
URL = "postgres://postgres:buycycle-local-fixture@127.0.0.1:5550/buycycle_local"


def run(*args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=ROOT, env=env, check=True)


def main() -> None:
    env = dict(
        os.environ,
        DATABASE_URL=URL,
        MIGRATION_DATABASE_URL=URL,
        BUYCYCLE_LOCAL_SEED="1",
        BUYCYCLE_ENV="local",
        BUYCYCLE_FIXTURE="1",
        BUYCYCLE_BIND="127.0.0.1:8088",
        ACCESS_ISSUER="http://127.0.0.1:9090",
        ACCESS_AUDIENCE="buycycle-local",
        ACCESS_ALLOWED_EMAILS="owner@example.test",
        BUYCYCLE_COLLECTION_ENABLED="false",
        NX_DAEMON="false",
        NX_ISOLATE_PLUGINS="false",
    )
    env["CARGO_INCREMENTAL"] = "0"
    pq = Path("/opt/homebrew/opt/libpq/lib")
    if pq.exists():
        env["PQ_LIB_DIR"] = str(pq)
        env["LIBRARY_PATH"] = str(pq) + (":" + env["LIBRARY_PATH"] if env.get("LIBRARY_PATH") else "")
    existing = subprocess.run(["docker", "inspect", CONTAINER, "--format", '{{index .Config.Labels "com.f0rge.fixture"}}'], capture_output=True, text=True, check=False)
    if existing.returncode == 0:
        if existing.stdout.strip() != "buycycle-local":
            raise SystemExit("Refusing a container not owned by this local fixture")
        run("docker", "start", CONTAINER)
    else:
        run(
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER,
            "--label",
            "com.f0rge.fixture=buycycle-local",
            "-e",
            "POSTGRES_PASSWORD=buycycle-local-fixture",
            "-e",
            "POSTGRES_DB=buycycle_local",
            "-p",
            "127.0.0.1:5550:5432",
            "-v",
            "buycycle-local-data:/var/lib/postgresql/data",
            "postgres:17-bookworm",
        )
    for _ in range(60):
        if subprocess.run(["docker", "exec", CONTAINER, "pg_isready", "-U", "postgres", "-d", "buycycle_local"], capture_output=True, check=False).returncode == 0:
            break
        time.sleep(0.5)
    else:
        raise SystemExit("Local PostgreSQL did not become ready")
    run("npx", "nx", "run", "buycycle-backend:build", env=env)
    binaries = ROOT / "target/nx/buycycle-backend/debug"
    run(str(binaries / "migrate"), env=env)
    run(str(binaries / "seed"), env=env)
    run("npm", "run", "codegen", "--workspace", "apps/buycycle/frontend", env=env)
    run("npx", "nx", "run", "buycycle-frontend:build", env=env)
    children: list[subprocess.Popen[bytes]] = []

    def stop(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        children.append(subprocess.Popen(["node", "apps/buycycle/ops/local-access.mjs"], cwd=ROOT, env=env))
        for _ in range(60):
            try:
                urllib.request.urlopen("http://127.0.0.1:9090/cdn-cgi/access/certs", timeout=1).close()
                break
            except OSError:
                time.sleep(0.2)
        children.append(subprocess.Popen([str(binaries / "buycycle-backend"), "serve"], cwd=ROOT, env=env))
        print("Local production build: http://127.0.0.1:8090 (synthetic identity/data only).", flush=True)
        print("Ctrl-C stops the app and identity fixture; local PostgreSQL data is retained.", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(1)
        raise SystemExit("A local application process stopped unexpectedly")
    except KeyboardInterrupt:
        pass
    finally:
        for child in reversed(children):
            child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
