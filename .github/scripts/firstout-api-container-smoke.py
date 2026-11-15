"""Exercise the exact API image with a disposable, egress-isolated PostgreSQL.

Only synthetic credentials and data are used. This script neither publishes an
image nor contacts Railway, Clerk, mail providers or production databases.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess
import time
from pathlib import Path

PYTHON = "/app/apps/firstout/backend/.venv/bin/python"
IMAGE_REF = re.compile(r"[a-z0-9][a-z0-9/_.:@-]*\Z")
SOURCE_SHA = re.compile(r"[0-9a-f]{40}\Z")


def docker(*args: str, capture: bool = True, check: bool = True) -> str:
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=180, check=False
    )
    if check and result.returncode:
        # Even local diagnostic output must not become a credential log. This
        # harness supplies only synthetic values, but never echoes argv/stderr.
        raise RuntimeError(f"Docker {args[0]} failed with exit {result.returncode}")
    return result.stdout.strip() if capture else ""


def image_identity(image: str, source_commit: str) -> dict[str, str]:
    values = json.loads(docker("image", "inspect", image))[0]
    if f"{values['Os']}/{values['Architecture']}" != "linux/amd64":
        raise RuntimeError("The release image must be linux/amd64")
    revision = (
        values["Config"].get("Labels", {}).get("org.opencontainers.image.revision")
    )
    if revision != source_commit:
        raise RuntimeError("The image revision does not match the selected source")
    if values["Config"].get("User") != "app":
        raise RuntimeError("The API image must run as the existing app user")
    expected = [
        PYTHON,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    if values["Config"].get("Cmd") != expected:
        raise RuntimeError("The image must use the frozen application interpreter")
    return {
        "image_id": values["Id"],
        "platform": "linux/amd64",
        "source_commit": revision,
    }


PROBE = r"""
import asyncio, json, os, time, urllib.error, urllib.request
import asyncpg
from alembic.config import Config
from alembic.script import ScriptDirectory
import app.commands.replace_primavera

def get(path):
    return urllib.request.urlopen(urllib.request.Request(
        'http://127.0.0.1:8000' + path,
        headers={'Host': 'localhost:8003', 'Cache-Control': 'no-cache'},
    ), timeout=3)

ready = False
for attempt in range(120):
    try:
        with get('/api/v1/health') as response:
            assert response.status == 200
            assert json.load(response) == {'status': 'ok'}
            assert 'no-store' in response.headers.get('Cache-Control', '')
            ready = True
            break
    except (OSError, AssertionError, ValueError):
        time.sleep(0.5)
assert ready, 'Normal API startup/readiness failed'
for path in ['/api/v1/skus', '/api/v1/customers/archive-counts']:
    try:
        get(path)
        raise AssertionError('Anonymous account/catalogue access was allowed')
    except urllib.error.HTTPError as error:
        assert error.code == 401
with get('/openapi.json') as response:
    schema = json.load(response)
    assert '/api/v1/customers/{customer_id}/archive' in schema['paths']
    assert '/api/v1/stocktakes/{stocktake_id}/lines/{line_id}' in schema['paths']
    assert 'is_sellable' in schema['components']['schemas']['SkuResponse']['properties']

scripts = ScriptDirectory.from_config(Config('alembic.ini'))
heads = scripts.get_heads()
assert len(heads) == 1, 'A release must have one joined Alembic head'
assert {'089_merge_record_workspaces', '088_archive_sales_precision', '085_record_workspaces'} <= {revision.revision for revision in scripts.walk_revisions()}
async def database_check():
    connection = await asyncpg.connect(os.environ['DATABASE_URL'].replace('+asyncpg', ''))
    try:
        row = await connection.fetchrow('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')
        assert not row['rolsuper'] and not row['rolbypassrls']
        assert not await connection.fetchval('''SELECT EXISTS (
            SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind='r'
            AND c.relname NOT IN ('users','memberships')
            AND EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attname='team_id')
            AND NOT(c.relrowsecurity AND c.relforcerowsecurity))''')
        assert await connection.fetchval('SELECT version_num FROM alembic_version') == heads[0]
        assert await connection.fetchval('SELECT count(*) FROM users') == 1
        for table, column in [('location_stock','on_hand'), ('po_lines','qty'), ('bill_lines','qty')]:
            data_type = await connection.fetchval(
                'SELECT data_type FROM information_schema.columns WHERE table_schema=$1 AND table_name=$2 AND column_name=$3',
                'public', table, column,
            )
            assert data_type == 'numeric'
    finally:
        await connection.close()
