"""Read-only operational checks; emit statuses, never app data or secret values."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from collect import compose_command
from ops_common import OpsError, commit, local_database, positive, protected_path, read_config, require_root

COLLECTION_SQL = """SELECT COALESCE(EXTRACT(EPOCH FROM (clock_timestamp()-max(recorded_at)))::bigint,-1)
FROM (SELECT day,max(recorded_at) AS recorded_at FROM collector_runs
WHERE complete GROUP BY day HAVING count(DISTINCT kind)=2) completed_days;"""


def check_backup(config: dict, *, uid: int = 0, now: datetime | None = None) -> None:
    directory = protected_path(config["backup_directory"], directory=True, uid=uid, mode=0o700)
    maximum_age = positive(config.get("backup_max_age_seconds"), "backup freshness limit")
    snapshots = sorted(path for path in directory.iterdir() if re.fullmatch(r"buycycle-[0-9]{8}T[0-9]{6}Z-[a-z0-9_]+", path.name))
    if not snapshots:
        raise OpsError("No complete encrypted backup: inspect backup service; preserve existing data")
    latest = protected_path(snapshots[-1], directory=True, uid=uid, mode=0o700)
    manifest = read_config(latest / "manifest.json", uid=uid)
    encrypted = protected_path(latest / "database.dump.age", uid=uid, mode=0o600)
    if manifest.get("database") != "buycycle" or manifest.get("format") != "pg_dump-custom+age" or manifest.get("bytes") != encrypted.stat().st_size:
        raise OpsError("Encrypted backup metadata mismatch: preserve files and investigate")
    commit(manifest.get("source_commit"))
    with encrypted.open("rb") as source:
        checksum = hashlib.file_digest(source, "sha256").hexdigest()
    if manifest.get("sha256") != checksum:
        raise OpsError("Encrypted backup checksum mismatch: preserve files and investigate")
    created = datetime.fromisoformat(manifest["created_at"])
    if created.tzinfo is None:
        raise OpsError("Backup creation time must have a timezone")
    age = ((now or datetime.now(UTC)) - created).total_seconds()
    if age < 0 or age > maximum_age:
        raise OpsError("Encrypted backup is stale: inspect backup service and recovery custody")


def monitor(config: dict, *, uid: int = 0) -> None:
    command, environment = compose_command(config, uid=uid)
    # Read the live app by explicit project/file; an older env-file pin must not
    # select a different image while examining the approved active deployment.
    environment["BUYCYCLE_IMAGE"] = config["image"]
    selected = subprocess.run([*command, "ps", "--quiet", "app"], capture_output=True, env=environment, check=True, timeout=15).stdout.decode().strip()
    if not re.fullmatch(r"[0-9a-f]{12,64}", selected):
        raise OpsError("Buycycle app is missing or ambiguous: inspect the managed release receipt")
    docker = command[0]
    inspected = subprocess.run([docker, "inspect", selected], capture_output=True, env=environment, check=True, timeout=15)
    container = json.loads(inspected.stdout)[0]
    if container["Config"]["Image"] != config["image"] or container["State"].get("Health", {}).get("Status") != "healthy":
        raise OpsError("Buycycle image or health is wrong: keep collection held and inspect managed release")
    ready = subprocess.run(
        [docker, "exec", selected, "curl", "--fail", "--silent", "--max-time", "5", "http://127.0.0.1:8080/ready"], capture_output=True, env=environment, check=True, timeout=10
    )
    if json.loads(ready.stdout).get("status") != "ready":
        raise OpsError("Buycycle readiness failed: inspect migration and database connectivity")
    stats = subprocess.run([docker, "stats", "--no-stream", "--format", "{{json .}}", selected], capture_output=True, env=environment, check=True, timeout=15)
    percent = float(json.loads(stats.stdout)["MemPerc"].removesuffix("%"))
    threshold = positive(config.get("memory_max_percent"), "measured memory threshold", maximum=99)
    if not 0 <= percent < threshold:
        raise OpsError("Buycycle memory pressure: inspect resource limits and measured workload")
    disk_max = positive(config.get("disk_max_percent"), "measured disk threshold", maximum=99)
    usage = shutil.disk_usage(protected_path(config["backup_directory"], directory=True, uid=uid, mode=0o700))
    if (usage.total - usage.free) * 100 / usage.total >= disk_max:
        raise OpsError("Buycycle disk pressure: review capacity and retention; do not delete backups automatically")
    db_args, db_environment = local_database(config, uid=uid)
    psql = protected_path(config["psql"], uid=uid)
    query = subprocess.run(
        [str(psql), *db_args, "--no-psqlrc", "--tuples-only", "--no-align", "--set", "ON_ERROR_STOP=1", "--command", COLLECTION_SQL],
        capture_output=True,
        env=db_environment,
        check=True,
        timeout=15,
    )
    age = int(query.stdout.strip())
    if age < 0 or age > positive(config.get("collection_max_age_seconds"), "daily collection freshness limit"):
        raise OpsError("Daily collection is incomplete or stale: inspect quota/blocked state; do not force a rerun")
    check_backup(config, uid=uid)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/buycycle/monitor.json"))
    args = parser.parse_args()
    try:
        require_root()
        monitor(read_config(args.config))
    except OpsError as error:
        print(f"Buycycle monitor action required: {error}", file=sys.stderr)
        return 1
    except (OSError, KeyError, ValueError, subprocess.SubprocessError):
        print("Buycycle monitor unavailable: inspect protected configuration, local dependencies and service status", file=sys.stderr)
        return 1
    print("Buycycle readiness, resource, collection and encrypted-backup checks passed; off-host custody/restore evidence is separate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
