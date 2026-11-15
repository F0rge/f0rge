"""Read-only binding for the one loopback backup socket and selected Docker DB.

The privileged backup/monitor calls this before connecting. It never starts a
unit, retargets an address, publishes a port or queries another app's records.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from ops_common import OpsError, protected_path, read_config, require_root, safe_environment

SOCKET = "buycycle-db-proxy.socket"
SERVICE = "buycycle-db-proxy.service"
ENDPOINT = "127.0.0.1:5547"
FIELDS = {
    "schema_version",
    "docker_engine_id",
    "container_id",
    "image",
    "image_id",
    "compose_project",
    "compose_service",
    "network_name",
    "network_id",
    "target_ipv4",
    "docker",
    "systemctl",
    "ss",
    "socket_file",
    "socket_sha256",
    "service_file",
    "service_sha256",
    "proxy_executable",
    "proxy_sha256",
}


def require(condition: bool) -> None:
    if not condition:
        raise OpsError("Buycycle backup proxy identity/state changed; keep backup and collection held and inspect the managed target")


def mapping(value) -> dict:
    require(isinstance(value, dict))
    return value


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def unit_properties(raw: str) -> dict[str, str]:
    result = {}
    for line in raw.splitlines():
        key, separator, value = line.partition("=")
        require(bool(separator) and key not in result)
        result[key] = value
    return result


def verify_proxy(policy_path: Path, *, uid: int = 0, runner=None, proc_root: Path = Path("/proc")) -> None:
    policy = read_config(policy_path, uid=uid)
    require(set(policy) == FIELDS)
    for name in ("container_id", "network_id"):
        require(isinstance(policy[name], str) and re.fullmatch(r"[0-9a-f]{64}", policy[name]) is not None)
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", str(policy["image_id"])) is not None)
    for name in ("docker_engine_id", "image", "compose_project", "compose_service", "network_name"):
        require(isinstance(policy[name], str) and 0 < len(policy[name]) <= 256 and not any(char.isspace() for char in policy[name]))
    address = ipaddress.IPv4Address(policy["target_ipv4"])
    require(any(address in ipaddress.IPv4Network(block) for block in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")))
    executables = {name: protected_path(policy[name], uid=uid) for name in ("docker", "systemctl", "ss", "proxy_executable")}
    require(all(os.access(path, os.X_OK) for path in executables.values()))
    for name in ("socket", "service", "proxy"):
        path = executables["proxy_executable"] if name == "proxy" else protected_path(policy[name + "_file"], uid=uid)
        require(re.fullmatch(r"[0-9a-f]{64}", str(policy[name + "_sha256"])) is not None and digest(path) == policy[name + "_sha256"])
    require(Path(policy["socket_file"]).name == SOCKET and Path(policy["service_file"]).name == SERVICE)
    execute = subprocess.run if runner is None else runner

    def command(binary: str, *args: str) -> str:
        value = execute([str(executables[binary]), *args], capture_output=True, env=safe_environment(), check=True, timeout=15)
        require(len(value.stdout) <= 4 * 1024 * 1024)
        return value.stdout.decode().strip()

    def docker(*args: str):
        return json.loads(command("docker", "--host", "unix:///run/docker.sock", *args))

    require(command("docker", "--host", "unix:///run/docker.sock", "info", "--format", "{{.ID}}") == policy["docker_engine_id"])
    inspected = docker("inspect", policy["container_id"])
    require(isinstance(inspected, list) and len(inspected) == 1)
    container = mapping(inspected[0])
    require(container.get("Id") == policy["container_id"] and container.get("Image") == policy["image_id"])
    configuration, state = mapping(container.get("Config")), mapping(container.get("State"))
    require(configuration.get("Image") == policy["image"] and state.get("Running") is True)
    labels = mapping(configuration.get("Labels"))
    require(labels.get("com.docker.compose.project") == policy["compose_project"] and labels.get("com.docker.compose.service") == policy["compose_service"])
    require(not mapping(container.get("HostConfig")).get("PortBindings"))
    selected = mapping(mapping(mapping(container.get("NetworkSettings")).get("Networks")).get(policy["network_name"]))
    require(selected.get("NetworkID") == policy["network_id"] and selected.get("IPAddress") == str(address))
    networks = docker("network", "inspect", policy["network_id"])
    require(isinstance(networks, list) and len(networks) == 1)
    network = mapping(networks[0])
    require(network.get("Id") == policy["network_id"] and network.get("Name") == policy["network_name"] and network.get("Driver") == "bridge" and network.get("Scope") == "local")
    occupants = []
    for identifier, details in mapping(network.get("Containers")).items():
        ipv4 = mapping(details).get("IPv4Address")
        require(isinstance(ipv4, str))
        if ipv4.split("/", 1)[0] == str(address):
            occupants.append(identifier)
    require(occupants == [policy["container_id"]])

    common = "Id,LoadState,ActiveState,SubState,FragmentPath,DropInPaths,Transient,NeedDaemonReload"
    socket = unit_properties(command("systemctl", "show", SOCKET, "--no-pager", "--property=" + common + ",Listen,Accept,Triggers"))
    service = unit_properties(
        command(
            "systemctl",
            "show",
            SERVICE,
            "--no-pager",
            "--property="
            + common
            + ",ExecStart,MainPID,DynamicUser,User,Group,NoNewPrivileges,ProtectSystem,ProtectHome,PrivateTmp,PrivateDevices,ProtectKernelTunables,ProtectKernelModules,ProtectControlGroups,RestrictSUIDSGID,CapabilityBoundingSet,AmbientCapabilities,RestrictAddressFamilies,IPAddressDeny,IPAddressAllow,MemoryMax,TasksMax,UMask",
        )
    )
    for properties, name in ((socket, "socket"), (service, "service")):
        require(properties.get("Id") == (SOCKET if name == "socket" else SERVICE) and properties.get("LoadState") == "loaded")
        require(properties.get("FragmentPath") == policy[name + "_file"] and properties.get("DropInPaths") == "" and properties.get("Transient") == "no")
        require(properties.get("NeedDaemonReload") == "no")
    require(socket.get("ActiveState") == "active" and socket.get("Listen") == ENDPOINT + " (Stream)")
    require(socket.get("Accept") == "no" and socket.get("Triggers") == SERVICE)
    argv = [str(executables["proxy_executable"]), "--connections-max=4", str(address) + ":5432"]
    # Loaded unit properties, not only files on disk, must retain the approved
    # command. Timestamp/PID status fields vary; no extra command is accepted.
    pattern = r"\{ path=" + re.escape(argv[0]) + r" ; argv\[\]=" + re.escape(" ".join(argv)) + r" ; ignore_errors=no ; (?:[^{}\n]*)\}"
    require(re.fullmatch(pattern, service.get("ExecStart", "")) is not None)
    require(service.get("DynamicUser") == "yes" and service.get("CapabilityBoundingSet") == "" and service.get("AmbientCapabilities") == "")
    require(service.get("User") == "buycycle-db-proxy" and service.get("Group") == "buycycle-db-proxy")
    for field in ("NoNewPrivileges", "ProtectHome", "PrivateTmp", "PrivateDevices", "ProtectKernelTunables", "ProtectKernelModules", "ProtectControlGroups", "RestrictSUIDSGID"):
        require(service.get(field) == "yes")
    require(service.get("ProtectSystem") == "strict" and service.get("MemoryMax") == "33554432" and service.get("TasksMax") == "8" and service.get("UMask") == "0077")
    require(service.get("RestrictAddressFamilies") == "AF_INET")
    require(service.get("IPAddressDeny") in {"0.0.0.0/0 ::/0", "::/0 0.0.0.0/0"})
    allow = set(service.get("IPAddressAllow", "").split())
    require(allow == {"127.0.0.0/8", "::1/128", str(address) + "/32"})
    pid = service.get("MainPID", "")
    require(pid.isdigit())
    if service.get("ActiveState") == "inactive":
        require(socket.get("SubState") == "listening" and service.get("SubState") == "dead" and pid == "0")
    else:
        require(socket.get("SubState") == "running" and service.get("ActiveState") == "active" and service.get("SubState") == "running" and int(pid) > 1)
        process = proc_root / pid
        require(os.readlink(process / "exe") == str(executables["proxy_executable"]))
        require((process / "cmdline").read_bytes() == b"\0".join(item.encode() for item in argv) + b"\0")
    listeners = command("ss", "--listening", "--tcp", "--numeric", "--no-header", "--processes", "sport = :5547").splitlines()
    require(len(listeners) == 1 and len(listeners[0].split()) >= 5 and listeners[0].split()[3] == ENDPOINT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/buycycle/database-proxy.json"))
    args = parser.parse_args()
    try:
        require_root()
        verify_proxy(args.config)
    except (OpsError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print("Buycycle backup proxy verification failed; inspect the protected cluster identity, units and listener before connecting", file=sys.stderr)
        return 1
    print("Buycycle backup loopback proxy matches the protected selected-cluster configuration")
    return 0


if __name__ == "__main__":
    sys.exit(main())
