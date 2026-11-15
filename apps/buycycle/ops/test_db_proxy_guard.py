"""Synthetic Docker/systemd boundary checks; no provider or database writes."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db_proxy_guard import ENDPOINT, SERVICE, SOCKET, verify_proxy
from ops_common import OpsError, local_database


class DatabaseProxyGuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.uid = os.getuid()
        self.policy = {
            "schema_version": 1,
            "docker_engine_id": "synthetic-engine",
            "container_id": "a" * 64,
            "image": "postgres:15-alpine",
            "image_id": "sha256:" + "b" * 64,
            "compose_project": "synthetic-database",
            "compose_service": "synthetic-postgres",
            "network_name": "synthetic-bridge",
            "network_id": "c" * 64,
            "target_ipv4": "10.123.0.4",
        }
        for name in ("docker", "systemctl", "ss", "proxy_executable"):
            self.policy[name] = str(self.file(name, "synthetic executable\n", 0o700))
        for name, filename in (("socket", SOCKET), ("service", SERVICE)):
            self.policy[name + "_file"] = str(self.file(filename, "synthetic reviewed unit\n"))
            self.policy[name + "_sha256"] = hashlib.sha256(Path(self.policy[name + "_file"]).read_bytes()).hexdigest()
        self.policy["proxy_sha256"] = hashlib.sha256(Path(self.policy["proxy_executable"]).read_bytes()).hexdigest()
        self.path = self.file("proxy.json", json.dumps(self.policy))
        self.container = {
            "Id": self.policy["container_id"],
            "Image": self.policy["image_id"],
            "Config": {
                "Image": self.policy["image"],
                "Labels": {"com.docker.compose.project": self.policy["compose_project"], "com.docker.compose.service": self.policy["compose_service"]},
            },
            "State": {"Running": True},
            "HostConfig": {"PortBindings": {}},
            "NetworkSettings": {"Networks": {self.policy["network_name"]: {"NetworkID": self.policy["network_id"], "IPAddress": self.policy["target_ipv4"]}}},
        }
        self.network = {
            "Id": self.policy["network_id"],
            "Name": self.policy["network_name"],
            "Driver": "bridge",
            "Scope": "local",
            "Containers": {self.policy["container_id"]: {"IPv4Address": self.policy["target_ipv4"] + "/24"}},
        }
        common = {"LoadState": "loaded", "DropInPaths": "", "Transient": "no", "NeedDaemonReload": "no"}
        self.socket = {
            **common,
            "Id": SOCKET,
            "FragmentPath": self.policy["socket_file"],
            "ActiveState": "active",
            "SubState": "listening",
            "Listen": ENDPOINT + " (Stream)",
            "Accept": "no",
            "Triggers": SERVICE,
        }
        executable = self.policy["proxy_executable"]
        self.argv = [executable, "--connections-max=4", self.policy["target_ipv4"] + ":5432"]
        self.service = {
            **common,
            "Id": SERVICE,
            "FragmentPath": self.policy["service_file"],
            "ActiveState": "inactive",
            "SubState": "dead",
            "MainPID": "0",
            "ExecStart": "{ path="
            + executable
            + " ; argv[]="
            + " ".join(self.argv)
            + " ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }",
            "DynamicUser": "yes",
            "User": "buycycle-db-proxy",
            "Group": "buycycle-db-proxy",
            "NoNewPrivileges": "yes",
            "ProtectHome": "yes",
            "PrivateTmp": "yes",
            "PrivateDevices": "yes",
            "ProtectKernelTunables": "yes",
            "ProtectKernelModules": "yes",
            "ProtectControlGroups": "yes",
            "RestrictSUIDSGID": "yes",
            "ProtectSystem": "strict",
            "MemoryMax": "33554432",
            "TasksMax": "8",
            "UMask": "0077",
            "CapabilityBoundingSet": "",
            "AmbientCapabilities": "",
            "RestrictAddressFamilies": "AF_INET",
            "IPAddressDeny": "0.0.0.0/0 ::/0",
            "IPAddressAllow": "127.0.0.0/8 ::1/128 " + self.policy["target_ipv4"] + "/32",
        }
        self.listeners = 'LISTEN 0 4 127.0.0.1:5547 0.0.0.0:* users:(("systemd",pid=1,fd=55))\n'
        self.engine = self.policy["docker_engine_id"]
        self.calls = []

    def file(self, name, text, mode=0o600):
        path = self.root / name
        path.write_text(text)
        path.chmod(mode)
        return path

    def command(self, args, **kwargs):
        self.calls.append((args, kwargs))
        self.assertEqual(kwargs["env"]["HOME"], "/nonexistent")
        self.assertNotIn("DOCKER_HOST", kwargs["env"])
        self.assertNotIn("PGPASSWORD", kwargs["env"])
        if args[0] == self.policy["docker"]:
            self.assertEqual(args[1:3], ["--host", "unix:///run/docker.sock"])
            if args[3] == "info":
                raw = self.engine
            elif args[3] == "inspect":
                self.assertEqual(args[4:], [self.policy["container_id"]])
                raw = json.dumps([self.container])
            elif args[3:5] == ["network", "inspect"]:
                self.assertEqual(args[5:], [self.policy["network_id"]])
                raw = json.dumps([self.network])
            else:
                raise AssertionError("Unexpected Docker mutation")
        elif args[0] == self.policy["systemctl"]:
            self.assertEqual(args[1], "show")
            properties = self.socket if args[2] == SOCKET else self.service
            raw = "\n".join(key + "=" + value for key, value in properties.items())
        elif args[0] == self.policy["ss"]:
            raw = self.listeners
        else:
            raise AssertionError("Unexpected executable")
        return subprocess.CompletedProcess(args, 0, raw.encode(), b"")

    def verify(self):
        verify_proxy(self.path, uid=self.uid, runner=self.command, proc_root=self.root / "proc")

    def test_verified_inactive_socket_activation_and_running_process(self):
        self.verify()
        self.service.update(ActiveState="active", SubState="running", MainPID="123")
        self.socket["SubState"] = "running"
        process = self.root / "proc" / "123"
        process.mkdir(parents=True)
        (process / "exe").symlink_to(self.policy["proxy_executable"])
        (process / "cmdline").write_bytes(b"\0".join(item.encode() for item in self.argv) + b"\0")
        self.verify()
        (process / "cmdline").write_bytes(b"wrong-target\0")
        with self.assertRaises(OpsError):
            self.verify()

    def test_socket_service_states_must_match_exact_waiting_or_running_pair(self):
        # systemd257 Accept=no sockets become running after activating their
        # service; listening is the distinct pre-activation state.
        for socket_state, service_active, service_state, pid in (
            ("running", "inactive", "dead", "0"),
            ("listening", "active", "running", "123"),
            ("listening", "inactive", "dead", "123"),
            ("listening", "inactive", "failed", "0"),
            ("running", "active", "running", "0"),
            ("running", "activating", "start", "123"),
            ("start-pre", "active", "running", "123"),
        ):
            self.socket["SubState"] = socket_state
            self.service.update(ActiveState=service_active, SubState=service_state, MainPID=pid)
            with self.subTest(socket=socket_state, service=service_active, substate=service_state, pid=pid), self.assertRaises(OpsError):
                self.verify()

    def test_changed_container_network_image_and_ip_fail_before_connect(self):
        changes = [
            lambda: self.container.update(Id="d" * 64),
            lambda: self.container.update(Image="sha256:" + "d" * 64),
            lambda: self.container["State"].update(Running=False),
            lambda: self.container["Config"].update(Image="postgres:17"),
            lambda: self.container["Config"]["Labels"].update({"com.docker.compose.project": "another-app"}),
            lambda: self.container["NetworkSettings"]["Networks"][self.policy["network_name"]].update(IPAddress="10.123.0.5"),
            lambda: self.container["HostConfig"].update(PortBindings={"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "5432"}]}),
            lambda: self.network.update(Id="d" * 64),
            lambda: self.network["Containers"].update({"d" * 64: {"IPv4Address": "10.123.0.4/24"}}),
        ]
        original_container, original_network = copy.deepcopy(self.container), copy.deepcopy(self.network)
        for index, mutate in enumerate(changes):
            self.container, self.network = copy.deepcopy(original_container), copy.deepcopy(original_network)
            self.calls = []
            mutate()
            with self.subTest(change=index), self.assertRaises(OpsError):
                self.verify()
            self.assertFalse(any(call[0][0] == self.policy["ss"] for call in self.calls))
        self.container, self.network = original_container, original_network
        self.engine = "different-engine"
        with self.assertRaises(OpsError):
            self.verify()
        self.assertTrue(all("psql" not in str(args) for args, _ in self.calls))

    def test_public_listener_changed_units_loaded_command_and_hardening_fail(self):
        for properties, key, value in (
            (self.socket, "Listen", "0.0.0.0:5547 (Stream)"),
            (self.socket, "ActiveState", "inactive"),
            (self.service, "ExecStart", self.service["ExecStart"].replace("10.123.0.4", "10.123.0.9")),
            (self.service, "DropInPaths", "/run/systemd/system/unreviewed.conf"),
            (self.service, "IPAddressAllow", "10.123.0.0/24"),
            (self.service, "DynamicUser", "no"),
            (self.service, "User", "root"),
            (self.service, "NoNewPrivileges", "no"),
            (self.service, "NeedDaemonReload", "yes"),
            (self.service, "CapabilityBoundingSet", "cap_sys_admin"),
            (self.service, "ActiveState", "activating"),
        ):
            original = properties[key]
            properties[key] = value
            with self.subTest(key=key), self.assertRaises(OpsError):
                self.verify()
            properties[key] = original
        for listener in (self.listeners.replace("127.0.0.1:5547", "0.0.0.0:5547"), self.listeners + self.listeners.replace("127.0.0.1:5547", "10.123.0.1:5547"), ""):
            self.listeners = listener
            with self.subTest(listener=bool(listener)), self.assertRaises(OpsError):
                self.verify()
        Path(self.policy["service_file"]).write_text("changed target\n")
        with self.assertRaises(OpsError):
            self.verify()

    def test_protected_policy_executable_and_private_target_only(self):
        for key, value in (("target_ipv4", "203.0.113.1"), ("container_id", "short-id"), ("unexpected", True)):
            self.path.write_text(json.dumps({**self.policy, key: value}))
            with self.subTest(key=key), self.assertRaises((OpsError, ValueError)):
                self.verify()
        self.path.write_text(json.dumps(self.policy))
        self.path.chmod(0o644)
        with self.assertRaises(OpsError):
            self.verify()

    def test_root_database_clients_cannot_omit_guard_or_change_loopback_port(self):
        password = self.file("pgpass", "127.0.0.1:5547:buycycle:buycycle_backup:synthetic\n")
        config = {"host": "127.0.0.1", "port": 5547, "database": "buycycle", "username": "buycycle_backup", "pgpassfile": str(password)}
        with patch("ops_common.protected_path", return_value=password), self.assertRaises(OpsError):
            local_database(config)
        with patch("ops_common.protected_path", return_value=password), patch("db_proxy_guard.verify_proxy") as guard:
            local_database({**config, "database_proxy_policy": str(self.path)})
            guard.assert_called_once_with(self.path, uid=0)
        with patch("ops_common.protected_path", return_value=password), patch("db_proxy_guard.verify_proxy", side_effect=OpsError("changed target")), self.assertRaises(OpsError):
            local_database({**config, "database_proxy_policy": str(self.path)})


if __name__ == "__main__":
    unittest.main()
