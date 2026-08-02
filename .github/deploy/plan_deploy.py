#!/usr/bin/env python3
"""Resolve deploy plan from manifest.yml + nx affected projects."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

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
        affected = set(
            json.loads(
                subprocess.check_output(
                    [
                        "npx",
                        "nx",
                        "show",
                        "projects",
                        "--affected",
                        f"--base={os.environ['NX_BASE']}",
                        f"--head={os.environ['NX_HEAD']}",
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
                # fly kept for legacy manifests; railway is the live marrow target.
                block = spec.get(spec["target"]) or spec.get("railway") or spec.get("fly")
                role = block["role"]
                if role == "api":
                    deploy_api = True
                    deploy_mcp = True
                elif role == "frontend":
                    deploy_frontend = True
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
        "api_health_url": health["api"],
        "frontend_health_url": health["frontend"],
        "mcp_health_url": health["mcp"],
    }
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            for key, value in outputs.items():
                fh.write(f"{key}={value}\n")
    else:
        print(json.dumps(outputs, indent=2))


def _health_urls(manifest: dict, environment: str) -> dict[str, str]:
    """Role -> health URL for this environment, from the manifest."""
    urls: dict[str, str] = {}
    for spec in manifest["components"].values():
        target = spec.get("target")
        if target not in {"fly", "railway"}:
            continue
        primary = spec.get(target) or spec.get("railway") or spec.get("fly") or {}
        for block in [primary, *spec.get("also_deploys", [])]:
            if "health_url" in block and "role" in block:
                urls[block["role"]] = block["health_url"][environment]
    return urls


if __name__ == "__main__":
    main()
