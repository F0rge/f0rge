"""Launch Node checkout QA with explicit local configuration and no inherited credentials."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-json", type=Path, required=True)
    parser.add_argument("--app", choices=["commerce", "web"], required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide a Node command after --")
    if Path(command[0]).name != "node":
        parser.error(
            "launch node directly so the loopback network preload always applies"
        )
    storefront = Path(__file__).resolve().parents[2]
    for app in ("commerce", "web"):
        unexpected = [
            p.name for p in (storefront / app).glob(".env*") if p.name != ".env.example"
        ]
        if unexpected:
            parser.error(f"refusing app environment files in {app}: {unexpected}")
    env_file = args.env_json.resolve()
    settings = json.loads(env_file.read_text())
    if not isinstance(settings, dict) or any(
        not isinstance(value, str) for value in settings.values()
    ):
        parser.error("environment JSON must map names to strings")
    external = (
        "PEACH_",
        "CLERK_",
        "NEXT_PUBLIC_CLERK_",
        "STOREFRONT_CLERK_",
        "STOREFRONT_SENDGRID_",
        "NEXT_PUBLIC_POSTHOG_",
    )
    if any(value for name, value in settings.items() if name.startswith(external)):
        parser.error(
            "external payment, email, identity and analytics configuration must be empty"
        )
    if settings.get("STOREFRONT_LOCAL_CHECKOUT_QA") != "true":
        parser.error("requires explicit STOREFRONT_LOCAL_CHECKOUT_QA=true")
    # Only OS process necessities survive; proxy variables and provider secrets do not.
    launch = {
        key: os.environ[key]
        for key in ("PATH", "TMPDIR", "LANG", "LC_ALL")
        if key in os.environ
    }
    launch.update(settings)
    local_home = env_file.parent / "home"
    local_home.mkdir(mode=0o700, exist_ok=True)
    launch.update(
        HOME=str(local_home),
        XDG_CONFIG_HOME=str(env_file.parent / "config"),
        NODE_OPTIONS="--require="
        + json.dumps(
            str(Path(__file__).with_name("local-checkout-loopback.cjs").resolve())
        ),
        MEDUSA_DISABLE_TELEMETRY="true",
        NEXT_TELEMETRY_DISABLED="1",
    )
    os.chdir(storefront / args.app)
    os.execvpe(command[0], command, launch)


if __name__ == "__main__":
    main()
