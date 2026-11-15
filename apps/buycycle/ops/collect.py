"""Thin protected dispatcher; the Rust collector owns locks, quotas and work."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from ops_common import OpsError, commit, positive, protected_path, read_config, require_root, safe_environment

TARGET = {"host": "pi", "app": "xi0qwpbyl2d8gf8u3xl13jkv"}


def compose_command(config: dict, *, uid: int = 0) -> tuple[list[str], dict[str, str]]:
    docker = protected_path(config["docker"], uid=uid)
    compose = protected_path(config["compose_file"], uid=uid)
    env_file = protected_path(config["env_file"], uid=uid, mode=0o600)
    environment = safe_environment()
    environment["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    return [str(docker), "compose", "--project-name", "buycycle", "--env-file", str(env_file), "--file", str(compose)], environment


def collect(config: dict, *, uid: int = 0) -> None:
    source_commit = commit(config.get("source_commit"))
    image = config.get("image")
    if not isinstance(image, str) or not re.fullmatch(r"ghcr\.io/f0rge/buycycle@sha256:[0-9a-f]{64}", image):
        raise OpsError("The approved immutable Buycycle image is required")
    activation = read_config(Path(config["activation_file"]), uid=uid)
    required = {"enabled": True, "legacy_scheduler_disabled": True, "budget_import_verified": True, "source_commit": source_commit, "image": image}
    if any(activation.get(key) != value for key, value in required.items()):
        raise OpsError("Collection remains held until approved cutover, legacy scheduler fencing and quota import are verified")
    command, environment = compose_command(config, uid=uid)
    active_path = protected_path(config["active_release_receipt"], uid=uid, mode=0o600)
    active_bytes = active_path.read_bytes()
    if activation.get("active_release_sha256") != hashlib.sha256(active_bytes).hexdigest():
        raise OpsError("Collection activation is not bound to the exact verified release receipt")
    active = json.loads(active_bytes)
    if (
        not isinstance(active, dict)
        or active.get("version") != 1
        or active.get("state") != "verified"
        or active.get("target") != TARGET
        or active.get("commit") != source_commit
        or active.get("image") != image
    ):
        raise OpsError("Collection remains held until a verified active release matches activation")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", active.get("image_id", "")) or not isinstance(active.get("docker_engine_id"), str) or not active["docker_engine_id"]:
        raise OpsError("The active release lacks local artifact or Docker engine identity")
    for path_key, receipt_key in (("compose_file", "compose_sha256"), ("env_file", "managed_env_sha256")):
        with Path(config[path_key]).open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if active.get(receipt_key) != digest:
            raise OpsError("Managed runtime files no longer match the verified release")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", active.get("config_digest", "")):
        raise OpsError("The active release lacks tested image configuration identity")
    approved_receipts = active.get("receipt_hashes", {})
    for kind in ("provider", "migration"):
        receipt_file = protected_path(config[f"{kind}_receipt"], uid=uid, mode=0o600)
        content = receipt_file.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if approved_receipts.get(kind) != digest or activation.get(f"{kind}_receipt_sha256") != digest:
            raise OpsError("Collector safety evidence differs from the exact approved cutover receipts")
        receipt = json.loads(content)
        if receipt.get("passed") is not True or receipt.get("commit") != source_commit or receipt.get("target") != TARGET:
            raise OpsError("Collector requires passing provider and migration evidence for this release")
        if kind == "provider" and (
            not all(
                receipt.get(key) is True
                for key in (
                    "legacy_collector_fenced",
                    "source_builds_disabled",
                    "origin_unpublished",
                    "access_policy_verified",
                    "database_grants_verified",
                    "managed_secrets_verified",
                )
            )
            or any(receipt.get(key) != active.get(key) for key in ("docker_engine_id", "compose_sha256", "managed_env_sha256"))
        ):
            raise OpsError("Observed provider safety evidence does not match the active release")
    # The managed env is itself receipt-hashed. Only the verified image is
    # overlaid, so an older pinned value there cannot select an older job image.
    environment["BUYCYCLE_IMAGE"] = image
    environment["BUYCYCLE_COLLECTION_ENABLED"] = "true"
    docker = command[0]
    engine = subprocess.run([docker, "info", "--format", "{{json .ID}}"], env=environment, capture_output=True, check=True, timeout=15)
    if json.loads(engine.stdout) != active.get("docker_engine_id"):
        raise OpsError("The local Docker engine is not the verified release destination")
    selected = subprocess.run([*command, "ps", "--quiet", "app"], env=environment, capture_output=True, check=True, timeout=15).stdout.decode().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", selected) or selected != active.get("container_id"):
        raise OpsError("The running app no longer matches the verified release")
    inspected = subprocess.run([docker, "inspect", selected], env=environment, capture_output=True, check=True, timeout=15)
    app = json.loads(inspected.stdout)[0]
    if app.get("Image") != active.get("image_id") or app["Config"]["Image"] != image or app["State"].get("Health", {}).get("Status") != "healthy":
        raise OpsError("The running app image or health does not match the verified release")
    image_result = subprocess.run([docker, "image", "inspect", image], env=environment, capture_output=True, check=True, timeout=15)
    local_image = json.loads(image_result.stdout)[0]
    if (
        local_image.get("Id") != active.get("image_id")
        or image not in local_image.get("RepoDigests", [])
        or local_image["Config"].get("Labels", {}).get("org.opencontainers.image.revision") != source_commit
    ):
        raise OpsError("The local collector artifact does not match the verified release image")
    health = subprocess.run(
        [docker, "exec", selected, "curl", "--fail", "--silent", "--max-time", "5", "http://127.0.0.1:8080/health"], env=environment, capture_output=True, check=True, timeout=10
    )
    if json.loads(health.stdout).get("source_commit") != source_commit:
        raise OpsError("The running app source commit does not match the verified release")
    rendered = subprocess.run([*command, "--profile", "collection", "config", "--format", "json"], env=environment, capture_output=True, check=True, timeout=30)
    service = json.loads(rendered.stdout).get("services", {}).get("collector", {})
    if service.get("image") != image or service.get("command") != ["collect"] or service.get("environment", {}).get("BUYCYCLE_COLLECTION_ENABLED") != "true":
        raise OpsError("Collector configuration does not match the activated image and fixed Rust command")
    timeout = positive(config.get("timeout_seconds"), "collector timeout", maximum=86400)
    # No pull/rebuild, shell, user argv, force option or automatic retry. Rust keeps
    # PostgreSQL advisory lock and durable Luxembourg-day request budget.
    subprocess.run(
        [*command, "--profile", "collection", "run", "--rm", "--no-deps", "--pull", "never", "collector"],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=timeout,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/buycycle/collector.json"))
    args = parser.parse_args()
    try:
        require_root()
        collect(read_config(args.config))
    except (OpsError, OSError, KeyError, ValueError, subprocess.SubprocessError):
        print("Buycycle collection held or failed: verify approved activation, local image, quota ledger and scheduler fence; do not force a rerun", file=sys.stderr)
        return 1
    print("Buycycle daily Rust collector completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
