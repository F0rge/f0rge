#!/usr/bin/env python3
"""Build once and test the exact ARM64 image with isolated synthetic dependencies."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NODE = "node:22-bookworm-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee"


def command(*args: str, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def config_digest(archive: Path, commit: str) -> str:
    # Docker 29's local image ID may be an OCI index, rather than its config ID.
    # Read bounded metadata directly; never extract an untrusted archive path.
    with tarfile.open(archive) as bundle:
        manifest = bundle.getmember("manifest.json")
        if not manifest.isfile() or manifest.size > 1024 * 1024:
            raise ValueError("Invalid image manifest")
        images = json.load(bundle.extractfile(manifest))
        if len(images) != 1:
            raise ValueError("Exactly one tested image is required")
        member = bundle.getmember(images[0]["Config"])
        if not member.isfile() or member.size > 1024 * 1024:
            raise ValueError("Invalid image configuration")
        raw = bundle.extractfile(member).read()
        config = json.loads(raw)
        assert config["architecture"] == "arm64" and config["os"] == "linux"
        assert config["config"]["Labels"]["org.opencontainers.image.revision"] == commit
        return "sha256:" + hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(os.environ.get("BUYCYCLE_IMAGE_OUTPUT", tempfile.gettempdir() + "/buycycle-tested-image")))
    parser.add_argument("--image", help="Test an existing image without rebuilding it")
    parser.add_argument("--allow-dirty", action="store_true", help="Exploratory local evidence only; never promotable")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise SystemExit("Artifacts must remain outside the public checkout")
    commit = command("git", "rev-parse", "HEAD", capture=True)
    dirty = bool(command("git", "status", "--porcelain", capture=True))
    if dirty and not args.allow_dirty:
        raise SystemExit("Commit the selected source before producing trusted image evidence")
    image = args.image or "f0rge-buycycle:tested-" + commit[:12]
    if not args.image:
        command(
            "docker",
            "buildx",
            "build",
            "--platform",
            "linux/arm64",
            "--load",
            "--file",
            "apps/buycycle/ops/Dockerfile",
            "--build-arg",
            "SOURCE_COMMIT=" + commit,
            "--tag",
            image,
            ".",
        )
    info = json.loads(command("docker", "image", "inspect", image, capture=True))[0]
    assert info["Architecture"] == "arm64" and info["Os"] == "linux", "Wrong target architecture"
    assert info["Config"]["Labels"]["org.opencontainers.image.revision"] == commit, "Wrong image commit"
    assert info["Config"]["User"] == "10001:10001", "Image must use the runtime identity"
    suffix = uuid.uuid4().hex[:12]
    network, anchor = "buycycle-test-net-" + suffix, "buycycle-test-pod-" + suffix
    containers: list[str] = []

    def start(name: str, *options: str) -> None:
        command("docker", "run", "-d", "--name", name, "--label", "com.f0rge.fixture=buycycle-image", *options)
        containers.append(name)

    def db_binary(binary: str, *arguments: str) -> None:
        command(
            "docker",
            "run",
            "--rm",
            "--network",
            "container:" + anchor,
            "-e",
            "MIGRATION_DATABASE_URL=postgres://buycycle_migrator:synthetic-migrator-image-only@127.0.0.1:5432/buycycle_rehearsal",
            "-e",
            "BUYCYCLE_LOCAL_SEED=1",
            image,
            binary,
            *arguments,
        )

    try:
        command("docker", "network", "create", "--internal", network)
        start(anchor, "--network", network, NODE, "node", "-e", "setInterval(()=>{}, 1000000)")
        postgres = "buycycle-test-pg-" + suffix
        start(postgres, "--network", "container:" + anchor, "-e", "POSTGRES_PASSWORD=synthetic-image-only", "-e", "POSTGRES_DB=buycycle_rehearsal", "postgres:17-bookworm")
        for _ in range(120):
            ready = subprocess.run(["docker", "exec", postgres, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "buycycle_rehearsal"], capture_output=True, check=False)
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Synthetic PostgreSQL readiness timed out")
        # The exact app image must work with the production privilege split,
        # rather than a superuser fixture masking missing runtime grants.
        subprocess.run(
            ["docker", "exec", "-i", postgres, "psql", "-U", "postgres", "-d", "buycycle_rehearsal", "-v", "ON_ERROR_STOP=1"],
            input="""