asyncio.run(database_check())
print(json.dumps({'schema_revision': heads[0], 'passed': True}))
"""


def smoke(image: str, source_commit: str) -> dict[str, object]:
    if not IMAGE_REF.fullmatch(image) or not SOURCE_SHA.fullmatch(source_commit):
        raise ValueError(
            "Pass a local image reference and the full selected source SHA"
        )
    identity = image_identity(image, source_commit)
    suffix = secrets.token_hex(8)
    network = f"firstout-api-smoke-{suffix}"
    database = f"firstout-api-smoke-db-{suffix}"
    api = f"firstout-api-smoke-app-{suffix}"
    owner_password, runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    owner_url = f"postgresql+asyncpg://smoke_owner:{owner_password}@database:5432/firstout_release"
    runtime_url = f"postgresql+asyncpg://smoke_runtime:{runtime_password}@database:5432/firstout_release"
    common_env = [
        "-e",
        "DIRECT_DATABASE_URL=",
        "-e",
        "SEED_BOOT_FIXTURES=false",
        "-e",
        "SEED_PLAYGROUND=false",
        "-e",
        "PAYMENT_REMINDER_TICKER=false",
        "-e",
        "JWT_SECRET=synthetic-release-image-smoke-only",
    ]
    enforced_env = [
        "-e",
        "TENANT_ISOLATION_MODE=enforced",
        "-e",
        "FRONTEND_PROXY_SECRET=synthetic-release-proxy-only",
    ]
    try:
        docker("network", "create", "--internal", network)
        docker(
            "run",
            "--detach",
            "--platform",
            "linux/amd64",
            "--name",
            database,
            "--network",
            network,
            "--network-alias",
            "database",
            "-e",
            "POSTGRES_USER=smoke_owner",
            "-e",
            f"POSTGRES_PASSWORD={owner_password}",
            "-e",
            "POSTGRES_DB=firstout_release",
            "postgres:18",
        )
        for attempt in range(120):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    database,
                    "pg_isready",
                    "-U",
                    "smoke_owner",
                    "-d",
                    "firstout_release",
                ],
                capture_output=True,
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Disposable PostgreSQL did not become ready")
        docker(
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            network,
            *common_env,
            "-e",
            f"DATABASE_URL={owner_url}",
            "-e",
            f"MIGRATION_DATABASE_URL={owner_url}",
            "--entrypoint",
            PYTHON,
            image,
            "-m",
            "alembic",
            "upgrade",
            "head",
        )
        grants = (
            f"CREATE ROLE smoke_runtime LOGIN PASSWORD '{runtime_password}' NOSUPERUSER NOBYPASSRLS;"
            "GRANT USAGE ON SCHEMA public TO smoke_runtime;"
            "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO smoke_runtime;"
            "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO smoke_runtime;"
        )
        docker(
            "exec",
            database,
            "psql",
            "-U",
            "smoke_owner",
            "-d",
            "firstout_release",
            "--no-psqlrc",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            grants,
        )
        # Migration 081 prepares policies without enabling them. Exercise the
        # existing explicit owner/runtime cutover on this disposable database;
        # do not weaken the application's enforced-mode startup verification.
        docker(
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            network,
            *common_env,
            *enforced_env,
            "-e",
            f"DATABASE_URL={runtime_url}",
            "-e",
            f"MIGRATION_DATABASE_URL={owner_url}",
            "--entrypoint",
            PYTHON,
            image,
            "-m",
            "app.commands.tenant_cutover",
            "activate",
        )
        docker(
            "run",
            "--detach",
            "--platform",
            "linux/amd64",
            "--name",
            api,
            "--network",
            network,
            *common_env,
            *enforced_env,
            "-e",
            f"DATABASE_URL={runtime_url}",
            "-e",
            "CLERK_ENABLED=true",
            "-e",
            "CLERK_ISSUER=https://synthetic.clerk.accounts.dev",
            "-e",
            'CLERK_AUTHORIZED_PARTIES=["http://localhost:8003"]',
            image,
        )
        probe = json.loads(docker("exec", api, PYTHON, "-c", PROBE))
        if probe.get("passed") is not True:
            raise RuntimeError("API image probe did not pass")
        network_state = json.loads(docker("network", "inspect", network))[0]
        if network_state.get("Internal") is not True:
            raise RuntimeError("The smoke network was not egress-isolated")
        return {
            **identity,
            "image": image,
            "schema_revision": probe["schema_revision"],
            "passed": True,
            "database_major": 18,
            "network_internal": True,
            "checks": [
                "real_startup",
                "migrations",
                "non_owner_runtime",
                "forced_tenant_rls",
                "readiness_no_store",
                "anonymous_401",
                "packaged_contract",
                "replacement_command_import",
            ],
        }
    finally:
        docker("rm", "--force", "--volumes", api, database, check=False)
        docker("network", "rm", network, check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = smoke(args.image, args.source_commit)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        "Firstout API image smoke passed: isolated PostgreSQL18, normal startup, migrations, role and HTTP contracts"
    )


if __name__ == "__main__":
    main()
