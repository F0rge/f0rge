#!/usr/bin/env python3
"""Resolve deploy plan from manifest.yml + nx affected projects."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
    import yaml


def main() -> None:
    environment = os.environ["ENVIRONMENT"]
    component_mode = os.environ.get("COMPONENT", "auto")
    manifest_path = Path(__file__).with_name("manifest.yml")
    manifest = yaml.safe_load(manifest_path.read_text())

    if component_mode != "auto":
        # Manual dispatch: marrow-only component override (existing behaviour).
        deploy_api = component_mode in {"all", "api"}
        deploy_mcp = component_mode in {"all", "mcp"}
        deploy_frontend = component_mode in {"all", "frontend"}
        coolify = []
    else:
        nx_base = os.environ["NX_BASE"]
        nx_head = os.environ["NX_HEAD"]
        # workflow_run / detached checkouts sometimes set NX_BASE == NX_HEAD,
        # which makes `nx affected` empty and skips Railway smoke entirely.
        if nx_base == nx_head:
            print(
                f"NX_BASE == NX_HEAD ({nx_head[:12]}); "
                "treating all marrow railway components as affected"
            )
            affected = {
                spec["nx"]
                for spec in manifest["components"].values()
                if environment in spec.get("branches", [])
                and spec.get("target") in {"fly", "railway"}
                and spec["nx"].startswith("marrow-")
            }
        else:
            affected = set(
                json.loads(
                    subprocess.check_output(
                        [
                            "npx",
                            "nx",
                            "show",
                            "projects",
                            "--affected",
                            f"--base={nx_base}",
                            f"--head={nx_head}",
                            "--json",
                        ],
                        text=True,
                    )
                )
            )
        deploy_api = deploy_mcp = deploy_frontend = False
        coolify = []
        for _name, spec in manifest["components"].items():
            if environment not in spec.get("branches", []):
                continue
            if spec["nx"] not in affected:
                continue
            if spec["target"] in {"fly", "railway"}:
                # fly kept for legacy manifests; railway is the live target.
                block = spec.get(spec["target"]) or spec.get("railway") or spec.get("fly")
                role = block["role"]
                url = _health_url_for_env(block, environment)
                is_marrow = spec["nx"].startswith("marrow-")
                if role == "api":
                    if is_marrow:
                        deploy_api = True
                        deploy_mcp = True
                    elif url:
                        deploy_api = True
                    else:
                        print(
                            f"skip railway smoke for {spec['nx']}: "
                            f"empty health_url.{environment} "
                            "(Vellano is its own Railway project; "
                            "do not smoke Marrow develop)"
                        )
                elif role == "frontend":
                    if is_marrow or url:
                        deploy_frontend = True
                    else:
                        print(
                            f"skip railway smoke for {spec['nx']}: "
                            f"empty health_url.{environment} "
                            "(Vellano is its own Railway project; "
                            "do not smoke Marrow develop)"
                        )
            elif spec["target"] == "coolify":
                coolify.append(
                    {
                        "name": _name,
                        "app_uuid": spec["coolify"]["app_uuid"],
                        "webhook_secret_env": spec["coolify"]["webhook_secret_env"],
                        "health_url": spec["health_url"],
                    }
                )

    github_output = os.environ.get("GITHUB_OUTPUT")
    health = _health_urls(manifest, environment)
    outputs = {
        "deploy_api": str(deploy_api).lower(),
        "deploy_mcp": str(deploy_mcp).lower(),
        "deploy_frontend": str(deploy_frontend).lower(),
        "coolify_matrix": json.dumps(coolify),
        "api_health_url": health.get("api", ""),
        "frontend_health_url": health.get("frontend", ""),
        "mcp_health_url": health.get("mcp", ""),
    }
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            for key, value in outputs.items():
                fh.write(f"{key}={value}\n")
    else:
        print(json.dumps(outputs, indent=2))


def _health_url_for_env(block: dict[str, Any], environment: str) -> str:
    mapping = block.get("health_url") or {}
    if environment not in mapping:
        return ""
    value = mapping[environment]
    if value is None:
        return ""
    return str(value).strip()


def _health_urls(manifest: dict, environment: str) -> dict[str, str]:
    """Role -> health URL for this environment, from the manifest.

    Empty / missing per-env URLs are skipped so an unprovisioned sibling
    (Vellano S0) cannot overwrite Marrow smoke targets. Marrow wins on
    shared roles when both are present.
    """
    other_urls: dict[str, str] = {}
    marrow_urls: dict[str, str] = {}
    for spec in manifest["components"].values():
        target = spec.get("target")
        if target not in {"fly", "railway"}:
            continue
        primary = spec.get(target) or spec.get("railway") or spec.get("fly") or {}
        dest = marrow_urls if spec.get("nx", "").startswith("marrow-") else other_urls
        for block in [primary, *spec.get("also_deploys", [])]:
            if "role" not in block:
                continue
            url = _health_url_for_env(block, environment)
            if not url:
                continue
            dest[block["role"]] = url
    return {**other_urls, **marrow_urls}


if __name__ == "__main__":
    main()
