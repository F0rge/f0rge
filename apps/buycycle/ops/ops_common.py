"""Small root-managed host boundary; no application data or credentials are logged."""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path


class OpsError(ValueError):
    """A safe, operator-facing validation or execution failure."""


def protected_path(value: str | Path, *, directory: bool = False, uid: int = 0, mode: int | None = None) -> Path:
    path = Path(value)
    if not path.is_absolute() or path != path.resolve() or any(part in {"..", "."} for part in path.parts):
        raise OpsError("Use an absolute canonical path without symlinks")
    info = path.stat()
    if info.st_uid != uid or (directory and not stat.S_ISDIR(info.st_mode)) or (not directory and not stat.S_ISREG(info.st_mode)):
        raise OpsError("Managed path has the wrong owner or type")
    if info.st_mode & 0o022 or (mode is not None and stat.S_IMODE(info.st_mode) != mode):
        raise OpsError("Managed path permissions are unsafe")
    for parent in path.parents:
        metadata = parent.stat()
        # Sticky root-owned temporary parents are safe for private fixture dirs.
        sticky_root = metadata.st_uid == 0 and metadata.st_mode & stat.S_ISVTX
        if metadata.st_uid not in {0, uid} or (metadata.st_mode & 0o022 and not sticky_root):
            raise OpsError("Managed parent directory permissions are unsafe")
    return path


def read_config(path: Path, *, uid: int = 0) -> dict:
    config = json.loads(protected_path(path, uid=uid, mode=0o600).read_text())
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise OpsError("Managed configuration requires schema_version 1")
    return config


def positive(value: object, label: str, *, maximum: int = 86400 * 30) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= maximum:
        raise OpsError(f"Configure a positive {label} within the supported bound")
    return value


def commit(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise OpsError("An exact source commit is required")
    return value


def local_database(config: dict, *, uid: int = 0) -> tuple[list[str], dict[str, str]]:
    if config.get("host") != "127.0.0.1" or config.get("database") != "buycycle" or config.get("username") != "buycycle_backup":
        raise OpsError("Only the approved local Buycycle backup endpoint and role are allowed")
    port = positive(config.get("port"), "PostgreSQL port", maximum=65535)
    password_file = protected_path(config["pgpassfile"], uid=uid, mode=0o600)
    lines = password_file.read_text().splitlines()
    prefix = f"127.0.0.1:{port}:buycycle:buycycle_backup:"
    if len(lines) != 1 or not lines[0].startswith(prefix) or not lines[0][len(prefix) :]:
        raise OpsError("The password file must contain one exact scoped endpoint without wildcards")
    args = ["--host=127.0.0.1", f"--port={port}", "--username=buycycle_backup", "--dbname=buycycle", "--no-password"]
    env = safe_environment()
    env.update(PGPASSFILE=str(password_file), PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=1800000", PGCONNECT_TIMEOUT="10")
    return args, env


def safe_environment() -> dict[str, str]:
    # In particular, do not inherit PG*, DOCKER_CONTEXT, DOCKER_HOST or preload vars.
    return {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TZ": "UTC", "HOME": "/nonexistent"}


def require_root() -> None:
    if os.geteuid() != 0:
        raise OpsError("This entrypoint requires the managed root-owned service")
