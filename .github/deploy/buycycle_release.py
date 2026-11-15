"""Verify/publish tested Buycycle images; a protected Pi agent applies approved releases.

Default planning is read-only. No source build, webhook or provider credential is
accepted from the requester. Production execution requires the separate managed
agent, verified GitHub approval and fresh, locally trusted migration receipts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import ssl
import stat
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

from firstout_release import ReleaseError, github, require, verified_source_checks

REPOSITORY = "F0rge/f0rge"
IMAGE = "ghcr.io/f0rge/buycycle"
WORKFLOW = ".github/workflows/release-buycycle.yml"
APP = "xi0qwpbyl2d8gf8u3xl13jkv"
OWNER = "leothesouthafrican"
OWNER_ID = 38779415
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
TAG = re.compile(r"release/buycycle/pi/[0-9]{8}T[0-9]{6}Z\Z")
TESTS = frozenset(
    {
        "production_frontend",
        "postgres_records",
        "verified_access",
        "origin_bypass_denied",
        "state_persistence",
        "revision_conflict",
        "backend_validation",
        "import_repeat_safe",
        "health_commit",
        "running_image_identity",
        "log_redaction",
    }
)
RECEIPTS = ("migration", "restore", "provider")


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def command(args: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        args, env=env, capture_output=True, timeout=600, check=False
    )
    require(result.returncode == 0, f"{args[0]} failed; inspect diagnostics privately")
    return result.stdout.decode()


def managed_docker_environment(
    image: str | None = None, *, environ: dict[str, str] | None = None
) -> dict[str, str]:
    """Only reviewed env-file configuration may supply Compose substitutions."""
    source = os.environ if environ is None else environ
    selected = {
        "PATH": source.get(
            "PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        ),
        "LANG": "C.UTF-8",
    }
    if source.get("DOCKER_CONFIG"):
        selected["DOCKER_CONFIG"] = source["DOCKER_CONFIG"]
    if image is not None:
        require(
            image.startswith(IMAGE + "@") and DIGEST.fullmatch(image.split("@")[-1]),
            "Managed image must be pinned",
        )
        selected["BUYCYCLE_IMAGE"] = image
    return selected


def agent_docker(args: list[str], *, env: dict[str, str] | None = None) -> str:
    """The privileged agent controls only its local daemon, never a client context."""
    selected = managed_docker_environment(
        env.get("BUYCYCLE_IMAGE") if env is not None else None, environ=env
    )
    selected["DOCKER_HOST"] = "unix:///run/docker.sock"
    return command(["docker", "--host", "unix:///run/docker.sock", *args], env=selected)


def age(value: str, now: dt.datetime | None = None) -> float:
    try:
        instant = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(instant.tzinfo is not None, "Timestamp has no timezone")
        return ((now or dt.datetime.now(dt.UTC)) - instant).total_seconds()
    except (ValueError, TypeError, AttributeError) as exc:
        raise ReleaseError("Invalid timestamp") from exc


def validate_image_evidence(evidence: dict[str, Any], commit: str) -> None:
    require(SHA.fullmatch(commit), "Invalid commit")
    require(
        evidence.get("version") == 1 and evidence.get("repository") == REPOSITORY,
        "Wrong image evidence schema/repository",
    )
    require(evidence.get("commit") == commit, "Wrong tested commit")
    require(evidence.get("platform") == "linux/arm64", "Wrong tested platform")
    require(
        evidence.get("dirty") is False and evidence.get("tested") is True,
        "Dirty or untested image",
    )
    require(DIGEST.fullmatch(str(evidence.get("image_id", ""))), "Invalid image ID")
    require(
        DIGEST.fullmatch(str(evidence.get("config_digest", ""))),
        "Invalid canonical image config digest",
    )
    require(
        HASH.fullmatch(str(evidence.get("archive_sha256", ""))), "Invalid archive hash"
    )
    tests = evidence.get("tests", {})
    require(
        isinstance(tests, dict)
        and TESTS <= tests.keys()
        and all(value is True for value in tests.values()),
        "Missing/failed image tests",
    )
    require(
        0 <= age(evidence.get("created_at", "")) <= 7 * 86400,
        "Image test evidence is stale or future-dated",
    )


def validate_ci_run(run: dict[str, Any], commit: str) -> None:
    require(
        run.get("repository", {}).get("full_name") == REPOSITORY
        and run.get("path") == ".github/workflows/ci.yml"
        and run.get("head_sha") == commit
        and run.get("head_branch") == "main"
        and run.get("event") == "push"
        and run.get("status") == "completed"
        and run.get("conclusion") == "success",
        "Not a successful main-push CI run",
    )


def verified_tag(tag: str, commit: str) -> None:
    require(TAG.fullmatch(tag), "Wrong Buycycle/Pi release tag")
    rulesets = github("rulesets?includes_parents=true&per_page=100")
    require(
        isinstance(rulesets, list) and len(rulesets) < 100,
        "Unexpected tag ruleset pagination",
    )
    protected = False
    for item in rulesets:
        if item.get("target") != "tag" or item.get("enforcement") != "active":
            continue
        rule = github(f"rulesets/{item['id']}")
        condition = rule.get("conditions", {}).get("ref_name", {})
        # Deliberately support only these unambiguous patterns; fnmatch `*`
        # differs between Python and GitHub when a ref contains slashes.
        includes = condition.get("include", [])
        applies = any(
            value in includes
            for value in ("~ALL", "refs/tags/" + tag, "refs/tags/release/buycycle/pi/*")
        )
        types = {entry.get("type") for entry in rule.get("rules", [])}
        if applies and not condition.get("exclude") and not rule.get("bypass_actors"):
            protected = {"update", "deletion"} <= types
            if protected:
                break
    require(protected, "Release tag update/deletion protection is not verified")
    ref = github("git/ref/tags/" + tag)["object"]
    if ref["type"] == "tag":
        ref = github("git/tags/" + ref["sha"])["object"]
    require(
        ref.get("type") == "commit" and ref.get("sha") == commit, "Release tag moved"
    )
    require(
        github(f"compare/{commit}...main").get("status") in ("ahead", "identical"),
        "Commit is not on main",
    )


def download_artifact(
    run_id: int, name: str, output: Path, entries: set[str]
) -> dict[str, Any]:
    listing = github(f"actions/runs/{run_id}/artifacts?per_page=100")
    require(listing.get("total_count", 0) <= 100, "Unexpected artifact pagination")
    found = [
        item
        for item in listing.get("artifacts", [])
        if item.get("name") == name and not item.get("expired")
    ]
    require(len(found) == 1, "Need one unexpired artifact")
    item = found[0]
    require(0 < item.get("size_in_bytes", 0) < 5_000_000_000, "Artifact size rejected")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="buycycle-artifact-") as temp:
        archive = Path(temp) / "artifact.zip"
        with archive.open("wb") as stream:
            result = subprocess.run(
                ["gh", "api", f"repos/{REPOSITORY}/actions/artifacts/{item['id']}/zip"],
                stdout=stream,
                stderr=subprocess.PIPE,
                timeout=600,
                check=False,
            )
        require(result.returncode == 0, "GitHub artifact download failed")
        digest = "sha256:" + file_sha256(archive)
        require(digest == item.get("digest"), "GitHub artifact digest mismatch")
        with zipfile.ZipFile(archive) as zipped:
            require(
                set(zipped.namelist()) == entries
                and len(zipped.namelist()) == len(entries),
                "Unexpected artifact files",
            )
            for member in zipped.infolist():
                require(
                    member.file_size < 5_000_000_000
                    and not stat.S_ISLNK(member.external_attr >> 16),
                    "Unsafe artifact entry",
                )
                with (
                    zipped.open(member) as source,
                    (output / member.filename).open("xb") as target,
                ):
                    shutil.copyfileobj(source, target)
                (output / member.filename).chmod(0o600)
    return {"id": item["id"], "digest": digest}


def archive_config(archive: Path, commit: str) -> tuple[str, str]:
    """Read the actual config bytes, never infer their digest from Docker's Id."""
    with tarfile.open(archive) as saved:

        def metadata(name: str) -> bytes:
            member = saved.getmember(name)
            require(
                member.isfile() and member.size <= 5_000_000, "Unsafe archive metadata"
            )
            stream = saved.extractfile(member)
            require(stream is not None, "Missing archive metadata")
            return stream.read()

        rows = json.loads(metadata("manifest.json"))
        require(isinstance(rows, list) and len(rows) == 1, "Need one archived image")
        entry = rows[0]
        config_name = entry.get("Config", "")
        require(
            re.fullmatch(r"(?:blobs/sha256/)?[0-9a-f]{64}(?:\.json)?", config_name),
            "Unsafe archived config path",
        )
        content = metadata(config_name)
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        require(
            Path(config_name).name.removesuffix(".json")
            == digest.removeprefix("sha256:"),
            "Archived config blob checksum mismatch",
        )
        config = json.loads(content)
        require(
            config.get("architecture") == "arm64"
            and config.get("os") == "linux"
            and config.get("config", {})
            .get("Labels", {})
            .get("org.opencontainers.image.revision")
            == commit,
            "Archived image config source/platform mismatch",
        )
        tags = entry.get("RepoTags")
        require(
            isinstance(tags, list) and len(tags) == 1 and isinstance(tags[0], str),
            "Need one archived image tag",
        )
        require(
            re.fullmatch(r"[a-z0-9][a-z0-9._/:-]{0,250}", tags[0]),
            "Invalid archived image tag",
        )
        return digest, tags[0]


