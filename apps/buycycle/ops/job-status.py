"""Record only fixed job lifecycle signals; always preserve the wrapped job result."""

from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from pathlib import Path

from heartbeat import JOBS, record_status
from ops_common import OpsError, require_root


def run_job(job: str, command: list[str], directory: Path, *, uid: int = 0) -> int:
    if job not in JOBS or not command or not Path(command[0]).is_absolute():
        raise OpsError("Configure a fixed absolute job command")
    run_id = uuid.uuid4().hex

    def signal(stage: str) -> None:
        try:
            record_status(directory, job, run_id, stage, uid=uid)
        except (OpsError, OSError, ValueError):
            print("Buycycle job status unavailable; remote missing-heartbeat detection remains required", file=sys.stderr)

    signal("start")
    try:
        # Inherited output retains the job's existing sanitized journal behavior.
        # No retry, shell, environment credential or outbound notification here.
        result = subprocess.run(command, check=False).returncode
        result = result if result >= 0 else 128 - result
    except OSError:
        result = 127
        print("Buycycle job could not start; inspect its managed service", file=sys.stderr)
    signal("success" if result == 0 else "failure")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", choices=JOBS, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        require_root()
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        return run_job(args.job, command, Path("/run/buycycle-alerts"))
    except (OpsError, OSError, ValueError):
        print("Buycycle job wrapper configuration invalid", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
