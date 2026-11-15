"""Firstout-only operator promotion of a GitHub-tested immutable image.

This command does not grant approval. The operator must have Leo's explicit
release consent. It uses the operator's existing gh/Railway sessions; no
production credentials are added to GitHub and no other app is enabled.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import ipaddress
import json
import re
import shlex
import subprocess
import sys
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any, NamedTuple

REPOSITORY = "F0rge/f0rge"
PROJECT = "c76d8df1-d839-454c-a94a-79b930deaf38"
ENVIRONMENT = "9f7b0c34-bd95-442b-b746-a9791dcc2895"
WORKFLOW = ".github/workflows/release-firstout.yml"
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
SCHEMA_REVISION = re.compile(r"[0-9]{3}_[a-z0-9_]{1,60}\Z")


class ReleaseProfile(NamedTuple):
    component: str
    service: str
    service_name: str
    image: str
    tag: re.Pattern[str]
    artifact: str
    manifest_file: str
    checks: tuple[str, ...]
    health: str


FRONTEND = ReleaseProfile(
    "frontend",
    "10838be1-7a37-4dfc-810a-8805d040d5d7",
    "firstout-frontend",
    "ghcr.io/f0rge/firstout-frontend",
    re.compile(r"release/firstout-frontend/railway/[0-9]{8}T[0-9]{6}Z\Z"),
    "firstout-release-evidence",
    "firstout-release.json",
    ("unit", "lint", "typecheck", "container_smoke"),
    "https://firstout.co.za/healthz",
)
API = ReleaseProfile(
    "api",
    "77a83033-b75e-4da1-88d0-b6db39bcedaf",
    "firstout-api",
    "ghcr.io/f0rge/firstout-api",
    re.compile(r"release/firstout-api/railway/[0-9]{8}T[0-9]{6}Z\Z"),
    "firstout-api-release-evidence",
    "firstout-api-release.json",
    ("unit", "lint", "format", "migrations", "container_smoke"),
    "https://api.firstout.co.za/api/v1/health",
)
PROFILES = {profile.component: profile for profile in (FRONTEND, API)}
# Retained aliases keep existing frontend operator integrations compatible.
SERVICE, IMAGE, TAG, CHECKS, HEALTH = (
    FRONTEND.service,
    FRONTEND.image,
    FRONTEND.tag,
    FRONTEND.checks,
    FRONTEND.health,
)
API_LEGACY_START = "uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"
API_LEGACY_PREDEPLOY = [
    "/bin/sh -c 'DATABASE_URL=\"${MIGRATION_DATABASE_URL:-$DATABASE_URL}\" uv run alembic upgrade head'"
]


class ReleaseError(RuntimeError):
    pass


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ReleaseError(message)


def profile_for(component: str) -> ReleaseProfile:
    require(component in PROFILES, "Unsupported Firstout component")
    return PROFILES[component]


def known_profile(profile: ReleaseProfile) -> None:
    require(profile in (FRONTEND, API), "Unsupported Firstout release profile")


def command(args: list[str], *, binary: bool = False) -> Any:
    result = subprocess.run(args, capture_output=True, check=False, timeout=90)
    # Command stderr can contain tokens or provider request bodies; never echo it.
    require(result.returncode == 0, f"{args[0]} command failed; inspect it privately")
    return result.stdout if binary else json.loads(result.stdout)


def github(path: str, *, binary: bool = False) -> Any:
    return command(["gh", "api", f"repos/{REPOSITORY}/{path}"], binary=binary)


def railway(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    result = command(["railway", "api", query, "--variables", json.dumps(variables)])
    require(not result.get("errors"), "Railway rejected the request")
    return result["data"]


def validate_manifest(
    manifest: dict[str, Any], run: dict[str, Any], profile: ReleaseProfile = FRONTEND
) -> None:
    known_profile(profile)
    require(manifest.get("schema_version") == 1, "Unsupported artifact schema")
    require(
        manifest.get("component", "frontend") == profile.component,
        "Artifact component mismatch",
    )
    require(manifest.get("repository") == REPOSITORY, "Wrong artifact repository")
    require(
        SHA.fullmatch(str(manifest.get("source_commit", ""))), "Invalid source commit"
    )
    require(
        SHA.fullmatch(str(manifest.get("workflow_commit", ""))),
        "Invalid workflow commit",
    )
    require(
        profile.tag.fullmatch(str(manifest.get("release_tag", ""))),
        "Invalid release tag",
    )
    require(manifest.get("platform") == "linux/amd64", "Wrong image platform")
    require(
        manifest.get("target")
        == {"project": PROJECT, "environment": ENVIRONMENT, "service": profile.service},
        "Wrong artifact target",
    )
    require(DIGEST.fullmatch(str(manifest.get("digest", ""))), "Invalid image digest")
    require(
        manifest.get("image") == f"{profile.image}@{manifest['digest']}",
        "Wrong image reference",
    )
    require(manifest.get("tested") is True, "Artifact is not tested")
    require(
        all(manifest.get("checks", {}).get(key) is True for key in profile.checks),
        "Missing tests",
    )
    if profile == API:
        require(
            SCHEMA_REVISION.fullmatch(str(manifest.get("schema_revision", ""))),
            "Missing or invalid tested API schema revision",
        )
    require(
        run.get("status") == "completed" and run.get("conclusion") == "success",
        "Run not successful",
    )
    require(
        run.get("event") == "workflow_dispatch" and run.get("head_branch") == "main",
        "Wrong run origin",
    )
    require(run.get("path") == WORKFLOW, "Wrong release workflow")
    require(
        run.get("repository", {}).get("full_name") == REPOSITORY, "Wrong run repository"
    )
    require(
        manifest.get("workflow_commit") == run.get("head_sha"),
        "Workflow commit mismatch",
    )
    require(manifest.get("workflow_run_id") == run.get("id"), "Run ID mismatch")
    require(
        manifest.get("workflow_run_attempt") == run.get("run_attempt"),
        "Stale run attempt",
    )


def verified_source_checks(commit: str) -> list[dict[str, Any]]:
    result = github(f"commits/{commit}/check-runs?per_page=100")
    require(result.get("total_count", 0) <= 100, "Unexpected check pagination")
    expected = {
        "ci": ".github/workflows/ci.yml",
        "playwright smoke": ".github/workflows/e2e-smoke.yml",
    }
    checks = []
    for name, workflow in expected.items():
        candidates = [
            item
            for item in result.get("check_runs", [])
            if item.get("name") == name
            and item.get("app", {}).get("slug") == "github-actions"
        ]
        require(candidates, f"Missing source check: {name}")
        check = max(candidates, key=lambda item: item["id"])
        require(
            check.get("head_sha") == commit
            and check.get("status") == "completed"
            and check.get("conclusion") == "success",
            f"Source check is not successful: {name}",
        )
        match = re.fullmatch(
            r"https://github\.com/F0rge/f0rge/actions/runs/([0-9]+)/job/[0-9]+",
            check.get("details_url", ""),
        )
        require(match, f"Unexpected source-check URL: {name}")
        run = github(f"actions/runs/{match[1]}")
        require(
            run.get("repository", {}).get("full_name") == REPOSITORY
            and run.get("head_branch") == "main"
            and run.get("event") in ("push", "workflow_dispatch")
            and run.get("head_sha") == commit
            and run.get("path") == workflow
            and run.get("status") == "completed"
            and run.get("conclusion") == "success",
            f"Source-check workflow identity mismatch: {name}",
        )
        checks.append(
            {
                "name": name,
                "check_id": check["id"],
                "run_id": run["id"],
                "run_attempt": run["run_attempt"],
                "commit": commit,
            }
        )
    return checks


def verified_artifact(
    run_id: int, profile: ReleaseProfile = FRONTEND
) -> dict[str, Any]:
    known_profile(profile)
    require(run_id > 0, "Invalid run ID")
    run = github(f"actions/runs/{run_id}")
    artifact_list = github(f"actions/runs/{run_id}/artifacts?per_page=100")
    require(
        artifact_list.get("total_count", 0) <= 100, "Unexpected artifact pagination"
    )
    artifacts = [
        item
        for item in artifact_list.get("artifacts", [])
        if item.get("name") == profile.artifact and not item.get("expired")
    ]
    require(len(artifacts) == 1, "Need one current release-evidence artifact")
    artifact = artifacts[0]
    require(
        artifact.get("size_in_bytes", 0) < 1_000_000,
        "Evidence archive is unexpectedly large",
    )
    archive = github(f"actions/artifacts/{artifact['id']}/zip", binary=True)
    archive_digest = "sha256:" + hashlib.sha256(archive).hexdigest()
    require(
        archive_digest == artifact.get("digest"),
        "GitHub artifact archive digest mismatch",
    )
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        require(
            zipped.namelist() == [profile.manifest_file],
            "Unexpected artifact entries",
        )
        info = zipped.getinfo(profile.manifest_file)
        require(info.file_size < 100_000, "Evidence manifest is unexpectedly large")
        manifest = json.loads(zipped.read(info))
    validate_manifest(manifest, run, profile)
    ref = github("git/ref/tags/" + manifest["release_tag"])["object"]
    if ref["type"] == "tag":
        ref = github("git/tags/" + ref["sha"])["object"]
    require(
        ref["type"] == "commit" and ref["sha"] == manifest["source_commit"],
        "Release tag moved",
    )
    comparison = github(f"compare/{manifest['source_commit']}...main")
    require(
        comparison.get("status") in ("ahead", "identical"),
        "Source commit is not on main",
    )
    checks = verified_source_checks(manifest["source_commit"])
    return {
        "manifest": manifest,
        "run_id": run_id,
        "run_attempt": run["run_attempt"],
        "artifact_id": artifact["id"],
        "artifact_digest": archive_digest,
        "workflow_commit": run["head_sha"],
        "source_checks": checks,
    }


def provider_state(profile: ReleaseProfile = FRONTEND) -> dict[str, Any]:
    known_profile(profile)
    service = profile.service
    # config is requested encrypted. Only this service's nonsecret fields leave
    # this function; credentials and other services' configuration are discarded.
    data = railway(
        """query($project:String!,$env:String!,$service:String!) {
      project(id:$project) { id deploymentTriggers(first:100) {
        pageInfo { hasNextPage } edges { node { id serviceId environmentId branch repository } }
      } }
      environment(id:$env,projectId:$project) { id name projectId config(decryptVariables:false) }
      serviceInstance(serviceId:$service,environmentId:$env) {
        serviceId environmentId serviceName source { repo image }
        activeDeployments { id status projectId environmentId serviceId canRollback
          meta instances { id status } }
        latestDeployment { id status meta }
      }
      environmentStagedChanges(environmentId:$env) { id patch status }
    }""",
        {"project": PROJECT, "env": ENVIRONMENT, "service": service},
    )
    environment = data["environment"]
    triggers = data["project"]["deploymentTriggers"]
    require(
        not triggers["pageInfo"]["hasNextPage"],
        "Unexpected deployment-trigger pagination",
    )
    require(
        environment["id"] == ENVIRONMENT and environment["projectId"] == PROJECT,
        "Provider target mismatch",
    )
    state = data["serviceInstance"]
    require(
        state["serviceId"] == service and state["environmentId"] == ENVIRONMENT,
        "Service target mismatch",
    )
    config = environment["config"].get("services", {}).get(service)
    require(isinstance(config, dict), "Missing service configuration")
    safe_config = {
        key: config[key]
        for key in ("source", "build", "deploy", "networking")
        if key in config
    }
    safe_config = redact_configuration(safe_config)
    deployments = []
    for item in state["activeDeployments"]:
        meta = item.pop("meta") or {}
        deployments.append(
            {
                **item,
                "image_digest": meta.get("imageDigest"),
                "image": meta.get("image"),
                "commit": meta.get("commitHash"),
            }
        )
    latest = state.get("latestDeployment")
    if latest:
        meta = latest.pop("meta") or {}
        latest.update(image_digest=meta.get("imageDigest"), image=meta.get("image"))
    return {
        "project": PROJECT,
        "environment": ENVIRONMENT,
        "service": service,
        "service_name": state["serviceName"],
        "source": state["source"],
        "active_deployments": deployments,
        "latest_deployment": latest,
        "config": safe_config,
        "pending_patch": bool(data["environmentStagedChanges"]["patch"]),
        "deployment_triggers": [edge["node"] for edge in triggers["edges"]],
    }


def redact_configuration(value: Any) -> Any:
    """Retain drift evidence without durable copies of registry credentials."""
    if isinstance(value, dict):
        return {
            key: {"configured": bool(item)}
            if any(
                word in key.lower()
                for word in ("credential", "password", "secret", "token")
            )
            else redact_configuration(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_configuration(item) for item in value]
    return value


def running_instance_ids(deployment: dict[str, Any]) -> list[str]:
    """Verify one serving replica while retaining fail-closed rollout checks.

    Railway retains terminal REMOVED instance history on successful deployments,
    including deployments that ran a pre-deploy command. Every other status still
    participates in the single-replica check; unhealthy or unsettled instances
    must not disappear merely because they are not RUNNING yet.
    """
    instances = [
        item for item in deployment["instances"] if item["status"] != "REMOVED"
    ]
    require(
        len(instances) == 1 and instances[0]["status"] == "RUNNING",
        "Expected the configured single running replica",
    )
    return [instances[0]["id"]]


def stable_deployment(
    state: dict[str, Any],
    digest: str,
    deployment_id: str,
    profile: ReleaseProfile = FRONTEND,
) -> list[str]:
    known_profile(profile)
    require(state["service"] == profile.service, "Serving component target mismatch")
    require(
        state["source"].get("image") == f"{profile.image}@{digest}",
        "Image source differs from approved artifact",
    )
    require(not state["source"].get("repo"), "Git source remains enabled")
    source = state["config"].get("source", {})
    require(
        not source.get("repo")
        and not source.get("branch")
        and not source.get("commitSha"),
        "Mutable Git source remains configured",
    )
    require(
        source.get("autoUpdates", {}).get("type") == "disabled",
        "Image auto-updates are enabled",
    )
    require(not state.get("pending_patch"), "Environment has pending changes")
    require(not state.get("deployment_triggers"), "Git deployment triggers are enabled")
    if profile == API:
        deploy = state["config"].get("deploy", {})
        require(
            not deploy.get("preDeployCommand") and not deploy.get("startCommand"),
            "API must use the tested image command without automatic migrations",
        )
    active = state["active_deployments"]
    require(
        len(active) == 1,
        "Expected exactly one active deployment; wait for rollout to settle",
    )
    deployment = active[0]
    require(deployment["id"] == deployment_id, "Serving deployment differs")
    require(deployment["status"] == "SUCCESS", "Serving deployment is not successful")
    require(
        deployment["projectId"] == PROJECT
        and deployment["environmentId"] == ENVIRONMENT
        and deployment["serviceId"] == state["service"],
        "Serving target mismatch",
    )
    require(
        deployment["image_digest"] == digest, "Provider running-image digest differs"
    )
    return running_instance_ids(deployment)


def unchanged_runtime(
    before: dict[str, Any], after: dict[str, Any], profile: ReleaseProfile = FRONTEND
) -> None:
    known_profile(profile)
    for key in ("build", "deploy", "networking"):
        original = before["config"].get(key)
        current = after["config"].get(key)
        if profile == API and key == "deploy":
            original = dict(original or {})
            current = dict(current or {})
            for override in ("preDeployCommand", "startCommand"):
                require(
                    not current.pop(override, None),
                    "API command override remains configured",
                )
                original.pop(override, None)
        require(
            original == current,
            f"Unexpected {key} configuration change",
        )


def api_runtime_patch(before: dict[str, Any]) -> dict[str, Any]:
    """Remove only the known legacy hooks as part of an approved API promotion."""
    deploy = before["config"].get("deploy", {})
    require(
        deploy.get("preDeployCommand") in (None, [], "", API_LEGACY_PREDEPLOY),
        "Unexpected API predeploy command; review it before promotion",
    )
    require(
        deploy.get("startCommand") in (None, "", API_LEGACY_START),
        "Unexpected API start command; review it before promotion",
    )
    return {"preDeployCommand": None, "startCommand": None}


def api_schema() -> dict[str, Any]:
    """Read the database revision through the fixed API runtime, without credentials."""
    script = """import asyncio,json,sys