def registry_config_digest(image: str, docker=None) -> str:
    """Resolve exactly one Linux ARM64 registry manifest, excluding attestations."""
    require(
        image.startswith(IMAGE + "@") and DIGEST.fullmatch(image.split("@")[-1]),
        "Registry image must be pinned",
    )
    selected = docker or (lambda args: command(["docker", *args]))
    manifest = json.loads(selected(["manifest", "inspect", image]))
    if "manifests" in manifest:
        matches = [
            item
            for item in manifest["manifests"]
            if item.get("platform", {}).get("os") == "linux"
            and item.get("platform", {}).get("architecture") == "arm64"
            and item.get("platform", {}).get("variant", "v8") in ("", "v8")
        ]
        require(len(matches) == 1, "Need one registry Linux ARM64 image")
        child = matches[0].get("digest", "")
        require(DIGEST.fullmatch(child), "Invalid platform manifest digest")
        manifest = json.loads(selected(["manifest", "inspect", IMAGE + "@" + child]))
    digest = manifest.get("config", {}).get("digest", "")
    require(DIGEST.fullmatch(digest), "Missing registry image config digest")
    return digest


def prepare(run_id: int, commit: str, tag: str, output: Path) -> dict[str, Any]:
    require(type(run_id) is int and run_id > 0, "Invalid CI run ID")
    run = github(f"actions/runs/{run_id}")
    validate_ci_run(run, commit)
    verified_tag(tag, commit)
    checks = verified_source_checks(commit)
    name = f"ci-buycycle-push-{run_id}-{run['run_attempt']}"
    artifact = download_artifact(run_id, name, output, {"image.tar", "evidence.json"})
    evidence = json.loads((output / "evidence.json").read_text())
    validate_image_evidence(evidence, commit)
    archive_hash = file_sha256(output / "image.tar")
    require(
        archive_hash == evidence["archive_sha256"], "Image archive checksum mismatch"
    )
    config_digest, archived_tag = archive_config(output / "image.tar", commit)
    require(
        config_digest == evidence["config_digest"]
        and archived_tag == evidence.get("image_tag"),
        "Archived image config/tag mismatch",
    )
    command(["docker", "load", "--input", str(output / "image.tar")])
    info = json.loads(command(["docker", "image", "inspect", archived_tag]))[0]
    require(
        DIGEST.fullmatch(str(info.get("Id", "")))
        and info.get("Architecture") == "arm64"
        and info.get("Os") == "linux"
        and info.get("Config", {})
        .get("Labels", {})
        .get("org.opencontainers.image.revision")
        == commit,
        "Loaded image identity mismatch",
    )
    candidate = {
        "source_ci_run": run_id,
        "source_ci_attempt": run["run_attempt"],
        "source_artifact": artifact,
        "source_checks": checks,
        "image_evidence": evidence,
        "release_tag": tag,
        "loaded_image_id": info["Id"],
    }
    (output / "candidate.json").write_text(json.dumps(candidate, indent=2) + "\n")
    return candidate


