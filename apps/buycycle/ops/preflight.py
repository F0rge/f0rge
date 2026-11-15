#!/usr/bin/env python3
"""Read-only, fail-closed Buycycle provider/configuration preflight.

Run on the selected Pi using root-managed configuration and scoped read tokens.
No raw provider response, credential, owner email or connection string is logged.
Only successful observations produce a release-consumable receipt.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ops_common import postgres_major

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / ".github" / "deploy"))
from buycycle_release import managed_docker_environment

APP = "xi0qwpbyl2d8gf8u3xl13jkv"
DOMAIN = "buycycle.leo-figueiredo.com"
SHA = re.compile(r"[0-9a-f]{40}\Z")


class Refused(ValueError):
    """A fixed diagnostic identifier, never an underlying provider body."""


def require(ok: object, code: str) -> None:
    if not ok:
        raise Refused(code)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def managed_file(path: str, *, uid: int = 0, secret: bool = False) -> Path:
    selected = Path(path)
    require(selected.is_absolute(), "managed_path_absolute")
    for item in [selected, *selected.parents]:
        info = item.lstat()
        require(not stat.S_ISLNK(info.st_mode), "managed_path_symlink")
        require(not info.st_mode & 0o022, "managed_path_writable")
        require(info.st_uid == (uid if item == selected else 0), "managed_path_owner")
    require(selected.is_file(), "managed_file_required")
    if secret:
        require(not selected.stat().st_mode & 0o077, "managed_secret_permissions")
        require(0 < selected.stat().st_size <= 65536, "managed_secret_size")
    return selected


def managed_directory(path: str) -> Path:
    selected = Path(path)
    require(selected.is_absolute() and selected == selected.resolve(), "managed_directory_path")
    for item in [selected, *selected.parents]:
        info = item.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022, "managed_directory_protection")
    return selected


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def get_json(url: str, token_file: str) -> object:
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password, "provider_https")
    token = managed_file(token_file, secret=True).read_text().strip()
    require(token and "\n" not in token and "\r" not in token, "provider_token")
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"}, method="GET")
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
            payload = response.read(2 * 1024 * 1024 + 1)
        require(len(payload) <= 2 * 1024 * 1024, "provider_response_size")
        return json.loads(payload)
    except Refused:
        raise
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise Refused("provider_read_failed") from exc


def cf_result(value: object, *, collection: bool = False):
    require(isinstance(value, dict) and value.get("success") is True and "result" in value, "cloudflare_response")
    if collection:
        result, info = value["result"], value.get("result_info", {})
        require(isinstance(result, list) and len(result) < 100, "cloudflare_collection")
        require(info.get("total_count") == len(result) and info.get("total_pages", 1) == 1, "cloudflare_pagination")
    return value["result"]


def validate_access(config: dict, application: dict, policies: list, identity: dict, tunnel: dict, tunnel_config: dict, dns: list, *, organization: dict) -> None:
    require(application.get("id") == config["cf_application_id"] and application.get("type") == "self_hosted", "access_app")
    require(application.get("domain") == DOMAIN and application.get("aud") == config["access_audience"], "access_destination_audience")
    # allowed_idps is the documented provider selection. The auxiliary all-IDPs
    # flag is not returned by every API response; a returned contradiction still
    # refuses the observation rather than widening the exact OTP allowlist.
    require(isinstance(config["otp_provider_id"], str) and bool(config["otp_provider_id"]) and application.get("allowed_idps") == [config["otp_provider_id"]], "access_otp_only")
    require("use_all_idps" not in application or application["use_all_idps"] is False, "access_otp_only")
    require(identity.get("id") == config["otp_provider_id"] and identity.get("type") == "onetimepin", "access_otp_provider")
    require(len(policies) == 1, "access_policy_count")
    policy = policies[0]
    require(policy.get("decision") == "allow" and policy.get("id") == config["access_policy_id"], "access_policy_action")
    require(policy.get("include") == [{"email": {"email": config["owner_email"]}}], "access_owner")
    require(policy.get("exclude", []) == [] and policy.get("require", []) == [], "access_policy_shape")
    require(application.get("options_preflight_bypass") is False, "access_bypass")
    # An explicit application boolean overrides the organization setting. When
    # omitted it inherits; missing/null values never imply a disabled bypass.
    warp_disabled = (
        application["allow_authenticate_via_warp"] is False if "allow_authenticate_via_warp" in application else organization.get("allow_authenticate_via_warp") is False
    )
    require(warp_disabled, "access_bypass")
    require(tunnel.get("id") == config["tunnel_id"] and tunnel.get("status") == "healthy", "tunnel_identity_health")
    ingress = tunnel_config.get("config", {}).get("ingress")
    require(isinstance(ingress, list) and len(ingress) == 2, "tunnel_routes")
    require(ingress[0].get("hostname") == DOMAIN and not ingress[0].get("path") and ingress[0].get("service") == "http://app:8080", "tunnel_origin")
    require(ingress[1] == {"service": "http_status:404"}, "tunnel_fallback")
    require(len(dns) == 1 and dns[0].get("name") == DOMAIN and dns[0].get("type") == "CNAME" and dns[0].get("proxied") is True, "dns_gateway")
    require(dns[0].get("content") == config["tunnel_id"] + ".cfargotunnel.com", "dns_tunnel")


def validate_legacy(application: dict, tasks: list, containers: list[dict]) -> None:
    require(application.get("uuid") == APP, "legacy_app_identity")
    require(application.get("settings", {}).get("is_auto_deploy_enabled") is False, "legacy_auto_deploy")
    require(application.get("settings", {}).get("is_preview_deployments_enabled") is False, "legacy_preview_deploy")
    require(
        all(
            key in application and application[key] in (None, "")
            for key in ("manual_webhook_secret_github", "manual_webhook_secret_gitlab", "manual_webhook_secret_bitbucket", "manual_webhook_secret_gitea")
        ),
        "legacy_webhook",
    )
    require(isinstance(tasks, list) and all(task.get("enabled") is False for task in tasks), "legacy_schedules")
    require(str(application.get("status", "")).split(":", 1)[0] in {"exited", "stopped"}, "legacy_provider_running")
    for container in containers:
        labels = container.get("labels") or {}
        if APP in container.get("name", "") or APP in labels.values():
            require(container.get("running") is False and container.get("restart") in {"no", ""}, "legacy_container_running")


def validate_compose(config: dict, compose: dict, containers: list[dict]) -> None:
    services = compose.get("services", {})
    require({"app", "migrate", "tunnel"} <= services.keys(), "compose_services")
    require(all(not service.get("ports") and not service.get("network_mode") for name, service in services.items() if name != "postgres"), "origin_published")
    for name in ("app", "migrate", "tunnel"):
        service = services[name]
        require(service.get("read_only") is True and "ALL" in service.get("cap_drop", []), "container_isolation")
        require(not service.get("volumes") and not service.get("devices") and not service.get("privileged") and not service.get("cap_add"), "app_host_authority")
    for name in ("app", "migrate"):
        require(services[name].get("user") in (None, "10001", "10001:10001"), "app_runtime_user")
    app = services["app"]
    environment = app.get("environment", {})
    require(environment.get("ACCESS_ISSUER") == config["access_issuer"] and environment.get("ACCESS_AUDIENCE") == config["access_audience"], "runtime_access_config")
    require(environment.get("ACCESS_ALLOWED_EMAILS") == config["owner_email"] and environment.get("BUYCYCLE_ENV") not in {"local", "test"}, "runtime_owner_mode")
    require(str(environment.get("BUYCYCLE_COLLECTION_ENABLED")).lower() in {"0", "false"}, "collection_activation_hold")
    require({item["source"] for item in app.get("secrets", [])} == {"runtime_database_url"}, "app_secrets")
    require({item["source"] for item in services["migrate"].get("secrets", [])} == {"migrator_database_url"}, "migration_secrets")
    require(re.fullmatch(r"ghcr.io/f0rge/buycycle@sha256:[0-9a-f]{64}", app.get("image", "")) and app["image"] == services["migrate"].get("image"), "compose_pinned_app_image")
    require(services["migrate"].get("command") == ["migrate", "--grant-runtime"] and "maintenance" in services["migrate"].get("profiles", []), "controlled_migration")
    if "postgres" in services:
        require("bootstrap-cluster" in services["postgres"].get("profiles", []), "cluster_bootstrap_profile")
        ports = services["postgres"].get("ports", [])
        require(
            not ports
            or (
                len(ports) == 1
                and ports[0].get("host_ip") == "127.0.0.1"
                and str(ports[0].get("published")) == "5547"
                and ports[0].get("target") == 5432
                and ports[0].get("protocol", "tcp") == "tcp"
            ),
            "postgres_loopback_only",
        )
    network = compose.get("networks", {}).get("data", {})
    require(network.get("external") is True and network.get("name") == config["database_network"], "existing_cluster_network")
    for container in containers:
        labels = container.get("labels") or {}
        if labels.get("com.docker.compose.project") == "buycycle" and labels.get("com.docker.compose.service") == "app":
            require(not any(container.get("ports", {}).values()), "running_origin_published")


def database_query(major: int = 17) -> str:
    """Read only catalog privileges, never app/customer rows or connection strings."""
    checks = [
        f"current_setting('server_version_num')::integer / 10000 = {postgres_major({'postgres_major': major})}",
        "EXISTS(SELECT 1 FROM pg_roles WHERE rolname='buycycle_runtime' AND rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls)",
        "NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='buycycle_runtime'))",
        "has_schema_privilege('buycycle_runtime','public','USAGE')",
        "NOT has_schema_privilege('buycycle_runtime','public','CREATE')",
        "NOT has_database_privilege('buycycle_runtime',current_database(),'CREATE,TEMP')",
        "has_database_privilege('buycycle_runtime',current_database(),'CONNECT')",
        "NOT EXISTS(SELECT 1 FROM pg_database WHERE NOT datistemplate AND datname NOT IN(current_database(),'postgres') AND has_database_privilege('buycycle_runtime',datname,'CONNECT'))",
    ]
    for table in ["legacy_record", "user_state", "collection_day", "collector_runs"]:
        checks += [f"has_table_privilege('buycycle_runtime','public.{table}','{privilege}')" for privilege in ("SELECT", "INSERT", "UPDATE")]
        checks += [f"NOT has_table_privilege('buycycle_runtime','public.{table}','DELETE,TRUNCATE')"]
    for table in ["user_state_history", "browser_import", "source_snapshots"]:
        checks += [f"has_table_privilege('buycycle_runtime','public.{table}','{privilege}')" for privilege in ("SELECT", "INSERT")]
        checks += [f"NOT has_table_privilege('buycycle_runtime','public.{table}','UPDATE,DELETE,TRUNCATE')"]
    checks += [
        "has_table_privilege('buycycle_runtime','public.import_manifest','SELECT')",
        "NOT has_table_privilege('buycycle_runtime','public.import_manifest','INSERT,UPDATE,DELETE,TRUNCATE')",
        "EXISTS(SELECT 1 FROM pg_roles WHERE rolname='buycycle_backup' AND rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls)",
        "NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='buycycle_backup'))",
        "has_database_privilege('buycycle_backup',current_database(),'CONNECT')",
        "NOT EXISTS(SELECT 1 FROM pg_database WHERE NOT datistemplate AND datname NOT IN(current_database(),'postgres') AND has_database_privilege('buycycle_backup',datname,'CONNECT'))",
        "NOT has_database_privilege('buycycle_backup',current_database(),'CREATE,TEMP')",
        "has_schema_privilege('buycycle_backup','public','USAGE')",
        "NOT has_schema_privilege('buycycle_backup','public','CREATE')",
    ]
    for table in [
        "legacy_record",
        "user_state",
        "collection_day",
        "collector_runs",
        "user_state_history",
        "browser_import",
        "source_snapshots",
        "import_manifest",
        "buycycle_schema_migrations",
    ]:
        checks += [f"has_table_privilege('buycycle_backup','public.{table}','SELECT')"]
        checks += [f"NOT has_table_privilege('buycycle_backup','public.{table}','INSERT,UPDATE,DELETE,TRUNCATE')"]
    return (
        "SELECT json_build_object('passed',"
        + " AND ".join("(" + check + ")" for check in checks)
        + ",'server_version_num',current_setting('server_version_num')::integer,'current_user',current_user,'current_database',current_database());"
    )


def postgres_inventory(config: dict, containers: list[dict], read) -> list[dict]:
    """Bind known clusters without treating a label as an ADR exemption."""
    declared = config.get("postgres_inventory")
    require(isinstance(declared, list) and 0 < len(declared) <= 50, "postgres_inventory_required")
    selected = config.get("postgres_container")
    require(isinstance(selected, str) and re.fullmatch(r"[0-9a-f]{64}", selected), "postgres_selected_full_id")
    by_id = {}
    for entry in declared:
        require(isinstance(entry, dict) and re.fullmatch(r"[0-9a-f]{64}", entry.get("container_id", "")), "postgres_inventory_identity")
        require(entry["container_id"] not in by_id, "postgres_inventory_duplicate")
        require(entry.get("classification") in {"application_data", "coolify_control_plane", "airflow_metadata"}, "postgres_inventory_classification")
        require(isinstance(entry.get("purpose"), str) and 0 < len(entry["purpose"]) <= 200, "postgres_inventory_purpose")
        require(
            isinstance(entry.get("compose_project"), str) and entry["compose_project"] and isinstance(entry.get("compose_service"), str) and entry["compose_service"],
            "postgres_inventory_labels",
        )
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", entry.get("image_id", "")), "postgres_inventory_image_id")
        require(type(entry.get("postgres_major")) is int and entry["postgres_major"] in {15, 16, 17}, "postgres_inventory_major")
        by_id[entry["container_id"]] = entry
    discovered = [
        container
        for container in containers
        if container.get("id") in by_id
        or re.fullmatch(r"(?:(?:docker\.io|registry-1\.docker\.io)/)?(?:library/)?postgres(?::[^/@\s]+)?(?:@sha256:[0-9a-f]{64})?", container.get("image", ""))
    ]
    require({container["id"] for container in discovered} == set(by_id), "postgres_inventory_incomplete")
    application = [entry for entry in declared if entry["classification"] == "application_data"]
    require(len(application) == 1 and application[0]["container_id"] == selected, "postgres_single_managed_cluster")
    observed = []
    for container in discovered:
        entry = by_id[container["id"]]
        labels = container.get("labels") or {}
        require(
            container.get("image_id") == entry["image_id"]
            and container.get("image") == entry.get("image")
            and labels.get("com.docker.compose.project") == entry["compose_project"]
            and labels.get("com.docker.compose.service") == entry["compose_service"],
            "postgres_inventory_binding",
        )
        running = container.get("running") is True
        version = None
        if running:
            version = read(["exec", container["id"], "postgres", "--version"]).strip()
            match = re.fullmatch(r"postgres \(PostgreSQL\) ([0-9]+)(?:\.[0-9]+)?[^\n]*", version)
            require(match is not None and int(match[1]) == entry["postgres_major"], "postgres_inventory_observed_major")
        if container["id"] == selected:
            require(entry["postgres_major"] == postgres_major(config), "postgres_selected_major")
        observed.append(dict(entry, running=running, observed_version=version, version_evidence="running_binary" if running else "declared_image_binding_only"))
    return observed


def docker(args: list[str]) -> str:
    env = managed_docker_environment()
    try:
        return subprocess.run(["docker", "--host", "unix:///run/docker.sock", *args], capture_output=True, text=True, env=env, check=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refused("local_docker_read_failed") from exc


def observe(config: dict, *, fetch=get_json, read=docker, files=managed_file, directories=managed_directory) -> dict:
    require(config.get("app") == APP and config.get("project_name") == "buycycle" and SHA.fullmatch(config.get("commit", "")), "preflight_target")
    major = postgres_major(config)
    admin_role = config.get("postgres_admin_role")
    require(isinstance(admin_role, str) and re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", admin_role), "postgres_admin_role")
    issuer = urllib.parse.urlsplit(config.get("access_issuer", ""))
    require(
        config.get("domain") == DOMAIN
        and issuer.scheme == "https"
        and issuer.hostname
        and issuer.hostname.endswith(".cloudflareaccess.com")
        and issuer.path in {"", "/"}
        and not issuer.username
        and not issuer.password
        and not issuer.query
        and not issuer.fragment
        and issuer.port in (None, 443),
        "preflight_access_issuer",
    )
    require(re.fullmatch(r"[0-9a-f]{32}", config.get("cf_account_id", "")) and re.fullmatch(r"[0-9a-f]{32}", config.get("cf_zone_id", "")), "preflight_account")
    for key in ("cf_application_id", "otp_provider_id", "access_policy_id", "tunnel_id"):
        require(re.fullmatch(r"[0-9a-f-]{36}", config.get(key, "")), "preflight_provider_id")
    journal = directories(config["journal_dir"])
    active_receipt = Path(config.get("active_release_receipt", str(journal / "active.json")))
    require(active_receipt == journal / "active.json", "active_receipt_path")
    if active_receipt.exists() or active_receipt.is_symlink():
        files(str(active_receipt), secret=True)
    compose_file = files(config["compose_path"])
    env_file = files(config["managed_env_file"], secret=True)
    compose_hash, env_hash = digest(compose_file), digest(env_file)
    require(compose_hash == config["compose_sha256"] and env_hash == config["managed_env_sha256"], "preflight_config_hash")
    engine = json.loads(read(["info", "--format", '{"ID":{{json .ID}},"Architecture":{{json .Architecture}},"OSType":{{json .OSType}}}']))
    require(engine.get("ID") == config["expected_docker_engine_id"] and engine.get("Architecture") in {"arm64", "aarch64"} and engine.get("OSType") == "linux", "preflight_engine")
    ids = read(["ps", "-aq", "--no-trunc"]).split()
    require(len(ids) <= 500, "preflight_container_inventory")
    template = '{"id":{{json .Id}},"name":{{json .Name}},"labels":{{json .Config.Labels}},"running":{{json .State.Running}},"restart":{{json .HostConfig.RestartPolicy.Name}},"ports":{{json .NetworkSettings.Ports}},"image":{{json .Config.Image}},"image_id":{{json .Image}}}'
    containers = [json.loads(read(["inspect", "--format", template, identifier])) for identifier in ids]
    compose = json.loads(read(["compose", "--project-name", "buycycle", "--env-file", str(env_file), "-f", str(compose_file), "config", "--format", "json"]))
    validate_compose(config, compose, containers)
    needed = {item["source"] for name in ("app", "migrate", "tunnel") for item in compose["services"][name].get("secrets", [])}
    owners = {"runtime_database_url": 10001, "migrator_database_url": 10001, "tunnel_token": 65532}
    require(needed == owners.keys(), "managed_secret_scope")
    for name in needed:
        secret = compose.get("secrets", {})[name]
        path = secret.get("file")
        require(path in config.get("secret_owners", {}), "managed_secret_inventory")
        require(config["secret_owners"][path] == owners[name], "managed_secret_owner")
        files(path, uid=owners[name], secret=True)
    cf_base = "https://api.cloudflare.com/client/v4/accounts/" + config["cf_account_id"]
    token = config["cloudflare_token_file"]
    organization = cf_result(fetch(cf_base + "/access/organizations", token))
    require(organization.get("auth_domain") == issuer.hostname, "access_team_issuer")
    app_base = cf_base + "/access/apps/" + config["cf_application_id"]
    application = cf_result(fetch(app_base, token))
    policies = cf_result(fetch(app_base + "/policies?per_page=100", token), collection=True)
    identity = cf_result(fetch(cf_base + "/access/identity_providers/" + config["otp_provider_id"], token))
    tunnel_base = cf_base + "/cfd_tunnel/" + config["tunnel_id"]
    tunnel = cf_result(fetch(tunnel_base, token))
    routes = cf_result(fetch(tunnel_base + "/configurations", token))
    dns_url = "https://api.cloudflare.com/client/v4/zones/" + config["cf_zone_id"] + "/dns_records?type=CNAME&name=" + DOMAIN + "&per_page=100"
    dns = cf_result(fetch(dns_url, token), collection=True)
    validate_access(config, application, policies, identity, tunnel, routes, dns, organization=organization)
    base = config["coolify_base_url"].rstrip("/")
    require(urllib.parse.urlsplit(base).scheme == "https", "coolify_https")
    legacy = fetch(base + "/applications/" + APP, config["coolify_token_file"])
    tasks = fetch(base + "/applications/" + APP + "/scheduled-tasks", config["coolify_token_file"])
    validate_legacy(legacy, tasks, containers)
    pg = config["postgres_container"]
    selected_pg = [container for container in containers if container.get("id") == pg or container.get("name", "").lstrip("/") == pg]
    require(len(selected_pg) == 1 and selected_pg[0].get("running") is True, "postgres_container_inventory")
    require(
        all(binding.get("HostIp") in {"127.0.0.1", "::1"} for bindings in (selected_pg[0].get("ports") or {}).values() for binding in bindings or []),
        "postgres_running_loopback_only",
    )
    inventory = postgres_inventory(config, containers, read)
    grants = json.loads(read(["exec", pg, "psql", "--no-psqlrc", "-U", admin_role, "-d", "buycycle", "-At", "-v", "ON_ERROR_STOP=1", "-c", database_query(major)]))
    require(
        grants.get("passed") is True
        and type(grants.get("server_version_num")) is int
        and grants["server_version_num"] // 10000 == major
        and grants.get("current_user") == admin_role
        and grants.get("current_database") == "buycycle",
        "database_grants",
    )
    return {
        "version": 1,
        "passed": True,
        "commit": config["commit"],
        "target": {"host": "pi", "app": APP},
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "docker_engine_id": engine["ID"],
        "compose_sha256": compose_hash,
        "managed_env_sha256": env_hash,
        "legacy_collector_fenced": True,
        "source_builds_disabled": True,
        "origin_unpublished": True,
        "access_policy_verified": True,
        "database_grants_verified": True,
        "managed_secrets_verified": True,
        "postgres_major": major,
        "postgres_server_version_num": grants["server_version_num"],
        "postgres_inventory": inventory,
        "p018_single_cluster_observed": len(inventory) == 1,
        "p018_host_wide_compliance_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = json.loads(managed_file(str(args.config)).read_text())
        result = observe(config)
        require(args.output.is_absolute() and not args.output.exists(), "receipt_output_new_absolute")
        for parent in [args.output.parent, *args.output.parent.parents]:
            info = parent.lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022, "receipt_parent_protection")
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(result, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        parent_fd = os.open(args.output.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        print(json.dumps({"passed": True, "receipt": str(args.output)}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.SubprocessError) as exc:
        code = str(exc) if isinstance(exc, Refused) else "preflight_input_or_read_failed"
        print(json.dumps({"passed": False, "reason": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
