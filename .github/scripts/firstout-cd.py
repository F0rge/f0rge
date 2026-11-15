"""Trusted Firstout CD source gate and exact-image publication, never provider access."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github/deploy"))
from firstout_release import API, FRONTEND

IMAGE_REPOSITORIES = {"backend": API.image, "frontend": FRONTEND.image}
REPOSITORY = "F0rge/f0rge"
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def command(args: list[str]) -> str:
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=180, check=False
    )
    if result.returncode:
        # Provider/registry stderr can carry credentials. Never print it here.
        raise RuntimeError(f"{args[0]} failed; inspect the private command output")
    return result.stdout.strip()


def github(path: str) -> object:
    return json.loads(command(["gh", "api", f"repos/{REPOSITORY}/{path}"]))


def source() -> str:
    value = os.environ.get("SOURCE_COMMIT", "")
    if not SHA.fullmatch(value):
        raise RuntimeError("SOURCE_COMMIT must be an exact 40-character commit")
    return value


def last_release() -> dict | None:
    """Read durable release receipts, including changes missed by failed runs."""
    import firstout_cd as controller

    latest = None
    for issue in controller.release_issues():
        if issue.get("state") == "open":
            raise RuntimeError(
                "Firstout CD is paused by an open release/incident journal; recover and review it first"
            )
        if issue["title"] == controller.PAUSE:
            continue
        journal = controller.read_journal(issue)
        if journal.get("state") == "succeeded" and latest is None:
            latest = journal
    return latest


def gate() -> None:
    commit = source()
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    run = event["workflow_run"]
    if not (
        event.get("repository", {}).get("full_name") == REPOSITORY
        and run.get("head_repository", {}).get("full_name") == REPOSITORY
        and run.get("event") == "push"
        and run.get("head_branch") == "main"
        and run.get("conclusion") == "success"
        and run.get("head_sha") == commit
        and run.get("path") == ".github/workflows/ci.yml"
    ):
        raise RuntimeError("Untrusted CD trigger")
    current = github("git/ref/heads/main")["object"]["sha"]
    affected = False
    if current == commit:
        spec = importlib.util.spec_from_file_location(
            "firstout_release", ROOT / ".github/deploy/firstout_release.py"
        )
        release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(release)
        deadline = time.monotonic() + 1800
        while True:
            checks = github(f"commits/{commit}/check-runs?per_page=100")
            if checks.get("total_count", 0) > 100:
                raise RuntimeError("Unexpected source check pagination")
            pending = False
            for name in ("ci", "playwright smoke"):
                matches = [
                    c
                    for c in checks["check_runs"]
                    if c["name"] == name
                    and c.get("app", {}).get("slug") == "github-actions"
                ]
                latest = max(matches, key=lambda c: c["id"]) if matches else None
                if latest and latest.get("status") == "completed":
                    if latest.get("conclusion") != "success":
                        raise RuntimeError(f"Required source check failed: {name}")
                else:
                    pending = True
            if not pending:
                release.verified_source_checks(commit)
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Timed out waiting for required main checks")
            time.sleep(10)
        spec = importlib.util.spec_from_file_location(
            "firstout_cd", ROOT / ".github/deploy/firstout_cd.py"
        )
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        controller.verified_reviewed_source(commit)
        journal = last_release()
        baseline = journal["source_commit"] if journal else None
        previous = (
            journal["manifest"]["images"]["backend"]["image"]
            if journal
            else os.environ.get("BOOTSTRAP_BACKEND_IMAGE", "")
        )
        if not re.fullmatch(re.escape(API.image) + r"@sha256:[0-9a-f]{64}", previous):
            raise RuntimeError(
                "Configure the verified FIRSTOUT_BOOTSTRAP_BACKEND_IMAGE digest for the first release"
            )
        if baseline is None:
            affected = True  # Bootstrap is explicit; no successful receipt exists.
        elif baseline != commit:
            command(["git", "merge-base", "--is-ancestor", baseline, commit])
            projects = json.loads(
                command(
                    [
                        "npx",
                        "nx",
                        "show",
                        "projects",
                        "--affected",
                        "--json",
                        f"--base={baseline}",
                        f"--head={commit}",
                    ]
                )
            )
            affected = bool(
                set(projects)
                & {"firstout-backend", "firstout-frontend", "f0rge-release-checks"}
            )
            # Release machinery or app configuration can change without graph
            # ownership of every root instruction/workflow; include those inputs.
            changed = command(
                ["git", "diff", "--name-only", baseline, commit]
            ).splitlines()
            affected = affected or any(
                p.startswith(
                    (
                        ".github/deploy/",
                        ".github/workflows/cd-firstout.yml",
                        ".github/scripts/firstout-cd",
                    )
                )
                for p in changed
            )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(f"affected={str(affected).lower()}\nsource={commit}\n")
        if affected:
            output.write(f"previous_backend_image={previous}\n")
    print(
        "Firstout source checks verified"
        if affected
        else "No current Firstout release required"
    )


def publish() -> None:
    commit = source()
    if github("git/ref/heads/main")["object"]["sha"] != commit:
        raise RuntimeError("Source superseded on main; a newer run will release")
    spec = importlib.util.spec_from_file_location(
        "firstout_cd", ROOT / ".github/deploy/firstout_cd.py"
    )
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    controller.verified_reviewed_source(commit)
    images = {}
    for component in ("backend", "frontend"):
        local = f"firstout-{component}:cd-candidate"
        metadata = json.loads(command(["docker", "image", "inspect", local]))[0]
        if metadata["Os"] != "linux" or metadata["Architecture"] != "amd64":
            raise RuntimeError("Wrong image platform")
        if (
            metadata["Config"]["Labels"].get("org.opencontainers.image.revision")
            != commit
        ):
            raise RuntimeError("Candidate image source mismatch")
        repository = IMAGE_REPOSITORIES[component]
        candidate = f"{repository}:cd-{commit}-{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}"
        command(["docker", "tag", local, candidate])
        command(["docker", "push", candidate])
        refs = json.loads(command(["docker", "image", "inspect", candidate]))[0][
            "RepoDigests"
        ]
        references = [r for r in refs if r.startswith(repository + "@")]
        if len(references) != 1 or not DIGEST.fullmatch(references[0].split("@", 1)[1]):
            raise RuntimeError("Need one immutable published image digest")
        pinned = references[0]
        command(["docker", "pull", "--platform", "linux/amd64", pinned])
        pulled = json.loads(command(["docker", "image", "inspect", pinned]))[0]
        if pulled["Id"] != metadata["Id"]:
            raise RuntimeError("Published image differs from tested image")
        images[component] = {
            "image": pinned,
            "digest": pinned.split("@", 1)[1],
            "image_id": metadata["Id"],
            "source_commit": commit,
        }
    tag = f"release/firstout/railway/{commit}"
    # No moving tags on retries. A pre-existing tag must select this exact source.
    tags = github("git/matching-refs/tags/" + tag)
    if tags:
        if (
            len(tags) != 1
            or tags[0]["ref"] != "refs/tags/" + tag
            or tags[0]["object"]["sha"] != commit
        ):
            raise RuntimeError("Release tag already selects a different source")
    else:
        command(
            [
                "gh",
                "api",
                "--method",
                "POST",
                f"repos/{REPOSITORY}/git/refs",
                "-f",
                "ref=refs/tags/" + tag,
                "-f",
                "sha=" + commit,
            ]
        )
    manifest = {
        "schema_version": 2,
        "repository": REPOSITORY,
        "source_commit": commit,
        "release_tag": tag,
        "platform": "linux/amd64",
        "images": images,
        "workflow_run_id": int(os.environ["GITHUB_RUN_ID"]),
        "workflow_run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
        "workflow_commit": os.environ["GITHUB_SHA"],
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "checks": {
            key: True
            for key in (
                "unit",
                "lint",
                "typecheck",
                "container_smoke",
                "migration_compatibility",
                "backend_http",
            )
        },
        "previous_backend_image": os.environ["PREVIOUS_BACKEND_IMAGE"],
        "database": json.loads(
            command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "--network",
                    "none",
                    "--entrypoint",
                    ".venv/bin/python",
                    "firstout-backend:cd-candidate",
                    "-m",
                    "app.commands.release_migrate",
                    "--describe",
                ]
            )
        ),
        "frontend_assets": json.loads(
            command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "--network",
                    "none",
                    "--entrypoint",
                    "node",
                    "firstout-frontend:cd-candidate",
                    "-e",
                    (
                        "const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');"
                        "const root='/app/apps/firstout/frontend/.next/static';"
                        "function files(d){return fs.readdirSync(d,{withFileTypes:true}).flatMap(e=>e.isDirectory()?files(path.join(d,e.name)):[path.join(d,e.name)])}"
                        "const all=files(root).sort();"
                        "const result=['.js','.css'].map(ext=>{const p=all.find(f=>f.endsWith(ext));if(!p)throw Error('Missing built asset');return {path:'/_next/static/'+path.relative(root,p),sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')}});"
                        "console.log(JSON.stringify(result));"
                    ),
                ]
            )
        ),
    }
    Path("firstout-cd.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Published exact tested backend/frontend images and release manifest")


if __name__ == "__main__":
    try:
        {"gate": gate, "publish": publish}[sys.argv[1]]()
    except (
        RuntimeError,
        ValueError,
        KeyError,
        OSError,
        subprocess.SubprocessError,
    ) as error:
        print(f"Firstout CD stopped: {error}", file=sys.stderr)
        sys.exit(1)