def validate_publication(manifest: dict[str, Any], run: dict[str, Any]) -> None:
    require(
        manifest.get("version") == 1 and manifest.get("repository") == REPOSITORY,
        "Wrong publication schema/repository",
    )
    require(
        SHA.fullmatch(str(manifest.get("commit", ""))), "Invalid publication commit"
    )
    require(
        TAG.fullmatch(str(manifest.get("release_tag", ""))),
        "Wrong publication release tag",
    )
    require(
        manifest.get("image") == IMAGE + "@" + manifest.get("digest", "")
        and DIGEST.fullmatch(str(manifest.get("digest", ""))),
        "Unpinned publication image",
    )
    require(
        manifest.get("target") == {"host": "pi", "app": APP}, "Wrong release target"
    )
    validate_image_evidence(manifest.get("image_evidence", {}), manifest["commit"])
    require(
        run.get("repository", {}).get("full_name") == REPOSITORY
        and run.get("path") == WORKFLOW
        and run.get("event") == "workflow_dispatch"
        and run.get("head_branch") == "main"
        and run.get("status") == "completed"
        and run.get("conclusion") == "success",
        "Invalid publication workflow",
    )
    require(
        manifest.get("workflow_run_id") == run.get("id")
        and manifest.get("workflow_commit") == run.get("head_sha")
        and manifest.get("workflow_attempt") == run.get("run_attempt") == 1,
        "Publication run/attempt mismatch; start a new run instead of rerunning",
    )


