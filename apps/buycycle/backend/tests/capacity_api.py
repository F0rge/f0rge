"""Actual-engine, full-size synthetic API regression at one CPU /768 MiB.

The exact supplied ARM64 image migrates a disposable PostgreSQL15/17 fixture.
Binary COPY seeds only invented v2 records efficiently; this is a capacity
fixture, not a substitute for real export/import/reconciliation evidence.
First/repeat and concurrent requests verify all items/history, health and status.
No real identity, collection, external network, provider or owner-state write.
"""

from __future__ import annotations

if not __debug__:
    raise SystemExit("Capacity verification requires Python assertions; optimized execution is refused")

import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import struct
import subprocess
import tempfile
import time
import uuid

from capacity_preview import COUNTS, FIXTURE_VERSION, canonical, row

ROOT = Path(__file__).resolve().parents[4]
OPS = ROOT / "apps/buycycle/ops"
spec = importlib.util.spec_from_file_location("buycycle_capacity_images", OPS / "image_rehearsal.py")
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)


def make_copy(path):
    fields = {"listing": ("id",), "price_history": ("id", "day"), "detail": ("id",), "runs": ("day", "kind"), "country_map": ("cid",)}
    with path.open("xb") as output:
        output.write(b"PGCOPY\n\xff\r\n\0" + struct.pack("!ii", 0, 0))
        for table in sorted(COUNTS):
            for index in range(COUNTS[table]):
                value = row(table, index)
                key = canonical([value[field] for field in fields[table]])
                output.write(struct.pack("!h", 3))
                for field in (table.encode(), key, b"\1" + canonical(value)):
                    output.write(struct.pack("!i", len(field)) + field)
        output.write(struct.pack("!h", -1))


