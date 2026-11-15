"""Firstout-only automatic image promotion and verified application recovery.

The GitHub issue is a durable public journal: it contains only allowlisted image,
provider identity and phase data, never variables or credentials. An open journal
blocks another release until recovery is explicitly reconciled. External calls
are the test seam; this module never downgrades or restores PostgreSQL.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import firstout_release as legacy

PROJECT = legacy.PROJECT
ENVIRONMENT = legacy.ENVIRONMENT
REPOSITORY = legacy.REPOSITORY
SERVICES = {
    "backend": "77a83033-b75e-4da1-88d0-b6db39bcedaf",
    "frontend": legacy.SERVICE,
}
DATABASE = "a1a6695d-b8fb-4c79-92a6-664b48bc07e4"
IMAGES = {name: f"ghcr.io/f0rge/firstout-{name}" for name in SERVICES}
HEALTH = {
    "backend": "https://api.firstout.co.za/api/v1/health",
    "frontend": legacy.HEALTH,
}
READY = "https://api.firstout.co.za/api/v1/ready"
PAUSE = "[Firstout CD paused]"
PREFIX = "[Firstout CD] "
MIGRATE = "uv run --no-sync python -m app.commands.release_migrate"
MAX_WAIT_SECONDS = 900
MONITOR_SAMPLES = 6
POLL_SECONDS = 10
BACKUP_MAX_AGE_HOURS = 24
CHECKS = (
    "unit",
    "lint",
    "typecheck",
    "container_smoke",
    "migration_compatibility",
    "backend_http",
)

ReleaseError = legacy.ReleaseError


class AmbiguousRelease(ReleaseError):
    """An external mutation cannot yet be proved settled; no competing mutation."""


require = legacy.require


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def github(path: str, method: str = "GET", body: Any = None) -> Any:
    args = ["gh", "api", f"repos/{REPOSITORY}/{path}", "--method", method]
    if body is not None:
        args += ["--input", "-"]
    result = subprocess.run(
        args,
        input=json.dumps(body).encode() if body is not None else None,
        capture_output=True,
        timeout=90,
        check=False,
    )
    require(result.returncode == 0, "GitHub request failed; inspect privately")
    return json.loads(result.stdout)


def release_issues() -> list[dict[str, Any]]:
    found = []
    for page in range(1, 11):
        items = github(
            f"issues?state=all&sort=created&direction=desc&per_page=100&page={page}"
        )
        require(isinstance(items, list), "Invalid issue listing")
        for item in items:
            if "pull_request" in item:
                continue
            if item.get("title", "").startswith(PREFIX) and bot_owned(item):
                found.append(item)
            elif item.get("title") == PAUSE:
                actor = item.get("user", {}).get("login", "")
                require(
                    re.fullmatch(r"[a-zA-Z0-9-]{1,100}", actor), "Invalid pause actor"
                )
                if github(f"collaborators/{actor}/permission").get("permission") in (
                    "admin",
                    "maintain",
                    "write",
                ):
                    found.append(item)
        if len(items) < 100:
            return found
    raise ReleaseError(
        "Issue pagination exceeded safety bound; reconcile release history"
    )


def bot_owned(issue: dict[str, Any]) -> bool:
    return (
        issue.get("user", {}).get("login") == "github-actions[bot]"
        and issue.get("user", {}).get("type") == "Bot"
    )


def read_journal(issue: dict[str, Any]) -> dict[str, Any]:
    require(bot_owned(issue), "Only bot-owned release journals are authoritative")
    match = re.fullmatch(r"```json\n(.+)\n```", issue.get("body", ""), re.DOTALL)
    require(match, "Invalid durable release journal")
    value = json.loads(match[1])
    number = issue.get("number")
    require(type(number) is int and number > 0, "Invalid journal issue number")
    # GitHub assigns the issue number only after the initial POST. A process
    # interruption before its first PATCH must remain safely recoverable.
    require(value.get("issue_number", number) == number, "Journal issue number differs")
    value["issue_number"] = number
    require(
        value.get("schema_version") == 1
        and legacy.SHA.fullmatch(value.get("source_commit", "")),
        "Invalid journal identity",
    )
    require(
        issue.get("title") == PREFIX + value["source_commit"], "Journal title mismatch"
    )
    require(
        value.get("manifest", {}).get("source_commit") == value["source_commit"],
        "Journal manifest differs",
    )
    require(
        set(value.get("before", {})) == set(SERVICES), "Invalid rollback service set"
    )
    require(
        isinstance(value.get("attempted"), list)
        and len(set(value["attempted"])) == len(value["attempted"])
        and set(value["attempted"]) <= set(SERVICES),
        "Invalid attempted service set",
    )
    for name, before in value["before"].items():
        require(
            legacy.DIGEST.fullmatch(before.get("digest", "")), "Invalid rollback digest"
        )
        require(
            before.get("image") == f"{IMAGES[name]}@{before['digest']}",
            "Invalid rollback image",
        )
        uuid.UUID(before["deployment_id"])
        require(
            isinstance(before.get("instances"), list) and len(before["instances"]) == 1,
            "Invalid rollback replica set",
        )
        for instance in before["instances"]:
            uuid.UUID(instance)
    validate_previous_readiness(value["before"]["backend"].get("readiness", {}))
    validate_intent(value)
    return value


def validate_intent(journal: dict[str, Any]) -> None:
    intent = journal.get("intent")
    if intent is None:
        require(
            journal.get("state") != "ambiguous",
            "Ambiguous journal lacks mutation intent",
        )
        return
    require(
        isinstance(intent, dict) and intent.get("service") in journal["attempted"],
        "Invalid mutation service",
    )
    name = intent["service"]
    require(intent.get("phase") in ("release", "recovery"), "Invalid mutation phase")
    expected = (
        journal["before"][name]["image"]
        if intent["phase"] == "recovery"
        else journal["manifest"]["images"][name]["image"]
    )
    require(
        intent.get("image") == expected
        and re.fullmatch(re.escape(IMAGES[name]) + r"@sha256:[0-9a-f]{64}", expected),
        "Invalid mutation image",
    )


def checkpoint(journal: dict[str, Any], path: Path, state: str) -> None:
    journal.update(state=state, updated_at=now())
    body = "```json\n" + json.dumps(journal, sort_keys=True, indent=2) + "\n```"
    require(len(body) < 60_000, "Journal unexpectedly large")
    result = github(f"issues/{journal['issue_number']}", "PATCH", {"body": body})
    require(read_journal(result) == journal, "Journal write was not acknowledged")
    legacy.write_receipt(path, journal)


def validate_manifest(manifest: dict[str, Any]) -> None:
    require(
        manifest.get("schema_version") == 2
        and manifest.get("repository") == REPOSITORY,
        "Wrong release manifest",
    )
    sha = manifest.get("source_commit", "")
    require(legacy.SHA.fullmatch(sha), "Invalid source commit")
    require(
        manifest.get("release_tag") == f"release/firstout/railway/{sha}",
        "Wrong release tag",
    )
    require(manifest.get("platform") == "linux/amd64", "Wrong platform")
    database = manifest.get("database", {})
    require(
        re.fullmatch(r"[0-9a-z_]{1,100}", database.get("schema_revision", "")),
        "Missing database head",
    )
    require(
        re.fullmatch(r"[0-9a-f]{64}", database.get("policy_sha256", "")),
        "Missing migration policy hash",
    )
    require(set(manifest.get("images", {})) == set(SERVICES), "Need both images")
    for name, image in manifest["images"].items():
        require(
            legacy.DIGEST.fullmatch(image.get("digest", "")), "Invalid image digest"
        )
        require(
            image.get("image") == f"{IMAGES[name]}@{image['digest']}",
            "Wrong image registry",
        )
        require(image.get("source_commit") == sha, "Mixed image source versions")
    require(
        re.fullmatch(
            re.escape(IMAGES["backend"]) + r"@sha256:[0-9a-f]{64}",
            manifest.get("previous_backend_image", ""),
        ),
        "Missing tested rollback binary",
    )
    require(
        all(manifest.get("checks", {}).get(key) is True for key in CHECKS),
        "Missing candidate tests",
    )
    assets = manifest.get("frontend_assets", [])
    require(
        isinstance(assets, list) and len(assets) == 2,
        "Need tested frontend JS and CSS assets",
    )
    for asset in assets:
        require(
            re.fullmatch(
                r"/_next/static/[A-Za-z0-9_./-]+\.(?:js|css)", asset.get("path", "")
            )
            and ".." not in asset["path"]
            and re.fullmatch(r"[0-9a-f]{64}", asset.get("sha256", "")),
            "Invalid frontend asset probe",
        )
    require(
        {asset["path"].rsplit(".", 1)[-1] for asset in assets} == {"js", "css"},
        "Need both asset types",
    )
    require(manifest.get("workflow_commit") == sha, "Workflow/source mismatch")
    run = github(f"actions/runs/{int(manifest['workflow_run_id'])}")
    require(
        run.get("repository", {}).get("full_name") == REPOSITORY
        and run.get("head_branch") == "main"
        and run.get("head_sha") == sha
        and run.get("path") == ".github/workflows/cd-firstout.yml"
        and run.get("event") == "workflow_run"
        and run.get("run_attempt") == manifest.get("workflow_run_attempt"),
        "Wrong candidate workflow identity",
    )
    # The controller runs inside this workflow; it cannot yet be completed.
    require(run.get("status") == "in_progress", "Candidate workflow is not active")
    verified_reviewed_source(sha)
    ref = github("git/ref/tags/" + manifest["release_tag"])["object"]
    require(
        ref.get("type") == "commit" and ref.get("sha") == sha, "Release tag mismatch"
    )


def verified_reviewed_source(sha: str) -> None:
    require(legacy.SHA.fullmatch(sha), "Invalid source commit")
    legacy.verified_source_checks(sha)
    pulls = github(f"commits/{sha}/pulls?per_page=100")
    require(len(pulls) < 100, "Unexpected associated PR pagination")
    merged = [
        pr
        for pr in pulls
        if pr.get("merged_at")
        and pr.get("merge_commit_sha") == sha
        and pr.get("base", {}).get("ref") == "main"
        and pr.get("base", {}).get("repo", {}).get("full_name") == REPOSITORY
    ]
    require(len(merged) == 1, "Release must be an identified merged main PR")
    pr = merged[0]
    reviews = github(f"pulls/{pr['number']}/reviews?per_page=100")
    require(len(reviews) < 100, "Unexpected review pagination")
    latest = {}
    for review in sorted(reviews, key=lambda review: review["id"]):
        if review["state"] != "COMMENTED":
            latest[review["user"]["login"]] = review
    approved = False
    for actor, review in latest.items():
        if (
            review["state"] != "APPROVED"
            or review.get("commit_id") != pr["head"]["sha"]
            or actor == pr["user"]["login"]
        ):
            continue
        require(
            re.fullmatch(r"[a-zA-Z0-9-]{1,100}(?:\[bot\])?", actor),
            "Invalid reviewer actor",
        )
        permission = github(
            f"collaborators/{urllib.parse.quote(actor, safe='')}/permission"
        ).get("permission")
        approved = approved or permission in ("admin", "maintain", "write")
    require(
        approved,
        "Merged PR needs an independent approval on its final head from an authorized reviewer",
    )
    main = github("git/ref/heads/main")["object"]["sha"]
    require(
        github(f"compare/{sha}...{main}").get("status") in ("ahead", "identical"),
        "Source is not on main",
    )


def backup_preflight() -> dict[str, Any]:
    data = legacy.railway(
        """query($project:String!,$env:String!){
      environment(id:$env,projectId:$project){id projectId volumeInstances(first:100){
        pageInfo{hasNextPage} edges{node{id serviceId environmentId deletedAt isPendingDeletion}}
      }} }""",
        {"project": PROJECT, "env": ENVIRONMENT},
    )
    env = data["environment"]
    require(
        env["id"] == ENVIRONMENT and env["projectId"] == PROJECT,
        "Backup target mismatch",
    )
    require(
        not env["volumeInstances"]["pageInfo"]["hasNextPage"],
        "Unexpected volume pagination",
    )
    volumes = [
        edge["node"]
        for edge in env["volumeInstances"]["edges"]
        if edge["node"]["serviceId"] == DATABASE
        and not edge["node"]["deletedAt"]
        and not edge["node"]["isPendingDeletion"]
    ]
    require(len(volumes) == 1, "Need one bound Firstout database volume")
    volume = volumes[0]
    require(volume["environmentId"] == ENVIRONMENT, "Wrong backup environment")
    backups = legacy.railway(
        """query($id:String!){volumeInstanceBackupList(volumeInstanceId:$id){
      id createdAt expiresAt externalId usedMB }}""",
        {"id": volume["id"]},
    )["volumeInstanceBackupList"]
    current = dt.datetime.now(dt.UTC)
    usable = []
    for item in backups:
        created = dt.datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00"))
        expiry = (
            dt.datetime.fromisoformat(item["expiresAt"].replace("Z", "+00:00"))
            if item["expiresAt"]
            else None
        )
        if (
            item["externalId"]
            and (item["usedMB"] or 0) > 0
            and (expiry is None or expiry > current)
            and dt.timedelta(0)
            <= current - created
            <= dt.timedelta(hours=BACKUP_MAX_AGE_HOURS)
        ):
            usable.append(item)
    require(usable, "No recent unexpired provider backup record; deployment blocked")
    latest = max(usable, key=lambda item: item["createdAt"])
    return {
        "volume_instance_id": volume["id"],
        "backup_id": latest["id"],
        "created_at": latest["createdAt"],
        "verification_limit": "Provider snapshot identity and age; not a restore drill",
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReleaseError("Health endpoint redirected")


def http_json(url: str) -> dict[str, Any]:
    require(url in (*HEALTH.values(), READY), "Unexpected health target")
    request = urllib.request.Request(
        url, headers={"Cache-Control": "no-cache", "User-Agent": "Firstout-CD"}
    )
    with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
        require(response.status == 200, "Health check failed")
        if url == READY:
            require(
                "no-store" in response.headers.get("Cache-Control", ""),
                "Database readiness response may be cached",
            )
        body = response.read(16385)
        require(len(body) <= 16384, "Health body unexpectedly large")
    return json.loads(body)


def frontend_probe(assets: list[dict[str, str]]) -> None:
    for asset in assets:
        url = "https://firstout.co.za" + asset["path"]
        request = urllib.request.Request(
            url, headers={"Cache-Control": "no-cache", "User-Agent": "Firstout-CD"}
        )
        with urllib.request.build_opener(NoRedirect).open(
            request, timeout=20
        ) as response:
            require(response.status == 200, "Frontend asset unavailable")
            content = response.read(10_000_001)
        require(
            len(content) <= 10_000_000
            and hashlib.sha256(content).hexdigest() == asset["sha256"],
            "Frontend asset differs from tested image",
        )


def safe_before(name: str, state: dict[str, Any]) -> dict[str, Any]:
    require(
        state["service"] == SERVICES[name]
        and state["project"] == PROJECT
        and state["environment"] == ENVIRONMENT,
        "Wrong provider target",
    )
    require(
        state["service_name"]
        == f"firstout-{'api' if name == 'backend' else 'frontend'}",
        "Wrong service",
    )
    require(
        not state["pending_patch"] and not state["deployment_triggers"],
        "Uncontained provider changes/triggers",
    )
    active = state["active_deployments"]
    require(
        len(active) == 1 and active[0]["status"] == "SUCCESS",
        "Need a settled previous deployment",
    )
    previous = active[0]
    require(
        legacy.DIGEST.fullmatch(previous.get("image_digest") or ""),
        "Missing previous image digest",
    )
    source_image = state["source"].get("image") or ""
    require(
        source_image == f"{IMAGES[name]}@{previous['image_digest']}",
        "Bootstrap a verified pinned rollback image before CD activation",
    )
    require(not state["source"].get("repo"), "Mutable Git source enabled")
    require(
        len(previous["instances"]) == 1
        and previous["instances"][0]["status"] == "RUNNING",
        "Previous replica unhealthy",
    )
    # Deliberately never persist runtime variables, registry credentials or full config.
    return {
        "deployment_id": previous["id"],
        "digest": previous["image_digest"],
        "image": source_image,
        "instances": [item["id"] for item in previous["instances"]],
    }


def validate_previous_readiness(ready: dict[str, Any]) -> None:
    require(
        ready.get("status") == "ok"
        and legacy.SHA.fullmatch(ready.get("source_commit", ""))
        and ready.get("migration_receipt") is True
        and re.fullmatch(r"[0-9a-z_]{1,100}", ready.get("schema_revision", ""))
        and re.fullmatch(r"[0-9a-z_]{1,100}", ready.get("image_schema_revision", ""))
        and ready.get("image_schema_revision") == ready.get("receipt_schema_revision")
        and re.fullmatch(r"[0-9a-f]{64}", ready.get("policy_sha256", "")),
        "Rollback baseline needs database-backed readiness and its migration receipt",
    )


def submit(name: str, image: str, *, rollback: bool = False) -> str:
    deploy = {
        "preDeployCommand": [] if rollback or name == "frontend" else [MIGRATE],
        "startCommand": None,
        "healthcheckPath": "/api/v1/ready" if name == "backend" else "/healthz",
    }
    patch = {
        "services": {
            SERVICES[name]: {
                "source": {
                    "repo": None,
                    "branch": None,
                    "commitSha": None,
                    "image": image,
                    "autoUpdates": {"type": "disabled"},
                },
                "deploy": deploy,
            }
        }
    }
    result = legacy.railway(
        """mutation($env:String!,$patch:EnvironmentConfig!,$message:String!){
      environmentPatchCommit(environmentId:$env,patch:$patch,commitMessage:$message,skipDeploys:false)}""",
        {
            "env": ENVIRONMENT,
            "patch": patch,
            "message": f"Firstout CD {'recovery' if rollback else 'release'} {name}",
        },
    )
    return str(result["environmentPatchCommit"])


def observed(
    name: str,
    image: str,
    *,
    ready_commit: str | None = None,
    database: dict[str, str] | None = None,
    previous_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    require(
        name != "backend" or ready_commit or previous_readiness,
        "Backend observation needs a database receipt context",
    )
    state = legacy.provider_state(SERVICES[name])
    require(
        state["source"].get("image") == image and not state["source"].get("repo"),
        "Serving source mismatch",
    )
    require(
        not state["pending_patch"] and not state["deployment_triggers"],
        "Unexpected provider changes",
    )
    require(
        state["config"].get("source", {}).get("autoUpdates", {}).get("type")
        == "disabled",
        "Automatic image updates enabled",
    )
    require(
        state["config"].get("deploy", {}).get("healthcheckPath")
        == ("/api/v1/ready" if name == "backend" else "/healthz"),
        "Provider readiness healthcheck differs",
    )
    active = state["active_deployments"]
    require(
        len(active) == 1 and active[0]["status"] == "SUCCESS", "Rollout is not settled"
    )
    item = active[0]
    require(
        item["projectId"] == PROJECT
        and item["environmentId"] == ENVIRONMENT
        and item["serviceId"] == SERVICES[name]
        and item["image_digest"] == image.split("@")[1],
        "Wrong running image",
    )
    require(
        len(item["instances"]) == 1 and item["instances"][0]["status"] == "RUNNING",
        "Replica not running",
    )
    require(http_json(HEALTH[name]).get("status") == "ok", "Health failed")
    if ready_commit:
        ready = http_json(READY)
        require(database, "Missing migration identity")
        require(
            ready.get("status") == "ok"
            and ready.get("source_commit") == ready_commit
            and ready.get("migration_receipt") is True
            and ready.get("schema_revision") == database["schema_revision"]
            and ready.get("image_schema_revision") == database["schema_revision"]
            and ready.get("receipt_schema_revision") == database["schema_revision"]
            and ready.get("policy_sha256") == database["policy_sha256"],
            "Migration/readiness receipt mismatch",
        )
    if name == "backend" and previous_readiness:
        validate_previous_readiness(previous_readiness)
        ready = http_json(READY)
        validate_previous_readiness(ready)
        require(
            all(
                ready[key] == previous_readiness[key]
                for key in (
                    "source_commit",
                    "image_schema_revision",
                    "receipt_schema_revision",
                    "policy_sha256",
                )
            ),
            "Recovered backend receipt/source differs from captured baseline",
        )
        require(
            database
            and ready["schema_revision"]
            in (previous_readiness["schema_revision"], database["schema_revision"]),
            "Recovered backend has an unexpected database schema",
        )
    return {
        "deployment_id": item["id"],
        "digest": item["image_digest"],
        "instances": [inst["id"] for inst in item["instances"]],
    }


def wait_for(
    name: str,
    image: str,
    *,
    ready_commit: str | None = None,
    database: dict[str, str] | None = None,
    previous_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while True:
        try:
            return observed(
                name,
                image,
                ready_commit=ready_commit,
                database=database,
                previous_readiness=previous_readiness,
            )
        except (ReleaseError, urllib.error.URLError, OSError):
            if time.monotonic() >= deadline:
                raise ReleaseError("Deployment verification timed out") from None
            time.sleep(POLL_SECONDS)


def recover(journal: dict[str, Any], path: Path) -> None:
    validate_intent(journal)
    if journal.get("intent"):
        # Reconcile the exact uncertain mutation, including recovery submissions.
        # A settled previous image proves a recovery intent succeeded, but cannot
        # prove that an unacknowledged candidate submission never happened.
        intent = journal["intent"]
        latest = (
            legacy.provider_state(SERVICES[intent["service"]]).get("latest_deployment")
            or {}
        )
        require(
            latest.get("image") == intent["image"]
            and latest.get("status")
            in ("SUCCESS", "FAILED", "CRASHED", "SKIPPED", "REMOVED"),
            "Resolve the ambiguous provider operation before recovery",
        )
    checkpoint(journal, path, "rolling_back")
    for name in ("frontend", "backend"):
        if name not in journal["attempted"]:
            continue
        prior = journal["before"][name]
        readiness_args = {
            "previous_readiness": journal["before"]["backend"]["readiness"]
            if name == "backend"
            else None,
            "database": journal["manifest"]["database"],
        }
        # Reconcile a lost recovery response: a matching healthy source needs no mutation.
        try:
            restored = observed(name, prior["image"], **readiness_args)
        except (ReleaseError, urllib.error.URLError, OSError):
            current = legacy.provider_state(SERVICES[name])
            require(
                current["source"].get("image")
                in (prior["image"], journal["manifest"]["images"][name]["image"])
                and not current["source"].get("repo")
                and not current["pending_patch"]
                and not current["deployment_triggers"],
                "Provider changed outside this release; recovery paused",
            )
            journal["intent"] = {
                "phase": "recovery",
                "service": name,
                "image": prior["image"],
            }
            checkpoint(journal, path, f"restoring_{name}")
            try:
                submit(name, prior["image"], rollback=True)
            except (
                ReleaseError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                subprocess.TimeoutExpired,
            ):
                checkpoint(journal, path, "ambiguous")
                # Never resubmit after a lost response. Read until settled, otherwise pause.
                try:
                    restored = wait_for(name, prior["image"], **readiness_args)
                except (
                    ReleaseError,
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                    subprocess.TimeoutExpired,
                ):
                    raise AmbiguousRelease(
                        "Recovery submission outcome unknown"
                    ) from None
            else:
                restored = wait_for(name, prior["image"], **readiness_args)
        journal.setdefault("recovered", {})[name] = restored
        journal.pop("intent", None)
        checkpoint(journal, path, "rolling_back")
    checkpoint(journal, path, "rolled_back")


def deploy(manifest: dict[str, Any], path: Path) -> dict[str, Any]:
    validate_manifest(manifest)
    issues = release_issues()
    sha = manifest["source_commit"]
    existing = [issue for issue in issues if issue["title"] == PREFIX + sha]
    require(len(existing) <= 1, "Duplicate release journals")
    for issue in issues:
        require(
            issue["state"] != "open",
            "Firstout CD paused by an open release/incident journal",
        )
    if existing:
        journal = read_journal(existing[0])
        require(
            journal.get("state") == "succeeded",
            "Release already attempted; explicit recovery required",
        )
        require(
            journal.get("manifest") == manifest,
            "Same commit supplied with a different release manifest",
        )
        legacy.write_receipt(path, journal)
        return journal
    # A release must not go backwards relative to any recorded successful release.
    for issue in issues:
        if issue["title"] == PAUSE:
            continue
        previous = read_journal(issue)
        if previous.get("state") == "succeeded":
            require(
                github(f"compare/{previous['source_commit']}...{sha}").get("status")
                in ("ahead", "identical"),
                "Release is older than a successful production release",
            )
            break
    backup = backup_preflight()
    before = {
        name: safe_before(name, legacy.provider_state(service))
        for name, service in SERVICES.items()
    }
    require(
        manifest["previous_backend_image"] == before["backend"]["image"],
        "Tested previous binary differs from serving rollback baseline",
    )
    for name in SERVICES:
        require(
            http_json(HEALTH[name]).get("status") == "ok", "Previous app is unhealthy"
        )
    previous_ready = http_json(READY)
    validate_previous_readiness(previous_ready)
    before["backend"]["readiness"] = {
        key: previous_ready[key]
        for key in (
            "status",
            "source_commit",
            "schema_revision",
            "image_schema_revision",
            "receipt_schema_revision",
            "policy_sha256",
            "migration_receipt",
        )
    }
    require(
        github("git/ref/heads/main")["object"]["sha"] == sha,
        "Candidate was superseded before release; wait for current main",
    )
    journal = {
        "schema_version": 1,
        "source_commit": sha,
        "manifest": copy.deepcopy(manifest),
        "state": "preparing",
        "started_at": now(),
        "updated_at": now(),
        "before": before,
        "backup": backup,
        "attempted": [],
    }
    body = "```json\n" + json.dumps(journal, sort_keys=True, indent=2) + "\n```"
    issue = github("issues", "POST", {"title": PREFIX + sha, "body": body})
    journal["issue_number"] = issue["number"]
    checkpoint(journal, path, "preparing")
    try:
        for name in ("backend", "frontend"):
            require(
                all(
                    journal["before"][name].get(key) == value
                    for key, value in safe_before(
                        name, legacy.provider_state(SERVICES[name])
                    ).items()
                ),
                "Provider baseline changed before mutation",
            )
            journal["attempted"].append(name)
            journal["intent"] = {
                "phase": "release",
                "service": name,
                "image": manifest["images"][name]["image"],
            }
            checkpoint(journal, path, f"deploying_{name}")
            try:
                workflow = submit(name, manifest["images"][name]["image"])
                journal.setdefault("submissions", {})[name] = workflow
                checkpoint(journal, path, f"submitted_{name}")
            except (
                ReleaseError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                subprocess.TimeoutExpired,
            ):
                checkpoint(journal, path, "ambiguous")
            try:
                journal.setdefault("deployed", {})[name] = wait_for(
                    name,
                    manifest["images"][name]["image"],
                    ready_commit=sha if name == "backend" else None,
                    database=manifest["database"],
                )
            except (
                ReleaseError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                subprocess.TimeoutExpired,
            ):
                if journal["state"] == "ambiguous":
                    raise AmbiguousRelease(
                        "Provider submission outcome remains unknown"
                    ) from None
                latest = (
                    legacy.provider_state(SERVICES[name]).get("latest_deployment") or {}
                )
                if latest.get("image") != manifest["images"][name][
                    "image"
                ] or latest.get("status") not in (
                    "SUCCESS",
                    "FAILED",
                    "CRASHED",
                    "SKIPPED",
                    "REMOVED",
                ):
                    checkpoint(journal, path, "ambiguous")
                    raise AmbiguousRelease(
                        "Provider deployment did not settle"
                    ) from None
                raise
            journal.pop("intent", None)
            checkpoint(journal, path, f"{name}_ready")
        checkpoint(journal, path, "monitoring")
        for _ in range(MONITOR_SAMPLES):
            frontend_probe(manifest["frontend_assets"])
            for name in SERVICES:
                require(
                    observed(
                        name,
                        manifest["images"][name]["image"],
                        ready_commit=sha if name == "backend" else None,
                        database=manifest["database"],
                    )
                    == journal["deployed"][name],
                    "Serving set changed during monitoring",
                )
            time.sleep(POLL_SECONDS)
        checkpoint(journal, path, "succeeded")
        closed = github(
            f"issues/{journal['issue_number']}", "PATCH", {"state": "closed"}
        )
        require(closed["state"] == "closed", "Could not close successful journal")
        return journal
    except AmbiguousRelease:
        checkpoint(journal, path, "ambiguous")
        raise
    except (
        ReleaseError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.TimeoutExpired,
    ):
        try:
            recover(journal, path)
        except (
            ReleaseError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            subprocess.TimeoutExpired,
        ):
            checkpoint(journal, path, "recovery_failed")
        raise ReleaseError(
            "Release failed; durable journal pauses Firstout CD"
        ) from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    release = sub.add_parser("deploy")
    release.add_argument("--manifest", type=Path, required=True)
    release.add_argument("--state-file", type=Path, required=True)
    recovery = sub.add_parser("recover")
    recovery.add_argument("--issue-number", type=int, required=True)
    recovery.add_argument("--state-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "deploy":
            deploy(json.loads(args.manifest.read_text()), args.state_file)
        else:
            issue = github(f"issues/{args.issue_number}")
            require(issue["state"] == "open", "Recovery requires an open journal")
            journal = read_journal(issue)
            require(
                journal.get("issue_number") == args.issue_number,
                "Journal issue mismatch",
            )
            recover(journal, args.state_file)
        print("Firstout CD: completed; inspect durable journal")
        return 0
    except (ReleaseError, ValueError, KeyError, OSError, subprocess.TimeoutExpired):
        print(
            "Firstout CD: paused or blocked; inspect release journal (no provider details logged)",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