def verify_approval(run: dict[str, Any], policy: dict[str, Any]) -> None:
    require(
        0 <= age(run.get("created_at", "")) <= policy.get("max_age_seconds", 3600),
        "Release authorization expired or future-dated",
    )
    actor, triggering = run.get("actor", {}), run.get("triggering_actor", {})
    require(
        re.fullmatch(r"[a-z0-9-]{1,100}", policy["requester_app_slug"]),
        "Invalid requester slug",
    )
    app = json.loads(command(["gh", "api", "apps/" + policy["requester_app_slug"]]))
    require(app.get("id") == policy["requester_app_id"], "Unverified automation app")
    permissions = app.get("permissions", {})
    allowed = {"actions": "write", "metadata": "read", "contents": "read"}
    require(
        permissions.get("actions") == "write"
        and all(allowed.get(name) == access for name, access in permissions.items()),
        "Requester app permissions exceed the reviewed release-request scope",
    )
    require(
        actor.get("type") == "Bot"
        and actor.get("login") == app.get("slug") + "[bot]"
        and triggering.get("id") == actor.get("id")
        and actor.get("login") != OWNER,
        "Independent automation requester is required",
    )
    environment = github("environments/production")
    rules = [
        rule
        for rule in environment.get("protection_rules", [])
        if rule.get("type") == "required_reviewers"
    ]
    require(
        len(rules) == 1
        and rules[0].get("prevent_self_review") is True
        and environment.get("can_admins_bypass") is False,
        "Production approval protections are not verified",
    )
    reviewers = rules[0].get("reviewers", [])
    require(
        len(reviewers) == 1
        and reviewers[0].get("type") == "User"
        and reviewers[0].get("reviewer", {}).get("login") == OWNER,
        "Leo must be the sole release reviewer",
    )
    require(
        reviewers[0].get("reviewer", {}).get("id") == OWNER_ID,
        "Release reviewer identity changed",
    )
    branches = github("environments/production/deployment-branch-policies").get(
        "branch_policies", []
    )
    require(
        len(branches) == 1
        and branches[0].get("name") == "main"
        and branches[0].get("type") == "branch",
        "Unexpected production branch policy",
    )
    approvals = github(f"actions/runs/{run['id']}/approvals")
    require(
        any(
            review.get("state") == "approved"
            and review.get("user", {}).get("login") == OWNER
            and review.get("user", {}).get("id") == OWNER_ID
            and any(
                env.get("id") == environment["id"]
                for env in review.get("environments", [])
            )
            for review in approvals
        ),
        "Independent Leo approval not found",
    )


