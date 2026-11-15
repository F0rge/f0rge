"""Public non-sensitive readiness facts; no customer data or credentials."""

from __future__ import annotations

import asyncio
import os

import sqlalchemy as sa
from asyncpg import PostgresError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.responses import JSONResponse

from app.commands.release_migrate import SOURCE_SHA, load_policy
from app.database import engine


async def release_readiness(database: AsyncEngine = engine) -> JSONResponse:
    try:
        response = await asyncio.wait_for(_readiness(database), timeout=5)
    except (
        SQLAlchemyError,
        PostgresError,
        TimeoutError,
        ValueError,
        OSError,
        RuntimeError,
        KeyError,
        TypeError,
    ):
        response = JSONResponse({"status": "unavailable"}, status_code=503)
    response.headers["Cache-Control"] = "no-store"
    return response


async def _readiness(database: AsyncEngine) -> JSONResponse:
    source = os.environ.get("SOURCE_COMMIT", "")
    if not SOURCE_SHA.fullmatch(source):
        return JSONResponse({"status": "unavailable"}, status_code=503)
    policy, policy_hash, scripts = load_policy()
    async with database.connect() as connection:
        await connection.execute(sa.text("SELECT 1"))
        revision = (
            (await connection.execute(sa.text("SELECT version_num FROM alembic_version")))
            .scalars()
            .all()
        )
        receipt = (
            (
                await connection.execute(
                    sa.text(
                        "SELECT schema_revision,policy_sha256 FROM release_migration_receipts WHERE source_commit=:commit"
                    ),
                    {"commit": source},
                )
            )
            .mappings()
            .one_or_none()
        )
    if (
        len(revision) != 1
        or not receipt
        or receipt["schema_revision"] != policy["target_revision"]
        or receipt["policy_sha256"] != policy_hash
    ):
        return JSONResponse({"status": "unavailable"}, status_code=503)
    known_old_heads = {item.revision for item in scripts.walk_revisions()} - {
        policy["target_revision"]
    }
    if revision[0] in known_old_heads:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    # A retained previous image must remain ready after a compatible additive
    # migration. The deployment controller checks exact current head for the
    # candidate; recovery compares the retained image/receipt separately.
    return JSONResponse(
        {
            "status": "ok",
            "source_commit": source,
            "schema_revision": revision[0],
            "image_schema_revision": policy["target_revision"],
            "receipt_schema_revision": receipt["schema_revision"],
            "policy_sha256": policy_hash,
            "migration_receipt": True,
        }
    )
