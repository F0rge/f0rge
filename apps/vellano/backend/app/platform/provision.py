from __future__ import annotations

import argparse
import asyncio
import datetime
import sys

from sqlalchemy import select

from app.platform.database import platform_sessionmaker
from app.platform.models import (
    SIGNUP_STATUS_VERIFIED,
    Signup,
)
from app.platform.provisioning import ProvisioningService
from app.platform.service import validate_slug
from app.services.auth import hash_password, validate_password
from f0rge_db.crud import unit_of_work


async def _run(slug: str, email: str, legal_name: str, password: str, owner_name: str) -> int:
    validate_slug(slug)
    validate_password(password)
    maker = platform_sessionmaker()
    async with maker() as db:
        existing = (
            await db.execute(select(Signup).where(Signup.slug == slug).limit(1))
        ).scalar_one_or_none()
        if existing is None:
            signup = Signup(
                email=email,
                legal_name=legal_name,
                trading_name=legal_name,
                slug=slug,
                owner_name=owner_name,
                password_hash=hash_password(password),
                status=SIGNUP_STATUS_VERIFIED,
                privacy_version="2026-09-draft",
                authorised_confirmed_at=datetime.datetime.utcnow(),
                verified_at=datetime.datetime.utcnow(),
            )
            async with unit_of_work(db):
                db.add(signup)
                await db.flush()
            signup_id = signup.id
        else:
            signup_id = existing.id
    tenant = await ProvisioningService().provision(signup_id)
    print(f"tenant {tenant.slug} status={tenant.status}")
    return 0 if tenant.status == "ready" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a verified signup and provision it.")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--legal-name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--owner-name", default="Owner")
    args = parser.parse_args()
    try:
        return asyncio.run(
            _run(args.slug, args.email, args.legal_name, args.password, args.owner_name)
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
