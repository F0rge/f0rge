"""Run a full-size synthetic import preview inside the actual ARM64 image.

Usage: python3 apps/buycycle/backend/tests/capacity_preview.py --image IMAGE
The CLI must validate 702,151 synthetic records with one CPU, 768 MiB RAM and no
swap allowance beyond that RAM limit. No real export, database, credential or
network is used. Keep this separate from ordinary unit tests: it requires the
already-built image and Docker. A successful small seed is not this regression.
"""

from __future__ import annotations

if not __debug__:
    raise SystemExit("Capacity verification requires Python assertions; optimized execution is refused")

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

COUNTS = {"listing": 37574, "price_history": 660120, "detail": 4386, "runs": 58, "country_map": 13}
FIXTURE_VERSION = "synthetic-capacity-v2"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def row(table, index):
    identifier = f"synthetic-{index:024d}"
    if table == "country_map":
        return {"cid": 100000 + index, "country": "Synthetic country"}
    if table == "runs":
        return {
            "day": str(datetime.date(2026, 1, 1) + datetime.timedelta(days=index)),
            "kind": "wheels" if index % 2 else "bikes",
            "complete": 1,
            "n": 1,
            "note": None,
        }
    if table == "price_history":
        # Most listings have 18 observations. Dangling IDs would miss API indexing.
        return {
            "id": f"synthetic-{index // 18:024d}",
            "day": str(datetime.date(2026, 1, 1) + datetime.timedelta(days=index % 18)),
            "price": 12345 + index % 3700,
        }
    if table == "detail":
        return {"id": identifier, "shipping": None, "seller_rating": "4.9", "unknown_future_column": None}
    kind = "wheels" if index % 4 == 0 else "bikes"
    price = 12345 + index % 3700
    # Invented values, complete 27-column legacy width and 1000 realistic cohorts.
    listing = {
        "id": identifier,
        "kind": kind,
        "slug": "synthetic-fixture",
        "name": f"Synthetic café model-{index % 1000}",
        "brand": f"Synthetic-brand-{index % 1000}",
        "year": 2020 + index % 3,
        "size": "M",
        "cond": "Synthetic condition",
        "msrp": price * 2,
        "price": price,
        "original_price": price + 100,
        "activated_at": 1767225600,
        "updated_at": 1767312000,
        "country_id": 100000 + index % COUNTS["country_map"],
        "seller_id": "synthetic-seller",
        "favs": 1,
        "offers": 0,
        "high_demand": 0,
        "n_media": 1,
        "desc_len": 20,
        "spec": json.dumps(
            {
                "spec": {
                    "wheel-type": "1372",
                    "complete-wheels-brakes-type": "1430" if index // 4 % 2 else "1431",
                    "rim-material": "1433" if index // 4 % 3 else "1432",
                }
            }
        )
        if kind == "wheels"
        else "{}",
        "first_seen": "2026-01-01",
        "last_seen": "2026-01-18",
        "gone_at": "2026-01-31" if index % 7 == 0 else None,
        "last_fetch": "2026-01-18",
        "fetch_price": price,
        "pr": None,
    }
    assert len(listing) == 27
    return listing


def rows(table, output):
    output.write(b"[")
    for index in range(COUNTS[table]):
        if index:
            output.write(b",")
        output.write(canonical(row(table, index)))
    output.write(b"]")


class HashOutput:
    def __init__(self):
        self.hash = hashlib.sha256()

    def write(self, value):
        self.hash.update(value)


def generate(destination):
    hashes = {}
    for table in sorted(COUNTS):
        output = HashOutput()
        rows(table, output)
        hashes[table] = output.hash.hexdigest()
    header = {
        "version": 1,
        "exported_at": "2026-01-16T00:00:00Z",
        "processing_version": FIXTURE_VERSION,
        "safety_ledger": None,
        "source_schema": {table: [] for table in COUNTS},
        "table_sha256": hashes,
    }
    with destination.open("xb") as output:
        output.write(canonical(header)[:-1] + b',"tables":{')
        for index, table in enumerate(sorted(COUNTS)):
            if index:
                output.write(b",")
            output.write(canonical(table) + b":")
            rows(table, output)
        output.write(b"}}\n")
    # Only synthetic data; the enclosing temporary directory stays owner-only.
    # Bind-mounting this individual file lets the image's real UID 10001 read it.
    destination.chmod(0o644)
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    endpoint = subprocess.run(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if not endpoint.startswith("unix:///") or "\n" in endpoint:
        parser.error("Only a local Unix Docker fixture endpoint is allowed")
    base = ["docker", "--host", endpoint]
    info = json.loads(subprocess.run([*base, "image", "inspect", args.image], capture_output=True, check=True).stdout)[0]
    if info["Architecture"] != "arm64" or info["Os"] != "linux" or info["Config"]["User"] != "10001:10001":
        parser.error("An existing ARM64 Buycycle image with its real runtime UID is required")
    fixture = "buycycle-preview-capacity-" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix=fixture + "-") as temporary:
        document = Path(temporary) / "synthetic.json"
        hashes = generate(document)
        start = time.monotonic()
        try:
            subprocess.run(
                [
                    *base,
                    "create",
                    "--name",
                    fixture,
                    "--label",
                    "com.f0rge.fixture=" + fixture,
                    "--network",
                    "none",
                    "--read-only",
                    "--memory",
                    "768m",
                    "--memory-swap",
                    "768m",
                    "--cpus",
                    "1",
                    "--pids-limit",
                    "128",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--mount",
                    "type=bind,source=" + str(document) + ",target=/synthetic.json,readonly",
                    args.image,
                    "import-legacy",
                    "--preview",
                    "/synthetic.json",
                ],
                capture_output=True,
                check=True,
            )
            result = subprocess.run([*base, "start", "--attach", fixture], capture_output=True, timeout=180)
            observed = json.loads(subprocess.run([*base, "inspect", fixture], capture_output=True, check=True).stdout)[0]
            limits = observed["HostConfig"]
            assert limits["Memory"] == limits["MemorySwap"] == 768 * 1024 * 1024
            assert limits["NanoCpus"] == 1000000000 and limits["NetworkMode"] == "none"
            state = observed["State"]
            summary = {
                "fixture_version": FIXTURE_VERSION,
                "synthetic_only": True,
                "rows": sum(COUNTS.values()),
                "image": args.image,
                "cpu": 1,
                "memory_bytes": limits["Memory"],
                "seconds": round(time.monotonic() - start, 3),
                "exit_code": state["ExitCode"],
                "oom_killed": state["OOMKilled"],
            }
            print(json.dumps(summary, sort_keys=True))
            assert result.returncode == state["ExitCode"] == 0 and not state["OOMKilled"], "Full-size capped preview failed"
            report = json.loads(result.stdout)
            assert report["table_counts"] == COUNTS and report["table_sha256"] == hashes
            assert report["already_imported"] is False
            print("Full-size synthetic preview: all five table counts/hashes match within the enforced resource limit.")
        finally:
            found = subprocess.run([*base, "inspect", "--format", '{{index .Config.Labels "com.f0rge.fixture"}}', fixture], capture_output=True, text=True)
            if found.returncode == 0 and found.stdout.strip() == fixture:
                subprocess.run([*base, "rm", "--force", "--volumes", fixture], capture_output=True, check=True)


if __name__ == "__main__":
    os.umask(0o077)
    main()