def verified_release(run_id: int, policy: dict[str, Any]) -> dict[str, Any]:
    run = github(f"actions/runs/{run_id}")
    with tempfile.TemporaryDirectory(prefix="buycycle-release-") as temp:
        directory = Path(temp)
        download_artifact(
            run_id, "buycycle-release-publication", directory, {"buycycle-release.json"}
        )
        manifest = json.loads((directory / "buycycle-release.json").read_text())
    validate_publication(manifest, run)
    ci_id = manifest.get("source_ci_run")
    require(type(ci_id) is int and ci_id > 0, "Missing source CI identity")
    ci_run = github(f"actions/runs/{ci_id}")
    validate_ci_run(ci_run, manifest["commit"])
    require(
        ci_run.get("run_attempt") == manifest.get("source_ci_attempt"),
        "Stale source CI attempt",
    )
    artifacts = github(f"actions/runs/{ci_id}/artifacts?per_page=100")
    require(artifacts.get("total_count", 0) <= 100, "Unexpected CI artifact pagination")
    found = [
        item
        for item in artifacts.get("artifacts", [])
        if item.get("name") == f"ci-buycycle-push-{ci_id}-{ci_run['run_attempt']}"
        and not item.get("expired")
    ]
    require(
        len(found) == 1
        and manifest.get("source_artifact")
        == {"id": found[0]["id"], "digest": found[0].get("digest")},
        "Source CI artifact identity changed",
    )
    verified_tag(manifest["release_tag"], manifest["commit"])
    verified_source_checks(manifest["commit"])
    verify_approval(run, policy)
    with tempfile.TemporaryDirectory(prefix="buycycle-approval-") as temp:
        directory = Path(temp)
        download_artifact(
            run_id, "buycycle-release-approval", directory, {"approval.json"}
        )
        approval = json.loads((directory / "approval.json").read_text())
    require(
        approval
        == {
            "version": 1,
            "run_id": run_id,
            "run_attempt": 1,
            "publication_sha256": hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        },
        "Protected approval did not bind the exact publication",
    )
    return manifest


def trusted_file(path: str) -> Path:
    result = Path(path)
    require(
        result.is_absolute() and not result.is_symlink(), "Managed file path rejected"
    )
    current = result
    while current != current.parent:
        info = current.lstat()
        require(
            not stat.S_ISLNK(info.st_mode)
            and info.st_uid == 0
            and not info.st_mode & 0o022,
            "Managed path must be root-owned and not writable by others",
        )
        current = current.parent
    return result


def verify_receipts(manifest: dict[str, Any], policy: dict[str, Any]) -> None:
    for kind in RECEIPTS:
        path = trusted_file(policy[kind + "_receipt"])
        content = path.read_bytes()
        require(
            hashlib.sha256(content).hexdigest()
            == manifest.get("receipt_hashes", {}).get(kind),
            f"{kind} receipt differs from approved release",
        )
        receipt = json.loads(content)
        require(
            receipt.get("passed") is True
            and receipt.get("commit") == manifest["commit"]
            and receipt.get("target") == {"host": "pi", "app": APP}
            and 0
            <= age(receipt.get("created_at", ""))
            <= policy.get("max_age_seconds", 3600),
            f"{kind} receipt is stale or invalid",
        )
        if kind == "provider":
            require(
                all(
                    receipt.get(key) is True
                    for key in (
                        "legacy_collector_fenced",
                        "source_builds_disabled",
                        "origin_unpublished",
                        "access_policy_verified",
                        "database_grants_verified",
                        "managed_secrets_verified",
                    )
                ),
                "Provider safety preconditions incomplete",
            )
            require(
                receipt.get("docker_engine_id")
                == policy.get("expected_docker_engine_id")
                and receipt.get("compose_sha256") == policy.get("compose_sha256")
                and receipt.get("managed_env_sha256")
                == policy.get("managed_env_sha256"),
                "Provider target/configuration differs from approved preflight",
            )


def write_journal(path: Path, value: dict[str, Any], exclusive: bool = False) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_NOFOLLOW
        | (os.O_EXCL if exclusive else os.O_TRUNC)
    )
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def active_receipt_path(policy: dict[str, Any], journal_dir: Path) -> Path:
    path = Path(policy.get("active_release_receipt", str(journal_dir / "active.json")))
    require(
        path.parent == journal_dir
        and path.name == "active.json"
        and not path.is_symlink(),
        "Active receipt must be the protected journal directory's active.json",
    )
    if path.exists():
        require(
            trusted_file(str(path)).is_file(),
            "Active receipt must be a regular managed file",
        )
    return path