CREATE ROLE buycycle_runtime LOGIN PASSWORD 'synthetic-runtime-image-only';
CREATE ROLE buycycle_migrator LOGIN PASSWORD 'synthetic-migrator-image-only';
REVOKE ALL ON DATABASE buycycle_rehearsal FROM PUBLIC;
GRANT CONNECT ON DATABASE buycycle_rehearsal TO buycycle_runtime, buycycle_migrator;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO buycycle_runtime;
GRANT USAGE, CREATE ON SCHEMA public TO buycycle_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE buycycle_migrator IN SCHEMA public GRANT SELECT ON TABLES TO buycycle_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE buycycle_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO buycycle_runtime;
""",
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        fixture = "buycycle-test-access-" + suffix
        start(
            fixture,
            "--network",
            "container:" + anchor,
            "-e",
            "BUYCYCLE_FIXTURE=1",
            "-e",
            "FIXTURE_UPSTREAM=http://127.0.0.1:8080",
            "-v",
            str(ROOT / "apps/buycycle/ops/local-access.mjs") + ":/fixture.mjs:ro",
            NODE,
            "node",
            "/fixture.mjs",
        )
        for _ in range(60):
            result = subprocess.run(
                ["docker", "exec", anchor, "node", "-e", "fetch('http://127.0.0.1:9090/cdn-cgi/access/certs').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"],
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Synthetic Access fixture did not start")
        db_binary("migrate", "--grant-runtime")
        db_binary("seed")
        app = "buycycle-test-app-" + suffix
        start(
            app,
            "--network",
            "container:" + anchor,
            "--read-only",
            "--tmpfs",
            "/tmp:size=16m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--memory",
            "768m",
            "--cpus",
            "1",
            "-e",
            "DATABASE_URL=postgres://buycycle_runtime:synthetic-runtime-image-only@127.0.0.1:5432/buycycle_rehearsal",
            "-e",
            "BUYCYCLE_ENV=local",
            "-e",
            "ACCESS_ISSUER=http://127.0.0.1:9090",
            "-e",
            "ACCESS_AUDIENCE=buycycle-local",
            "-e",
            "ACCESS_ALLOWED_EMAILS=owner@example.test",
            "-e",
            "BUYCYCLE_COLLECTION_ENABLED=false",
            image,
        )
        raw = command(
            "docker",
            "run",
            "--rm",
            "--network",
            "container:" + anchor,
            "-e",
            "SOURCE_COMMIT=" + commit,
            "-v",
            str(ROOT / "apps/buycycle/ops/probe-image.mjs") + ":/probe.mjs:ro",
            NODE,
            "node",
            "/probe.mjs",
            capture=True,
        )
        tests = json.loads(raw.splitlines()[-1])
        assert tests and all(value is True for value in tests.values()), "Incomplete image verification"
        running = json.loads(command("docker", "inspect", app, capture=True))[0]
        assert running["Image"] == info["Id"], "Running image differs from tested candidate"
        log_result = subprocess.run(["docker", "logs", app], capture_output=True, text=True, check=True)
        logs = log_result.stdout + log_result.stderr
        for marker in ["synthetic-image-only", "synthetic-runtime-image-only", "synthetic-migrator-image-only", "owner@example.test", "BEGIN PRIVATE KEY"]:
            assert marker not in logs, "Sensitive fixture value appeared in app logs"
        tests["running_image_identity"] = True
        tests["log_redaction"] = True
        tests["restricted_runtime_role"] = True
        output.mkdir(parents=True, exist_ok=True, mode=0o700)
        archive = output / "image.tar"
        command("docker", "save", "--output", str(archive), image)
        archive.chmod(0o600)
        hasher = hashlib.sha256()
        with archive.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(block)
        digest = hasher.hexdigest()
        evidence = {
            "version": 1,
            "repository": "F0rge/f0rge",
            "commit": commit,
            "platform": "linux/arm64",
            "image_id": info["Id"],
            "config_digest": config_digest(archive, commit),
            "image_tag": image,
            "archive_sha256": digest,
            "tested": True,
            "tests": tests,
            "dirty": dirty,
            "created_at": dt.datetime.now(dt.UTC).isoformat(),
        }
        (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        (output / "evidence.json").chmod(0o600)
        print(json.dumps({"output": str(output), "image_id": info["Id"], "tested": True, "dirty": dirty}))
    finally:
        for container in reversed(containers):
            subprocess.run(["docker", "rm", "-f", "-v", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run(["docker", "network", "rm", network], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


if __name__ == "__main__":
    main()
