// Exercise the tested backend image against disposable PostgreSQL, with only
// Clerk's external signing-key lookup replaced by an owned RSA key fixture.
// The Docker network has no internet; no production identity/data is used.
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { randomBytes } from "node:crypto";

function docker(args, input) {
  const result = spawnSync("docker", args, { encoding: "utf8", input, maxBuffer: 8 * 1024 * 1024, timeout: 240000 });
  if (result.status !== 0) throw new Error(`Docker ${args[0]} failed (${result.status ?? result.signal ?? result.error?.message}): ${result.stderr || result.stdout}`);
  return (args[0] === "logs" ? result.stdout + result.stderr : result.stdout).trim();
}
const image = process.argv[2];
if (!image || !/^[a-z0-9][a-z0-9/_.:@-]+$/.test(image)) throw new Error("Pass the tested local backend image");
// Local rehearsals can build the actual old source without publishing it. The
// privileged workflow never uses this option; its baseline must be immutable.
const localPrevious = process.argv[3]?.startsWith("--previous-local-image=") ? process.argv[3].split("=",2)[1] : null;
if (localPrevious && !/^firstout-backend:cd-baseline$/.test(localPrevious)) throw new Error("Invalid local rehearsal image");
const previous = localPrevious || process.env.PREVIOUS_BACKEND_IMAGE;
if (!localPrevious && (!previous || !/^ghcr\.io\/f0rge\/firstout-api@sha256:[0-9a-f]{64}$/.test(previous))) throw new Error("A verified previous API digest is required for compatibility testing");
const prefix = `firstout-cd-${randomBytes(6).toString("hex")}`;
const network = prefix + "-net", pg = prefix + "-pg";
const directory = mkdtempSync(join(tmpdir(), prefix));
const containers = [];
const ownerPassword = randomBytes(24).toString("hex"), runtimePassword = randomBytes(24).toString("hex");
const dbUrl = `postgresql+asyncpg://firstout_app:${runtimePassword}@${pg}:5432/firstout_cd_test_fixture`;
const migrationUrl = `postgresql+asyncpg://firstout:${ownerPassword}@${pg}:5432/firstout_cd_test_fixture`;
const env = ["--env", `DATABASE_URL=${dbUrl}`, "--env", "DIRECT_DATABASE_URL=", "--env", "PAYMENT_REMINDER_TICKER=false", "--env", "SEED_BOOT_FIXTURES=false", "--env", "SEED_PLAYGROUND=false", "--env", "TENANT_ISOLATION_MODE=enforced", "--env", "FRONTEND_PROXY_SECRET=synthetic-cd-proxy-only", "--env", "CLERK_ENABLED=true", "--env", "CLERK_ISSUER=https://synthetic.clerk.accounts.dev", "--env", 'CLERK_AUTHORIZED_PARTIES=["http://test"]', "--env", "RECORD_WORKSPACE_SIGNING_KEY=isolated-cd-fixture-signing-key-32-characters"];
// The HTTP application never receives the administrative database credential.
const migrationEnv = [...env, "--env", `MIGRATION_DATABASE_URL=${migrationUrl}`];
const fixture = String.raw`
import asyncio, json, os, time, sys, uuid
sys.path.insert(0, "/app/apps/firstout/backend")
from pathlib import Path
from types import SimpleNamespace
import jwt, uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.main import app
from app.models.team import Team
from app.models.user import User
from app.models.membership import Membership
from app.models.customer import Customer
import app.services.clerk as clerk
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
clerk.jwks_client = lambda issuer: SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key()))
async def seed():
    admin = create_async_engine(os.environ["MIGRATION_DATABASE_URL"])
    sessions = async_sessionmaker(admin, expire_on_commit=False)
    try:
        async with sessions() as db:
            team = await db.scalar(select(Team).where(Team.slug == "cd-fixture"))
            if team is None:
                team = Team(name="Disposable CD fixture", slug="cd-fixture", clerk_org_id="org_cd_fixture")
                db.add(team)
                await db.flush()
            user = await db.scalar(select(User).where(User.clerk_user_id == "user_cd_fixture"))
            if user is None:
                user = User(team_id=team.id, clerk_user_id="user_cd_fixture", email="cd-fixture@example.com", password_hash="not-a-login", role="owner")
                db.add(user)
                await db.flush()
                db.add(Membership(user_id=user.id, team_id=team.id, role="owner", is_legacy_home=True))
            other = Team(name="Other disposable CD fixture", slug="cd-foreign", clerk_org_id="org_cd_foreign")
            db.add(other)
            await db.flush()
            db.add(Customer(id=uuid.UUID("22222222-2222-4222-8222-222222222222"), team_id=other.id, name="Foreign CD fixture customer"))
            await db.commit()
    finally:
        await admin.dispose()
if os.environ.get("CD_SEED_ONLY") == "true":
    asyncio.run(seed())
    raise SystemExit(0)
now = int(time.time())
claims = {"iss":"https://synthetic.clerk.accounts.dev", "sub":"user_cd_fixture", "iat":now, "nbf":now, "exp":now+600, "azp":"http://test", "o":{"id":"org_cd_fixture", "slg":"cd-fixture", "rol":"member"}}
Path("/tmp/cd-token").write_text(jwt.encode(claims, key, algorithm="RS256"))
uvicorn.run(app, host="0.0.0.0", port=8000, lifespan="off", access_log=False)
`;
const probe = String.raw`
import asyncio, json, os, time, urllib.request, urllib.error
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import engine
from app.runtime_database import verify_isolation_stage

assert "MIGRATION_DATABASE_URL" not in os.environ, "HTTP fixture must not receive administrative credentials"
async def runtime_privileges():
    # The JWT fixture disables lifespan to replace only external signing-key
    # lookup. Explicitly exercise the normal production isolation startup gate.
    async with AsyncSession(engine) as session:
        await verify_isolation_stage(session)
    async with engine.connect() as connection:
        role = (await connection.execute(text("SELECT current_user AS name, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"))).mappings().one()
        assert role["name"] == "firstout_app" and not role["rolsuper"] and not role["rolbypassrls"]
        assert not await connection.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND pg_has_role(current_user,c.relowner,'MEMBER'))"))
        tenant_tables = (await connection.execute(text("SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND c.relname NOT IN ('users','memberships') AND EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attname='team_id')"))).mappings().all()
        assert tenant_tables and all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in tenant_tables), "Tenant RLS must be enabled and forced"
        assert "record_workspace_batches" in {row["relname"] for row in tenant_tables}
        assert await connection.scalar(text("SELECT count(*) FROM customers")) == 0, "Runtime without tenant context must not see customer rows"
    for table, column in (("alembic_version", "version_num"), ("release_migration_receipts", "source_commit")):
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT has_table_privilege(current_user,:table,'SELECT')"), {"table": table})
            assert not await connection.scalar(text("SELECT has_table_privilege(current_user,:table,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"), {"table": table}), "Runtime can write release metadata"
        try:
            async with engine.begin() as connection:
                await connection.execute(text(f"UPDATE {table} SET {column}={column} WHERE false"))
        except DBAPIError as error:
            assert getattr(error.orig, "sqlstate", None) == "42501", "Expected PostgreSQL privilege denial"
        else:
            raise AssertionError("Runtime metadata UPDATE was allowed")
    await engine.dispose()
asyncio.run(runtime_privileges())

base="http://127.0.0.1:8000/api/v1"
for attempt in range(60):
    if Path("/tmp/cd-token").exists(): break
    if attempt==59: raise AssertionError("Synthetic identity fixture did not become ready")
    time.sleep(.5)
token=Path("/tmp/cd-token").read_text()
def request(path, body=None, authenticated=True):
    headers={"Host":"test", "Content-Type":"application/json"}
    if authenticated: headers["Authorization"]="Bearer "+token
    req=urllib.request.Request(base+path, headers=headers, data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=10) as response: return json.load(response)
for attempt in range(60):
    try:
        assert request("/health")["status"]=="ok"
        break
    except Exception:
        if attempt==59: raise
        time.sleep(.5)
assert request("/auth/me")["team"]["name"]=="Disposable CD fixture"
if os.environ.get("CD_CANDIDATE") == "true":
    ready_request=urllib.request.Request(base+"/ready", headers={"Host":"test"})
    with urllib.request.urlopen(ready_request, timeout=10) as response:
        assert response.headers.get("Cache-Control")=="no-store"
        ready=json.load(response)
    assert ready["status"]=="ok" and ready["migration_receipt"] is True
    assert ready["source_commit"]==os.environ["SOURCE_COMMIT"]
    assert ready["schema_revision"]==ready["image_schema_revision"]==ready["receipt_schema_revision"]
try:
    request("/customers", authenticated=False)
    raise AssertionError("Unauthenticated requests must be denied")
except urllib.error.HTTPError as error: assert error.code==401
customers=request("/customers")
items=customers.get("items",[]) if isinstance(customers,dict) else customers
assert all(row["id"] != "22222222-2222-4222-8222-222222222222" and row["name"] != "Foreign CD fixture customer" for row in items), "Cross-tenant customer leaked in list"
try:
    request("/customers/22222222-2222-4222-8222-222222222222")
    raise AssertionError("Cross-tenant customer was readable")
except urllib.error.HTTPError as error: assert error.code == 404
if not any(row["name"]=="CD compatibility customer" for row in items):
    created=request("/customers", {"name":"CD compatibility customer", "classification":"retail", "payment_terms_days":30})
    assert created["name"]=="CD compatibility customer"
else: assert any(row["name"]=="CD compatibility customer" for row in items)
print("Actual backend image HTTP/auth/PostgreSQL journey passed")
`;
writeFileSync(join(directory, "fixture.py"), fixture);
try {
  if (!localPrevious) docker(["pull", "--platform", "linux/amd64", previous]);
  docker(["network", "create", "--internal", network]);
  containers.push(pg);
  // Match Firstout production and the retained manual API image probe's major.
  docker(["run", "--detach", "--name", pg, "--network", network, "--env", "POSTGRES_USER=firstout", "--env", `POSTGRES_PASSWORD=${ownerPassword}`, "--env", "POSTGRES_DB=firstout_cd_test_fixture", "postgres:18"]);
  // Initialization briefly accepts socket connections before creating the
  // target database. Wait for a real query over the final server's TCP socket.
  docker(["exec", "--env", `PGPASSWORD=${ownerPassword}`, pg, "sh", "-c", "until psql -h 127.0.0.1 -U firstout -d firstout_cd_test_fixture -tAc 'SELECT 1' >/dev/null 2>&1; do sleep 1; done"]);
  // Default business-table grants reproduce the production metadata leak: the
  // migration runner must remove them only from its two metadata tables.
  docker(["exec", "-i", pg, "psql", "-v", "ON_ERROR_STOP=1", "-U", "firstout", "-d", "firstout_cd_test_fixture"], `
    CREATE ROLE firstout_app LOGIN PASSWORD '${runtimePassword}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    GRANT CONNECT ON DATABASE firstout_cd_test_fixture TO firstout_app;
    GRANT USAGE ON SCHEMA public TO firstout_app;
    ALTER DEFAULT PRIVILEGES FOR ROLE firstout IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO firstout_app;
    ALTER DEFAULT PRIVILEGES FOR ROLE firstout IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO firstout_app;
  `);
  docker(["run", "--rm", "--platform", "linux/amd64", "--network", network, ...migrationEnv, "--entrypoint", ".venv/bin/python", image, "-m", "app.commands.release_migrate", "--bootstrap-test-database"]);
  // A second invocation must be idempotent; readiness requires its durable receipt.
  docker(["run", "--rm", "--platform", "linux/amd64", "--network", network, ...migrationEnv, "--entrypoint", ".venv/bin/python", image, "-m", "app.commands.release_migrate"]);
  docker(["run", "--rm", "--platform", "linux/amd64", "--network", network, ...migrationEnv, "--env", "CD_SEED_ONLY=true", "--mount", `type=bind,source=${join(directory, "fixture.py")},target=/tmp/cd-fixture.py,readonly`, "--entrypoint", ".venv/bin/python", image, "/tmp/cd-fixture.py"]);
  // Match the explicit production cutover; migrations only prepare policies.
  docker(["run", "--rm", "--platform", "linux/amd64", "--network", network, ...migrationEnv, "--entrypoint", ".venv/bin/python", image, "-m", "app.commands.tenant_cutover", "activate"]);
  for (const [index, candidate] of [image, ...(previous ? [previous] : [])].entries()) {
    const name = prefix + "-api-" + index;
    containers.push(name);
    docker(["run", "--detach", "--platform", "linux/amd64", "--name", name, "--network", network, ...env, "--mount", `type=bind,source=${join(directory, "fixture.py")},target=/tmp/cd-fixture.py,readonly`, "--entrypoint", ".venv/bin/python", candidate, "/tmp/cd-fixture.py"]);
    try { console.log(docker(["exec", "--env", `CD_CANDIDATE=${index === 0}`, "-i", name, ".venv/bin/python", "-"], probe)); }
    catch(error) { console.error(docker(["logs", name])); throw error; }
    docker(["rm", "--force", name]);
    containers.splice(containers.indexOf(name), 1);
  }
  console.log(previous ? "Previous backend image reads new-schema/new-version writes" : "Bootstrap candidate checked; previous-image compatibility requires a retained baseline image");
} finally {
  for (const name of containers.reverse()) { try { docker(["rm", "--force", name]); } catch {} }
  try { docker(["network", "rm", network]); } catch {}
  rmSync(directory, {recursive:true, force:true});
}