sys.path.insert(0,'/app/apps/firstout/backend')
from sqlalchemy import text
from app.database import engine
async def main():
    try:
        async with engine.connect() as conn:
            conn=await conn.execution_options(isolation_level='SERIALIZABLE',postgresql_readonly=True)
            async with conn.begin():
                await conn.execute(text("SET LOCAL statement_timeout='10000'"))
                versions=(await conn.execute(text('SELECT version_num FROM alembic_version'))).scalars().all()
                if len(versions)!=1:raise RuntimeError('Expected one migration head')
                role=dict((await conn.execute(text("SELECT current_user AS role,rolsuper,rolbypassrls,EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND pg_has_role(current_user,c.relowner,'MEMBER')) AS owns_public_tables,EXISTS(SELECT 1 FROM pg_roles r WHERE (r.rolsuper OR r.rolbypassrls) AND pg_has_role(current_user,r.oid,'MEMBER')) AS can_assume_bypass_role FROM pg_roles WHERE rolname=current_user"))).mappings().one())
                identity=dict((await conn.execute(text('SELECT current_database() AS database_name,host(inet_server_addr()) AS server_address,inet_server_port() AS server_port'))).mappings().one())
                print(json.dumps({'schema_revision':versions[0],'runtime_role':role,'database_identity':identity}))
    finally:
        await engine.dispose()
