"""Unprivileged outbound status courier; never reads app data or runs app jobs."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import ssl
import sys
import time
import uuid
from http.client import HTTPException, HTTPSConnection
from pathlib import Path

from ops_common import OpsError, positive, protected_path

JOBS = ("monitor", "collector", "backup", "offhost")
STAGES = {"start": "/start", "success": "", "failure": "/fail"}
MAX_BYTES = 8192


def read_json(path: Path, *, uid: int, private: bool = True) -> dict:
    path = protected_path(path, uid=uid)
    if private and path.stat().st_mode & 0o077:
        raise OpsError("Heartbeat private file permissions are unsafe")
    with path.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise OpsError("Heartbeat record exceeds its bound")
    value = json.loads(raw)
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise OpsError("Heartbeat record schema is invalid")
    return value


def atomic_json(path: Path, value: dict, *, uid: int, shared: bool = False) -> None:
    parent = protected_path(path.parent, directory=True, uid=uid)
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    if len(raw) > MAX_BYTES:
        raise OpsError("Heartbeat record exceeds its bound")
    temporary = parent / f".{path.name}-{uuid.uuid4().hex}"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as target:
            if shared:
                # Root-created runtime directory supplies the courier's read group.
                if os.geteuid() == 0:
                    os.fchown(target.fileno(), uid, parent.stat().st_gid)
                os.fchmod(target.fileno(), 0o640)
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def record_status(directory: Path, job: str, run_id: str, stage: str, *, uid: int = 0, now_ns: int | None = None) -> None:
    if job not in JOBS or stage not in STAGES or not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise OpsError("Heartbeat job status is invalid")
    atomic_json(
        directory / f"{job}.json",
        {"schema_version": 1, "job": job, "run_id": run_id, "stage": stage, "recorded_ns": time.time_ns() if now_ns is None else now_ns},
        uid=uid,
        shared=True,
    )


def check_policy(config: dict) -> dict:
    if (
        set(config) != {"schema_version", "checks"}
        or type(config["schema_version"]) is not int
        or config["schema_version"] != 1
        or not isinstance(config["checks"], dict)
        or set(config["checks"]) != set(JOBS)
    ):
        raise OpsError("Configure exactly the four Buycycle heartbeat checks")
    for check in config["checks"].values():
        if not isinstance(check, dict) or set(check) != {"max_age_seconds", "runtime_seconds"}:
            raise OpsError("Heartbeat check policy is invalid")
        positive(check["max_age_seconds"], "heartbeat freshness", maximum=172800)
        positive(check["runtime_seconds"], "heartbeat runtime", maximum=21600)
    return config["checks"]


def credential(path: Path, *, uid: int) -> str:
    path = protected_path(path, uid=uid)
    if path.stat().st_mode & 0o077:
        raise OpsError("Heartbeat credential permissions are unsafe")
    with path.open("rb") as source:
        value = source.read(101).decode("ascii").strip()
    # Only individual check UUIDs: no project key, query, alternate host or redirect.
    if not re.fullmatch(r"https://hc-ping\.com/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value):
        raise OpsError("Heartbeat credential must identify one hosted check")
    return value.removeprefix("https://hc-ping.com")


def post_signal(path: str, stage: str) -> None:
    """Direct TLS, no environment proxy, redirects, request bodies or raw errors."""
    for attempt in range(2):
        connection = HTTPSConnection("hc-ping.com", timeout=5, context=ssl.create_default_context())
        try:
            connection.request("POST", path + STAGES[stage], body=b"", headers={"User-Agent": "f0rge-buycycle-heartbeat/1", "Content-Length": "0"})
            response = connection.getresponse()
            if response.status != 200 or response.read(3).strip() != b"OK":
                raise OpsError("Heartbeat delivery was not acknowledged")
            return
        except (OSError, HTTPException):
            if attempt:
                raise OpsError("Heartbeat transport unavailable") from None
        finally:
            connection.close()


def event(directory: Path, job: str, check: dict, *, source_uid: int, now_ns: int, last_recorded_ns: int) -> tuple[str, str, int]:
    try:
        record = read_json(directory / f"{job}.json", uid=source_uid, private=False)
        if (
            set(record) != {"schema_version", "job", "run_id", "stage", "recorded_ns"}
            or record["job"] != job
            or not isinstance(record["run_id"], str)
            or not re.fullmatch(r"[0-9a-f]{32}", record["run_id"])
            or record["stage"] not in STAGES
            or type(record["recorded_ns"]) is not int
            or not 0 < record["recorded_ns"] <= now_ns
            or record["recorded_ns"] < last_recorded_ns
        ):
            raise OpsError("Heartbeat job record is invalid")
        stage = record["stage"]
        maximum = check["runtime_seconds"] if stage == "start" else check["max_age_seconds"]
        stale = now_ns - record["recorded_ns"] > maximum * 1_000_000_000
        fingerprint = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest() + ("-stale" if stale else "")
        return ("failure" if stale else stage), fingerprint, record["recorded_ns"]
    except (OpsError, OSError, ValueError, TypeError):
        # Absent/corrupt/replayed status never reports success. One down transition
        # per unavailable episode; the provider detects a dead courier separately.
        return "failure", "unavailable", last_recorded_ns


def courier(config: dict, credentials: Path, source: Path, state: Path, *, uid: int, source_uid: int = 0, now_ns: int | None = None) -> bool:
    checks = check_policy(config)
    protected_path(state, directory=True, uid=uid, mode=0o700)
    paths = {job: credential(credentials / job, uid=uid) for job in JOBS}
    if len(set(paths.values())) != len(JOBS):
        raise OpsError("Heartbeat checks require separate credentials")
    descriptor = os.open(state / "courier.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        delivered_path = state / "delivered.json"
        delivered = read_json(delivered_path, uid=uid) if delivered_path.exists() else {"schema_version": 1}
        if set(delivered) - {"schema_version", *JOBS}:
            raise OpsError("Heartbeat delivery state is invalid")
        healthy = True
        current = time.time_ns() if now_ns is None else now_ns
        for job, check in checks.items():
            previous = delivered.get(job, {})
            if not isinstance(previous, dict) or set(previous) - {"fingerprint", "recorded_ns", "last_event"} or type(previous.get("recorded_ns", 0)) is not int:
                raise OpsError("Heartbeat delivery state is invalid")
            stage, fingerprint, recorded_ns = event(source, job, check, source_uid=source_uid, now_ns=current, last_recorded_ns=previous.get("recorded_ns", 0))
            if fingerprint == previous.get("fingerprint"):
                continue
            if stage != "failure" and fingerprint == previous.get("last_event"):
                # Restoring an old status file or reversing the clock must not
                # turn a missing/stale episode into a false recovery.
                continue
            try:
                post_signal(paths[job], stage)
            except OpsError:
                healthy = False
                continue
            last_event = previous.get("last_event", "") if fingerprint == "unavailable" else fingerprint.removesuffix("-stale")
            delivered[job] = {"fingerprint": fingerprint, "recorded_ns": recorded_ns, "last_event": last_event}
            atomic_json(delivered_path, delivered, uid=uid)
        return healthy
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="LoadCredential policy path; credentials are adjacent named files")
    args = parser.parse_args()
    try:
        uid = os.geteuid()
        if uid == 0:
            raise OpsError("Heartbeat courier must run as its separate unprivileged user")
        config = read_json(args.config, uid=uid)
        if not courier(config, args.config.parent, Path("/run/buycycle-alerts"), Path("/var/lib/buycycle-heartbeat"), uid=uid):
            raise OpsError("Heartbeat delivery unavailable; inspect service and remote deadline")
    except (OpsError, OSError, ValueError, TypeError, HTTPException):
        print("Buycycle heartbeat unavailable; inspect protected policy, signal files and remote deadlines", file=sys.stderr)
        return 1
    print("Buycycle heartbeat courier completed; delivery acknowledgement is not owner receipt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
