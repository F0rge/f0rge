"""Copy one verified encrypted Buycycle backup; read it back without restoring paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from heartbeat import atomic_json
from monitor import check_backup
from ops_common import OpsError, positive, protected_path, read_config, require_root, safe_environment

TAG = "buycycle-pg-v1"
HOST = "buycycle-pi"
FIXED_SSH = {
    "host": "buycycle-backup",
    "identityfile": "/etc/buycycle/offhost-ssh-key",
    "userknownhostsfile": "/etc/buycycle/offhost-known-hosts",
    "globalknownhostsfile": "/dev/null",
    "identitiesonly": "yes",
    "batchmode": "yes",
    "stricthostkeychecking": "yes",
    "passwordauthentication": "no",
    "kbdinteractiveauthentication": "no",
    "connectionattempts": "1",
    "connecttimeout": "10",
}


def bounded_file(path: Path, *, uid: int, limit: int = 8192) -> bytes:
    path = protected_path(path, uid=uid, mode=0o600)
    with path.open("rb") as source:
        value = source.read(limit + 1)
    if not value or len(value) > limit:
        raise OpsError("Off-host configuration file is empty or too large")
    return value


def connection_files(config: dict, *, uid: int) -> tuple[Path, Path, Path]:
    repository, password, ssh = (Path(config[key]) for key in ("repository_file", "password_file", "ssh_config"))
    value = bounded_file(repository, uid=uid).decode("ascii").strip()
    if not re.fullmatch(r"sftp:buycycle-backup:/[A-Za-z0-9_./-]+", value) or ".." in value.split(":", 2)[2].split("/"):
        raise OpsError("Use the fixed SSH alias and an absolute SFTP repository path")
    protected_path(password, uid=uid, mode=0o600)
    settings = {}
    for line in bounded_file(ssh, uid=uid).decode("ascii").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        pair = line.split()
        if len(pair) != 2 or pair[0].lower() in settings:
            raise OpsError("Off-host SSH policy contains duplicate or unsafe directives")
        settings[pair[0].lower()] = pair[1]
    if set(settings) != {*FIXED_SSH, "hostname", "user", "port"} or any(settings[key] != value for key, value in FIXED_SSH.items()):
        raise OpsError("Off-host SSH policy must pin identity and known hosts without commands or includes")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}", settings["hostname"]) or settings["hostname"] in {"localhost", "127.0.0.1"}:
        raise OpsError("Off-host SSH destination is invalid")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", settings["user"]) or not settings["port"].isdigit():
        raise OpsError("Off-host SSH account or port is invalid")
    positive(int(settings["port"]), "SSH port", maximum=65535)
    for key in ("identityfile", "userknownhostsfile"):
        # The files contain secrets/host keys; check metadata without parsing them.
        protected_path(settings[key], uid=uid, mode=0o600)
    return repository, password, ssh


def restic(command: list[str], *, deadline: float, limit: int = 65536, destination: Path | None = None) -> bytes:
    """Bound stdout, memory and total runtime; discard potentially sensitive stderr."""
    process = subprocess.Popen(command, env=safe_environment(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
    output = bytearray()
    size = 0
    try:
        os.set_blocking(process.stdout.fileno(), False)
        with selectors.DefaultSelector() as selector, context_destination(destination) as target:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise OpsError("Off-host verification exceeded its deadline")
                if not selector.select(min(remaining, 1)):
                    continue
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise OpsError("Off-host output exceeded its bound")
                if target is None:
                    output.extend(chunk)
                else:
                    target.write(chunk)
            remaining = deadline - time.monotonic()
            if remaining <= 0 or process.wait(timeout=remaining) != 0:
                raise OpsError("Off-host command failed; preserve the local backup")
        return bytes(output)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        process.stdout.close()


def context_destination(path: Path | None):
    # Fixed destination inside a freshly created private directory, never an
    # archived path. No tar extraction or restored symlink can escape this root.
    from contextlib import nullcontext

    return nullcontext(None) if path is None else os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb")


def copy_backup(config: dict, *, uid: int = 0) -> dict:
    repository, password, ssh = connection_files(config, uid=uid)
    binary = protected_path(config["restic"], uid=uid)
    if uid == 0 and binary != Path("/usr/bin/restic"):
        raise OpsError("Use the managed restic binary")
    # Keep filenames out of sftp.command's token grammar. No shell is used by
    # this process; restic parses this fixed option into an SSH argv.
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(ssh)):
        raise OpsError("Off-host SSH config path is invalid")
    state = protected_path(config["state_directory"], directory=True, uid=uid, mode=0o700)
    selected = check_backup(config, uid=uid)
    expected_manifest = bounded_file(selected / "manifest.json", uid=uid)
    manifest = json.loads(expected_manifest)
    maximum = positive(config["maximum_ciphertext_bytes"], "ciphertext size", maximum=8 * 1024**3)
    if type(manifest.get("bytes")) is not int or not 0 < manifest["bytes"] <= maximum:
        raise OpsError("Encrypted backup exceeds the assessed off-host size bound")
    if {path.name for path in selected.iterdir()} != {"manifest.json", "database.dump.age"}:
        raise OpsError("Off-host copy only accepts the two verified backup files")
    timeout = positive(config["timeout_seconds"], "off-host deadline", maximum=6600)
    deadline = time.monotonic() + timeout
    base = [
        str(binary),
        "--repository-file",
        str(repository),
        "--password-file",
        str(password),
        "--no-cache",
        "--option",
        f"sftp.command=/usr/bin/ssh -F {ssh} -s buycycle-backup sftp",
    ]
    run_tag = "buycycle-run-" + uuid.uuid4().hex
    raw = restic([*base, "--json", "--quiet", "backup", "--host", HOST, "--tag", TAG, "--tag", run_tag, "--", str(selected)], deadline=deadline)
    summaries = [json.loads(line) for line in raw.splitlines() if line.strip()]
    summaries = [item for item in summaries if isinstance(item, dict) and item.get("message_type") == "summary"]
    snapshot = summaries[0].get("snapshot_id") if len(summaries) == 1 else None
    if not isinstance(snapshot, str) or not re.fullmatch(r"[0-9a-f]{64}", snapshot):
        raise OpsError("Off-host backup did not return one exact snapshot")
    archived = json.loads(restic([*base, "cat", "snapshot", snapshot], deadline=deadline))
    if not isinstance(archived, dict) or archived.get("paths") != [str(selected)] or archived.get("hostname") != HOST or set(archived.get("tags", [])) != {TAG, run_tag}:
        raise OpsError("Off-host snapshot identity or paths differ from this copy")
    restored_manifest = restic([*base, "dump", snapshot, str(selected / "manifest.json")], deadline=deadline, limit=8192)
    if restored_manifest != expected_manifest:
        raise OpsError("Off-host manifest readback differs from the local backup")
    with tempfile.TemporaryDirectory(prefix="verify-", dir=state) as directory:
        restored = Path(directory) / "database.dump.age"
        restic([*base, "dump", snapshot, str(selected / "database.dump.age")], deadline=deadline, limit=manifest["bytes"], destination=restored)
        with restored.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if restored.stat().st_size != manifest["bytes"] or digest != manifest["sha256"]:
            raise OpsError("Off-host ciphertext readback failed size or hash verification")
    receipt = {
        "schema_version": 1,
        "snapshot_id": snapshot,
        "source_commit": manifest["source_commit"],
        "backup_name": selected.name,
        "ciphertext_sha256": digest,
        "manifest_sha256": hashlib.sha256(expected_manifest).hexdigest(),
        "verified_ns": time.time_ns(),
    }
    atomic_json(state / "latest.json", receipt, uid=uid)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/buycycle/offhost.json"))
    args = parser.parse_args()
    try:
        require_root()
        copy_backup(read_config(args.config))
    except (OpsError, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print("Buycycle off-host verification failed; preserve local backups and inspect protected destination, SSH trust and repository custody", file=sys.stderr)
        return 1
    print("Buycycle encrypted off-host copy read back and verified; decryption/database restoration evidence remains separate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