asyncio.run(main())
"""
    result = command(
        [
            "railway",
            "ssh",
            "--project",
            PROJECT,
            "--environment",
            ENVIRONMENT,
            "--service",
            API.service,
            "--",
            shlex.join(["/app/apps/firstout/backend/.venv/bin/python", "-c", script]),
        ]
    )
    validate_api_schema_metadata(result)
    return result


def validate_api_schema_metadata(result: dict[str, Any]) -> None:
    require(
        isinstance(result, dict)
        and set(result) == {"schema_revision", "runtime_role", "database_identity"},
        "Unexpected API database metadata shape",
    )
    require(
        SCHEMA_REVISION.fullmatch(str(result.get("schema_revision", ""))),
        "Unexpected API database revision",
    )
    role = result.get("runtime_role", {})
    require(
        isinstance(role, dict)
        and set(role)
        == {
            "role",
            "rolsuper",
            "rolbypassrls",
            "owns_public_tables",
            "can_assume_bypass_role",
        }
        and isinstance(role.get("role"), str)
        and 0 < len(role["role"].encode()) <= 63
        and role.get("rolsuper") is False
        and role.get("rolbypassrls") is False
        and role.get("owns_public_tables") is False
        and role.get("can_assume_bypass_role") is False,
        "API database role bypasses isolation",
    )
    identity = result["database_identity"]
    require(
        isinstance(identity, dict)
        and set(identity) == {"database_name", "server_address", "server_port"}
        and isinstance(identity.get("database_name"), str)
        and 0 < len(identity["database_name"].encode()) <= 63
        and isinstance(identity.get("server_address"), str)
        and type(identity.get("server_port")) is int
        and 1 <= identity["server_port"] <= 65535,
        "Unexpected API database identity",
    )
    try:
        ipaddress.ip_address(identity["server_address"])
    except ValueError as exc:
        raise ReleaseError("Unexpected API database server address") from exc


def write_receipt(
    path: Path, value: dict[str, Any], *, exclusive: bool = False
) -> None:
    if exclusive:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
        path.chmod(0o600)
    else:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
        temporary.chmod(0o600)
        temporary.replace(path)


def promote(
    run_id: int,
    receipt_path: Path,
    approval_reference: str,
    profile: ReleaseProfile = FRONTEND,
) -> dict[str, Any]:
    known_profile(profile)
    require(
        bool(approval_reference.strip()),
        "An existing explicit approval reference is required",
    )
    evidence = verified_artifact(run_id, profile)
    before = provider_state(profile)
    require(before["service_name"] == profile.service_name, "Unexpected service name")
    require(
        not before["pending_patch"],
        "Refusing to commit an environment with pending changes",
    )
    require(
        not before["deployment_triggers"],
        "Git deployment triggers must remain contained",
    )
    active = before["active_deployments"]
    require(
        len(active) == 1
        and active[0]["status"] == "SUCCESS"
        and active[0]["canRollback"],
        "Need one healthy rollback-capable deployment",
    )
    require(
        DIGEST.fullmatch(str(active[0]["image_digest"] or "")),
        "Missing rollback image identity",
    )
    require(
        before["source"].get("image") != evidence["manifest"]["image"],
        "Artifact already selected; verify it instead of redeploying",
    )
    runtime_patch = api_runtime_patch(before) if profile == API else None
    schema_before = api_schema() if profile == API else None
    if schema_before:
        require(
            schema_before["schema_revision"] == evidence["manifest"]["schema_revision"],
            "Run the controlled API migration step before promotion",
        )
    receipt = {
        "schema_version": 1,
        "component": profile.component,
        "state": "submission_started",
        "approval_reference": approval_reference,
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "evidence": evidence,
        "before": before,
    }
    if schema_before:
        receipt.update(
            schema_before=schema_before, planned_runtime_overrides=runtime_patch
        )
    # A durable exclusive journal prevents accidentally reusing the same operator
    # command after a lost submission response. Never blindly retry a mutation.
    write_receipt(receipt_path, receipt, exclusive=True)
    patch = {
        "services": {
            profile.service: {
                "source": {
                    "repo": None,
                    "branch": None,
                    "commitSha": None,
                    "image": evidence["manifest"]["image"],
                    "autoUpdates": {"type": "disabled"},
                }
            }
        }
    }
    if runtime_patch is not None:
        patch["services"][profile.service]["deploy"] = runtime_patch
    try:
        result = railway(
            """mutation($env:String!,$patch:EnvironmentConfig!,$message:String!) {
          environmentPatchCommit(environmentId:$env,patch:$patch,commitMessage:$message,skipDeploys:false)
        }""",
            {
                "env": ENVIRONMENT,
                "patch": patch,
                "message": f"Approved Firstout release {evidence['manifest']['release_tag']}",
            },
        )
        receipt.update(state="submitted", workflow_id=result["environmentPatchCommit"])
    except Exception:
        receipt["state"] = "submission_outcome_unknown"
        write_receipt(receipt_path, receipt)
        raise
    write_receipt(receipt_path, receipt)
    return receipt


def verify(
    receipt_path: Path, deployment_id: str, profile: ReleaseProfile = FRONTEND
) -> dict[str, Any]:
    known_profile(profile)
    uuid.UUID(deployment_id)
    receipt = json.loads(receipt_path.read_text())
    require(
        receipt.get("component", "frontend") == profile.component,
        "Receipt component mismatch",
    )
    if profile == API:
        validate_api_schema_metadata(receipt.get("schema_before"))
    evidence = verified_artifact(receipt["evidence"]["run_id"], profile)
    require(evidence == receipt["evidence"], "Trusted artifact evidence changed")
    digest = evidence["manifest"]["digest"]
    first = provider_state(profile)
    unchanged_runtime(receipt["before"], first, profile)
    instances = stable_deployment(first, digest, deployment_id, profile)
    schema_first = api_schema() if profile == API else None
    if schema_first:
        require(
            schema_first["schema_revision"] == evidence["manifest"]["schema_revision"],
            "Serving API schema differs from the tested artifact",
        )
        require(
            schema_first == receipt["schema_before"],
            "Serving API database identity or runtime role differs from pre-promotion evidence",
        )
    request = urllib.request.Request(
        profile.health, headers={"User-Agent": "Firstout-release-verification"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        require(
            response.status == 200 and response.geturl() == profile.health,
            "Unexpected health response",
        )
        require(
            "no-store" in response.headers.get("Cache-Control", ""),
            "Health response may be stale",
        )
        health_body = response.read(4097)
    require(len(health_body) <= 4096, "Unexpected health payload")
    require(json.loads(health_body) == {"status": "ok"}, "Application is not healthy")
    second = provider_state(profile)
    unchanged_runtime(receipt["before"], second, profile)
    require(
        stable_deployment(second, digest, deployment_id, profile) == instances,
        "Serving instances changed during health check",
    )
    schema_second = api_schema() if profile == API else None
    require(
        schema_second == schema_first,
        "API database identity changed during verification",
    )
    receipt.update(
        state="verified",
        verified_at=dt.datetime.now(dt.UTC).isoformat(),
        deployment_id=deployment_id,
        instances=instances,
        provider=second,
        health={"url": profile.health, "status": 200},
        verification_limit="Provider deployment imageDigest mapped to its running instances; not executable attestation",
    )
    if schema_second:
        receipt["schema_after"] = schema_second
    write_receipt(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    inspect = subs.add_parser(
        "inspect", help="Read the fixed production target without secrets"
    )
    inspect.add_argument("--output", type=Path, required=True)
    prepare = subs.add_parser(
        "evidence",
        help="Download and authenticate tested image evidence; no deployment",
    )
    prepare.add_argument("--run-id", type=int, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    release = subs.add_parser(
        "promote",
        help="Deploy the approved CI image to the selected fixed Firstout service",
    )
    release.add_argument("--run-id", type=int, required=True)
    release.add_argument("--approval-reference", required=True)
    release.add_argument("--receipt", type=Path, required=True)
    verification = subs.add_parser(
        "verify", help="Read back the exact serving image, replicas and health"
    )
    verification.add_argument("--receipt", type=Path, required=True)
    verification.add_argument("--deployment-id", required=True)
    for sub in (inspect, prepare, release, verification):
        sub.add_argument("--component", choices=tuple(PROFILES), default="frontend")
    args = parser.parse_args()
    try:
        profile = profile_for(args.component)
        if args.command == "inspect":
            write_receipt(args.output, provider_state(profile), exclusive=True)
        elif args.command == "evidence":
            write_receipt(
                args.output, verified_artifact(args.run_id, profile), exclusive=True
            )
        elif args.command == "promote":
            promote(args.run_id, args.receipt, args.approval_reference, profile)
        else:
            verify(args.receipt, args.deployment_id, profile)
        print(f"Firstout release {args.command}: completed")
        return 0
    except (
        ReleaseError,
        OSError,
        ValueError,
        KeyError,
        subprocess.TimeoutExpired,
    ) as error:
        # Avoid echoing malformed input or provider payloads in failures.
        print(
            f"Firstout release {args.command}: blocked ({type(error).__name__}); inspect private evidence",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