class Fixture:
    def __init__(self, image, major, directory):
        endpoint = subprocess.run(
            ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], capture_output=True, text=True, check=True
        ).stdout.strip()
        if not endpoint.startswith("unix:///") or "\n" in endpoint:
            raise ValueError("Only an explicit local Unix Docker fixture endpoint is allowed")
        self.base = ["docker", "--host", endpoint]
        self.directory, self.image, self.major = directory, image, major
        self.name = "buycycle-api-capacity-" + uuid.uuid4().hex
        self.pg, self.network = self.name + "-pg", self.name + "-net"
        self.containers = []
        self.results = []
        self.observed = json.loads(self.command("image", "inspect", image).stdout)[0]
        if self.observed["Architecture"] != "arm64" or self.observed["Os"] != "linux" or self.observed["Config"]["User"] != "10001:10001":
            raise ValueError("An existing ARM64 Buycycle image with its real UID is required")

    def command(self, *arguments, input=None, check=True, timeout=180):
        result = subprocess.run([*self.base, *arguments], input=input, capture_output=True, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError("Synthetic capacity fixture failed; no records or credentials are logged")
        return result

    def start(self, name, *arguments):
        self.containers.append(name)
        self.command("run", "--detach", "--name", name, "--label", "com.f0rge.fixture=" + self.name, *arguments)

    def foreground(self, name, *arguments):
        self.containers.append(name)
        return self.command("run", "--rm", "--name", name, "--label", "com.f0rge.fixture=" + self.name, *arguments)

    def info(self, name):
        return json.loads(self.command("inspect", name).stdout)[0]

    def sql(self, query):
        return self.command(
            "exec", "-i", self.pg, "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-U", "nextcloud", "-d", "buycycle_rehearsal", input=query.encode()
        ).stdout

    def envfile(self, name, values):
        path = self.directory / name
        path.write_text("".join(key + "=" + value + "\n" for key, value in values.items()))
        path.chmod(0o600)
        return path

    def setup(self):
        self.command("network", "create", "--internal", "--label", "com.f0rge.fixture=" + self.name, self.network)
        admin, migrator, runtime = [secrets.token_hex(32) for _ in range(3)]
        pg_env = self.envfile("pg.env", {"POSTGRES_USER": "nextcloud", "POSTGRES_DB": "buycycle_rehearsal", "POSTGRES_PASSWORD": admin})
        self.start(
            self.pg,
            "--network",
            self.network,
            "--memory",
            "2048m",
            "--memory-swap",
            "2048m",
            "--cpus",
            "1",
            "--pids-limit",
            "256",
            "--env-file",
            str(pg_env),
            images.POSTGRES[self.major],
            "-c",
            "log_statement=none",
            "-c",
            "log_min_error_statement=panic",
            "-c",
            "log_parameter_max_length_on_error=0",
        )
        for _ in range(240):
            if self.command("exec", self.pg, "pg_isready", "-h", "127.0.0.1", "-U", "nextcloud", "-d", "buycycle_rehearsal", check=False).returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Synthetic PostgreSQL failed readiness")
        assert int(self.sql("SHOW server_version_num").strip()) == images.POSTGRES_VERSION[self.major]
        pg_config = self.info(self.pg)["HostConfig"]
        assert not pg_config.get("PortBindings")
        assert pg_config["Memory"] == pg_config["MemorySwap"] == 2147483648
        assert pg_config["NanoCpus"] == 1000000000
        assert json.loads(self.command("network", "inspect", self.network).stdout)[0]["Internal"] is True
        self.sql(
            "CREATE ROLE buycycle_migrator LOGIN PASSWORD '"
            + migrator
            + "'; CREATE ROLE buycycle_runtime LOGIN PASSWORD '"
            + runtime
            + "'; REVOKE ALL ON DATABASE buycycle_rehearsal FROM PUBLIC; GRANT CONNECT ON DATABASE buycycle_rehearsal TO buycycle_runtime,buycycle_migrator; REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT USAGE,CREATE ON SCHEMA public TO buycycle_migrator; GRANT USAGE ON SCHEMA public TO buycycle_runtime; ALTER DEFAULT PRIVILEGES FOR ROLE buycycle_migrator IN SCHEMA public GRANT SELECT ON TABLES TO buycycle_runtime;"
        )
        migration = self.envfile("migration.env", {"MIGRATION_DATABASE_URL": "postgres://buycycle_migrator:" + migrator + "@127.0.0.1:5432/buycycle_rehearsal"})
        self.foreground(
            self.name + "-migration",
            "--network",
            "container:" + self.pg,
            "--env-file",
            str(migration),
            "--memory",
            "768m",
            "--memory-swap",
            "768m",
            "--cpus",
            "1",
            self.image,
            "migrate",
            "--grant-runtime",
        )
        self.app_env = self.envfile(
            "runtime.env",
            {
                "DATABASE_URL": "postgres://buycycle_runtime:" + runtime + "@127.0.0.1:5432/buycycle_rehearsal",
                "BUYCYCLE_ENV": "local",
                "ACCESS_ISSUER": "http://127.0.0.1:9090",
                "ACCESS_AUDIENCE": "buycycle-local",
                "ACCESS_ALLOWED_EMAILS": "owner@example.test",
                "BUYCYCLE_COLLECTION_ENABLED": "false",
            },
        )
        data = self.directory / "synthetic.copy"
        make_copy(data)
        with data.open("rb") as stream:
            result = subprocess.run(
                [
                    *self.base,
                    "exec",
                    "-i",
                    self.pg,
                    "psql",
                    "-X",
                    "-q",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-U",
                    "nextcloud",
                    "-d",
                    "buycycle_rehearsal",
                    "-c",
                    "COPY legacy_record(table_name,row_key,payload) FROM STDIN WITH (FORMAT binary)",
                ],
                stdin=stream,
                capture_output=True,
                timeout=180,
            )
        assert result.returncode == 0, "Synthetic COPY failed"
        counts = json.loads(self.sql("SELECT json_object_agg(table_name,n) FROM(SELECT table_name,count(*) n FROM legacy_record GROUP BY table_name)t"))
        assert counts == COUNTS
        self.sql("INSERT INTO collection_day(day,detail_attempts,blocked,pending) VALUES(CURRENT_DATE,150,true,false)")
        self.access = self.name + "-access"
        self.start(
            self.access,
            "--network",
            "container:" + self.pg,
            "--memory",
            "256m",
            "--memory-swap",
            "256m",
            "--cpus",
            "0.25",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--env",
            "BUYCYCLE_FIXTURE=1",
            "--env",
            "FIXTURE_UPSTREAM=http://127.0.0.1:8080",
            "--mount",
            "type=bind,source=" + str(OPS / "local-access.mjs") + ",target=/fixture.mjs,readonly",
            images.NODE,
            "node",
            "/fixture.mjs",
        )
        # The API verifies JWKS during startup; wait for the synthetic issuer's
        # RSA generation/listener rather than racing two freshly started images.
        for _ in range(100):
            ready = self.command(
                "exec",
                self.access,
                "node",
                "-e",
                "fetch('http://127.0.0.1:9090/cdn-cgi/access/certs').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))",
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Synthetic identity issuer failed readiness")

    def workload(self, mode):
        app = self.name + "-" + mode
        self.start(
            app,
            "--network",
            "container:" + self.pg,
            "--read-only",
            "--tmpfs",
            "/tmp:size=16m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--memory",
            "768m",
            "--memory-swap",
            "768m",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "--env-file",
            str(self.app_env),
            self.image,
        )
        for _ in range(100):
            result = self.command(
                "exec",
                self.access,
                "node",
                "-e",
                "fetch('http://127.0.0.1:8080/ready').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))",
                check=False,
            )
            if result.returncode == 0:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Synthetic API readiness failed")
        observed = self.info(app)
        assert observed["Image"] == self.observed["Id"] and observed["Config"]["User"] == "10001:10001"
        assert observed["HostConfig"]["Memory"] == observed["HostConfig"]["MemorySwap"] == 805306368
        assert observed["HostConfig"]["NanoCpus"] == 1000000000
        probe = self.name + "-" + mode + "-probe"
        self.start(
            probe,
            "--network",
            "container:" + self.pg,
            "--memory",
            "768m",
            "--memory-swap",
            "768m",
            "--cpus",
            "1",
            "--env",
            "CAPACITY_MODE=" + mode,
            "--mount",
            "type=bind,source=" + str(Path(__file__).with_name("capacity_api_probe.mjs")) + ",target=/probe.mjs,readonly",
            images.NODE,
            "node",
            "--max-old-space-size=512",
            "/probe.mjs",
        )
        peak = 0
        started = time.monotonic()
        while self.info(probe)["State"]["Running"]:
            if time.monotonic() - started > 180:
                raise RuntimeError("Synthetic capacity workload exceeded 180 seconds")
            memory = self.command("exec", app, "cat", "/sys/fs/cgroup/memory.peak", check=False)
            if memory.returncode == 0 and memory.stdout.strip().isdigit():
                peak = max(peak, int(memory.stdout.strip()))
            time.sleep(0.2)
        app_state, probe_state = self.info(app)["State"], self.info(probe)["State"]
        log = self.command("logs", probe, check=False)
        report = json.loads(log.stdout) if log.stdout.strip() else {"passed": False, "client_exit": probe_state["ExitCode"]}
        if app_state["Running"]:
            metrics = (
                self.command("exec", app, "sh", "-c", "cat /sys/fs/cgroup/memory.peak; cat /sys/fs/cgroup/memory.events; echo CPU; cat /sys/fs/cgroup/cpu.stat")
                .stdout.decode()
                .splitlines()
            )
            peak = max(peak, int(metrics[0]))
            separator = metrics.index("CPU")
            report["cgroup_memory_events"] = {key: int(value) for key, value in (line.split() for line in metrics[1:separator])}
            report["cgroup_cpu_stat"] = {key: int(value) for key, value in (line.split() for line in metrics[separator + 1 :])}
            assert report["cgroup_memory_events"]["oom_kill"] == 0
        report.update({"observed_cgroup_peak_bytes": peak, "app_oom_killed": app_state["OOMKilled"], "client_oom_killed": probe_state["OOMKilled"]})
        self.results.append(report)
        print(json.dumps(report, sort_keys=True), flush=True)
        assert report["passed"] and app_state["Running"] and not app_state["OOMKilled"] and probe_state["ExitCode"] == 0
        self.command("stop", "--time", "5", app)

    def cleanup(self):
        for container in reversed(self.containers):
            result = self.command("inspect", "--format", '{{index .Config.Labels "com.f0rge.fixture"}}', container, check=False)
            if result.returncode == 0 and result.stdout.decode().strip() == self.name:
                self.command("rm", "--force", "--volumes", container, check=False)
        found = self.command("network", "inspect", self.network, check=False)
        if found.returncode == 0 and json.loads(found.stdout)[0].get("Labels", {}).get("com.f0rge.fixture") == self.name:
            self.command("network", "rm", self.network, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--postgres-major", type=int, choices=(15, 17), default=17)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="buycycle-api-capacity-") as temporary:
        fixture = Fixture(args.image, args.postgres_major, Path(temporary))
        try:
            fixture.setup()
            for mode in ("bikes", "wheels", "concurrent", "concurrent-bikes"):
                fixture.workload(mode)
            owners = json.loads(
                fixture.sql(
                    "SELECT json_build_object('state',(SELECT count(*) FROM user_state),'history',(SELECT count(*) FROM user_state_history),'browser',(SELECT count(*) FROM browser_import))"
                )
            )
            assert owners == {"state": 0, "history": 0, "browser": 0}
            assert not fixture.info(fixture.pg)["State"]["OOMKilled"]
            print(
                json.dumps(
                    {
                        "passed": True,
                        "fixture_version": FIXTURE_VERSION,
                        "rows": sum(COUNTS.values()),
                        "postgres_major": args.postgres_major,
                        "owner_state_unchanged": True,
                        "modes": [result["mode"] for result in fixture.results],
                        "app_cpu": 1,
                        "app_memory_bytes": 805306368,
                        "postgres_memory_bytes": 2147483648,
                    }
                )
            )
        finally:
            fixture.cleanup()


if __name__ == "__main__":
    os.umask(0o077)
    main()
