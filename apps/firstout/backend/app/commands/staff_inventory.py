"""Local-only staff access snapshots. Never emit password hashes or credentials.

Run ``python -m app.commands.staff_inventory snapshot output.json`` before/after
migration on a disposable restored database; compare with ``compare before after``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from sqlalchemy import text
from app.database import async_session_maker
from f0rge_db.organisation import organisation_session
from app.permissions import PERMISSION_CATALOG


async def inventory() -> list[dict]:
    records = []
    async with organisation_session(async_session_maker) as db:
        users = (
            (
                await db.execute(
                    text(
                        "SELECT u.id, u.email, u.display_name, u.role, u.is_disabled, u.token_version, u.default_location_id, u.team_id, t.name AS team_name FROM users u JOIN teams t ON t.id=u.team_id ORDER BY u.id"
                    )
                )
            )
            .mappings()
            .all()
        )
        has_memberships = await db.scalar(
            text("SELECT to_regclass('public.memberships') IS NOT NULL")
        )
        if has_memberships:
            homes = set(
                (
                    await db.execute(text("SELECT user_id FROM memberships WHERE is_legacy_home"))
                ).scalars()
            )
            if any(user["id"] not in homes for user in users):
                raise RuntimeError("Staff inventory has missing legacy home memberships")
    for user in users:
        async with organisation_session(async_session_maker, user["team_id"]) as db:
            # Compatible with pre-tenant roles and post-backfill RLS roles.
            rows = (
                await db.execute(
                    text(
                        "SELECT r.is_owner_preset, p.key FROM roles r LEFT JOIN role_permissions p ON p.role_id=r.id WHERE r.slug=:slug"
                    ),
                    {"slug": user["role"]},
                )
            ).all()
            keys = (
                sorted(PERMISSION_CATALOG)
                if user["role"] == "owner" or any(row[0] for row in rows)
                else sorted({row[1] for row in rows if row[1]})
            )
            record = {
                key: str(value)
                if key in {"id", "team_id", "default_location_id"} and value is not None
                else value
                for key, value in user.items()
            }
            record["permissions"] = keys
            records.append(record)
    return records


def compare(before: list[dict], after: list[dict]) -> list[str]:
    indexed = {row["id"]: row for row in after}
    failures = []
    for row in before:
        current = indexed.get(row["id"])
        if current is None:
            failures.append(f"Missing staff {row['id']}")
            continue
        for key in ("team_id", "is_disabled", "token_version", "default_location_id"):
            if current[key] != row[key]:
                failures.append(f"Changed {key} for {row['id']}")
        if not set(row["permissions"]).issubset(current["permissions"]):
            failures.append(f"Reduced permissions for {row['id']}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["snapshot", "compare"])
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    if args.action == "snapshot" and len(args.paths) == 1:
        args.paths[0].write_text(json.dumps(asyncio.run(inventory()), indent=2) + "\n")
    elif args.action == "compare" and len(args.paths) == 2:
        failures = compare(*(json.loads(path.read_text()) for path in args.paths))
        print(json.dumps({"passed": not failures, "failures": failures}, indent=2))
        raise SystemExit(bool(failures))
    else:
        parser.error("snapshot takes one path; compare takes two")


if __name__ == "__main__":
    main()
