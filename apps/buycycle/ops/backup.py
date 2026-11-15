"""Stream a consistent PostgreSQL snapshot directly into age encryption."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ops_common import OpsError, commit, local_database, positive, protected_path, read_config, require_root


def backup(config: dict, *, uid: int = 0) -> Path:
    args, env = local_database(config, uid=uid)
    destination = protected_path(config["destination"], directory=True, uid=uid, mode=0o700)
    recipients = protected_path(config["recipients_file"], uid=uid, mode=0o600)
    keys = [line.strip() for line in recipients.read_text().splitlines() if line.strip() and not line.startswith("#")]
    if not keys or any(not re.fullmatch(r"age1[0-9a-z]{58}", key) for key in keys):
        raise OpsError("Configure approved age public recipients only; keep recovery identities offline")
    source_commit = commit(config.get("source_commit"))
    timeout = positive(config.get("timeout_seconds"), "backup timeout", maximum=86400)
    pg_dump = protected_path(config["pg_dump"], uid=uid)
    age = protected_path(config["age"], uid=uid)
    if not os.access(pg_dump, os.X_OK) or not os.access(age, os.X_OK):
        raise OpsError("Install executable PostgreSQL 17 pg_dump and age prerequisites")
    version = subprocess.run([str(pg_dump), "--version"], capture_output=True, env=env, check=True, timeout=10)
    if not re.fullmatch(rb"pg_dump \(PostgreSQL\) 17(?:\.[0-9]+)?[^\n]*\n?", version.stdout):
        raise OpsError("The controlled backup requires PostgreSQL 17 pg_dump")
    temporary = Path(tempfile.mkdtemp(prefix=".incomplete-", dir=destination))
    dump_process = None
    age_process = None
    try:
        ciphertext = temporary / "database.dump.age"
        with ciphertext.open("xb") as output:
            os.chmod(ciphertext, 0o600)
            dump_process = subprocess.Popen([str(pg_dump), *args, "--format=custom", "--no-owner", "--no-acl"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
            age_process = subprocess.Popen(
                [str(age), "--encrypt", "--recipients-file", str(recipients)], stdin=dump_process.stdout, stdout=output, stderr=subprocess.DEVNULL, env=env
            )
            assert dump_process.stdout is not None
            dump_process.stdout.close()
            if age_process.wait(timeout=timeout) != 0 or dump_process.wait(timeout=timeout) != 0:
                raise OpsError("Backup pipeline failed; no backup was published")
            output.flush()
            os.fsync(output.fileno())
        if ciphertext.stat().st_size == 0:
            raise OpsError("Encrypted output is empty; no backup was published")
        with ciphertext.open("rb") as encrypted_source:
            sha256 = hashlib.file_digest(encrypted_source, "sha256").hexdigest()
        created = datetime.now(UTC)
        manifest = {
            "schema_version": 1,
            "database": "buycycle",
            "format": "pg_dump-custom+age",
            "created_at": created.isoformat(),
            "source_commit": source_commit,
            "bytes": ciphertext.stat().st_size,
            "sha256": sha256,
        }
        manifest_file = temporary / "manifest.json"
        with manifest_file.open("x") as output:
            os.chmod(manifest_file, 0o600)
            json.dump(manifest, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        with_directory = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(with_directory)
        finally:
            os.close(with_directory)
        final = destination / f"buycycle-{created.strftime('%Y%m%dT%H%M%SZ')}-{temporary.name.removeprefix('.incomplete-')}"
        temporary.rename(final)
        directory_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return final
    finally:
        for process in (age_process, dump_process):
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
        # Never prune published backups; retention needs a separate reviewed policy.
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/buycycle/backup.json"))
    args = parser.parse_args()
    try:
        require_root()
        backup(read_config(args.config))
    except (OpsError, OSError, KeyError, ValueError, subprocess.SubprocessError):
        print("Buycycle backup failed: check protected configuration, backup role, disk space and pipeline; no automatic deletion occurs", file=sys.stderr)
        return 1
    print("Buycycle encrypted snapshot published; verify off-host custody and rehearse restoration")
    return 0


if __name__ == "__main__":
    sys.exit(main())
