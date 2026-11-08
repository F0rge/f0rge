"""Explicit operator staff import. Default dry-run; never print credentials or PII."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

import httpx

from app.config import settings
from app.database import tenant_session
from app.services.clerk_api import ClerkAPI
from app.services.staff_import import StaffImportService


async def run(team_id: uuid.UUID, commit: bool) -> dict:
    async with httpx.AsyncClient() as client, tenant_session() as db:
        return await StaffImportService(db, ClerkAPI(client, settings.clerk_secret_key)).run(
            team_id, commit=commit
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-id", required=True, type=uuid.UUID)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run(args.team_id, args.commit))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