def publish_active_receipt(path: Path, receipt: dict[str, Any]) -> None:
    """Publish one complete verified record; collectors never see partial JSON."""
    pending = path.parent / (".active-" + uuid.uuid4().hex + ".tmp")
    try:
        write_journal(pending, receipt, exclusive=True)
        os.replace(pending, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        pending.unlink(missing_ok=True)


def _apply_locked(
    run_id: int, request_id: str, policy: dict[str, Any]
) -> dict[str, Any]:
    require(type(run_id) is int and run_id > 0, "Invalid release run ID")
    require(str(uuid.UUID(request_id)) == request_id, "Invalid request ID")
    require(
        policy.get("app") == APP and policy.get("project_name") == "buycycle",
        "Wrong Pi agent scope",
    )
    manifest = verified_release(run_id, policy)
    verify_receipts(manifest, policy)
    compose, envfile = (
        trusted_file(policy["compose_path"]),
        trusted_file(policy["managed_env_file"]),
    )
    journal_dir = trusted_file(policy["journal_dir"])
    require(journal_dir.is_dir(), "Journal directory missing")
    active_receipt = active_receipt_path(policy, journal_dir)
    require(
        hashlib.sha256(compose.read_bytes()).hexdigest() == policy["compose_sha256"],
        "Managed Compose changed",
    )
    require(
        file_sha256(envfile) == policy["managed_env_sha256"],
        "Managed runtime configuration changed",
    )
    require(
        not envfile.stat().st_mode & 0o077,
        "Managed runtime secrets must be readable only by their owner",
    )
    engine_id = agent_docker(
        ["info", "--format", "{{.ID}}"], env=managed_docker_environment()
    ).strip()
    require(
        bool(engine_id) and engine_id == policy.get("expected_docker_engine_id"),
        "Wrong Pi Docker engine; no deployment performed",
    )
    journal = journal_dir / f"{run_id}-1.json"
    receipt = {
        "version": 1,
        "request_id": request_id,
        "release_run_id": run_id,
        "image": manifest["image"],
        "commit": manifest["commit"],
        "target": manifest["target"],
        "state": "submission_started",
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "docker_engine_id": engine_id,
        "compose_sha256": policy["compose_sha256"],
        "managed_env_sha256": policy["managed_env_sha256"],
    }
    write_journal(journal, receipt, exclusive=True)
    command_base = [
        "compose",
        "--project-name",
        "buycycle",
        "--env-file",
        str(envfile),
        "--file",
        str(compose),
    ]
    env = managed_docker_environment(manifest["image"])
    try:
        agent_docker(command_base + ["pull", "app"], env=env)
        image = json.loads(
            agent_docker(["image", "inspect", manifest["image"]], env=env)
        )[0]
        require(
            DIGEST.fullmatch(str(image.get("Id", "")))
            and image.get("Architecture") == "arm64"
            and image.get("Os") == "linux"
            and manifest["image"] in image.get("RepoDigests", [])
            and image.get("Config", {})
            .get("Labels", {})
            .get("org.opencontainers.image.revision")
            == manifest["commit"],
            "Pulled image differs from tested artifact",
        )
        require(
            registry_config_digest(
                manifest["image"], lambda args: agent_docker(args, env=env)
            )
            == manifest["image_evidence"]["config_digest"],
            "Registry config differs from tested artifact",
        )
        agent_docker(
            command_base
            + ["up", "--detach", "--no-build", "--pull", "never", "--wait", "app"],
            env=env,
        )
        container = agent_docker(
            command_base + ["ps", "--quiet", "app"], env=env
        ).strip()
        require(
            re.fullmatch(r"[0-9a-f]{12,64}", container),
            "Need exactly one app container",
        )
        running = json.loads(agent_docker(["inspect", container], env=env))[0]
        require(
            running.get("Image") == image["Id"]
            and running.get("State", {}).get("Running") is True
            and running.get("State", {}).get("Health", {}).get("Status") == "healthy"
            and not running.get("HostConfig", {}).get("PortBindings")
            and running.get("Config", {})
            .get("Labels", {})
            .get("org.opencontainers.image.revision")
            == manifest["commit"],
            "Serving container identity, health or private boundary mismatch",
        )
        receipt.update(
            state="verified",
            receipt_hashes=dict(manifest["receipt_hashes"]),
            image_id=image["Id"],
            container_id=container,
            digest=manifest["digest"],
            config_digest=manifest["image_evidence"]["config_digest"],
        )
        write_journal(journal, receipt)
        publish_active_receipt(active_receipt, receipt)
    except Exception:
        receipt["state"] = "submission_outcome_unknown"
        write_journal(journal, receipt)
        raise
    return receipt


def agent_apply(run_id: int, request_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    """Managed-agent seam; requester supplies no path, image, command or secret."""
    directory = trusted_file(policy["journal_dir"])
    fd = os.open(
        directory / "deployment.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ReleaseError("Another Buycycle deployment is in progress") from exc
        return _apply_locked(run_id, request_id, policy)
    finally:
        os.close(fd)


def promote(run_id: int, policy: dict[str, Any]) -> dict[str, Any]:
    """Send a verified release reference to the fixed mutually authenticated agent."""
    manifest = verified_release(run_id, policy)
    endpoint = urllib.parse.urlsplit(policy["agent_url"])
    require(
        endpoint.scheme == "https"
        and endpoint.hostname
        and not endpoint.username
        and not endpoint.password
        and endpoint.path == "/v1/releases"
        and not endpoint.query
        and not endpoint.fragment,
        "Invalid fixed Pi agent endpoint",
    )
    cert, key, ca = (
        trusted_file(policy[name]) for name in ("client_cert", "client_key", "agent_ca")
    )
    require(not key.stat().st_mode & 0o077, "Client private key permissions rejected")
    context = ssl.create_default_context(cafile=str(ca))
    context.load_cert_chain(str(cert), str(key))
    request_id = str(uuid.uuid4())
    request = urllib.request.Request(
        policy["agent_url"],
        method="POST",
        data=json.dumps({"release_run_id": run_id, "request_id": request_id}).encode(),
        headers={"Content-Type": "application/json"},
    )

    # No redirects: the authenticated endpoint must remain the configured agent.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context), NoRedirect()
    )
    with opener.open(request, timeout=600) as response:
        require(response.status == 200, "Pi agent did not verify the deployment")
        value = json.loads(response.read(100_001))
    require(
        value.get("state") == "verified"
        and value.get("request_id") == request_id
        and value.get("release_run_id") == run_id
        and value.get("commit") == manifest["commit"]
        and value.get("target") == manifest["target"]
        and value.get("image") == manifest["image"]
        and DIGEST.fullmatch(str(value.get("image_id", "")))
        and value.get("config_digest") == manifest["image_evidence"]["config_digest"]
        and value.get("digest") == manifest["digest"]
        and value.get("docker_engine_id") == policy.get("expected_docker_engine_id"),
        "Pi running-image receipt mismatch",
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--ci-run-id", type=int, required=True)
    prepare_parser.add_argument("--commit", required=True)
    prepare_parser.add_argument("--tag", required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    registry_parser = sub.add_parser("verify-registry")
    registry_parser.add_argument("--image", required=True)
    registry_parser.add_argument("--config-digest", required=True)
    apply_parser = sub.add_parser("agent-apply")
    apply_parser.add_argument("--release-run-id", type=int, required=True)
    apply_parser.add_argument("--request-id", required=True)
    apply_parser.add_argument("--policy", required=True)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--release-run-id", type=int, required=True)
    plan_parser.add_argument("--policy", required=True)
    promote_parser = sub.add_parser("promote")
    promote_parser.add_argument("--release-run-id", type=int, required=True)
    promote_parser.add_argument("--policy", required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.ci_run_id, args.commit, args.tag, args.output)
        elif args.command == "verify-registry":
            digest = registry_config_digest(args.image)
            require(
                digest == args.config_digest,
                "Registry config differs from tested artifact",
            )
            result = {"config_digest": digest, "image": args.image}
        else:
            policy = json.loads(trusted_file(args.policy).read_text())
            if args.command == "agent-apply":
                result = agent_apply(args.release_run_id, args.request_id, policy)
            elif args.command == "promote":
                result = promote(args.release_run_id, policy)
            else:
                result = verified_release(args.release_run_id, policy)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (
        ReleaseError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        zipfile.BadZipFile,
        tarfile.TarError,
        subprocess.SubprocessError,
    ):
        # Provider errors and command stderr can contain credentials or PII.
        print(
            "Buycycle release refused or outcome unknown; inspect the private journal and prerequisites."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
