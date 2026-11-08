"""Seed or serve a disposable Firstout instance for the local checkout walkthrough."""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import os
import re
import socket
import sys
from pathlib import Path


def block_outbound_connections() -> None:
    """Apply to DNS and TCP, including asyncpg and any accidental provider call."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo

    def check(host: str) -> None:
        if host == "localhost":
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise PermissionError("Local checkout fixture blocks outbound connections")

    def connect(connection, address):
        if isinstance(address, tuple):
            check(address[0])
        return original_connect(connection, address)

    def connect_ex(connection, address):
        if isinstance(address, tuple):
            check(address[0])
        return original_connect_ex(connection, address)

    def getaddrinfo(host, *args, **kwargs):
        if host is not None:
            check(host)
        return original_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo


async def seed(state: Path, api_port: int) -> None:
    from decimal import Decimal

    import app.models  # noqa: F401
    import sqlalchemy as sa
    from app.database import Base, TenantSession
    from app.models.inventory import LocationStock, SkuStock
    from app.models.location import Location
    from app.models.sku import Sku
    from app.models.team import Team
    from app.services.chart_of_accounts import ChartOfAccountsSeedService
    from app.services.locations import LocationSeedService
    from app.services.roles import RoleSeedService
    from app.services.storefront_system_actor import StorefrontSystemActorService
    from app.services.users import BootstrapService
    from f0rge_db.organisation import apply_tenant_context, tenant_id_ctx
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as connection:
        existing = await connection.scalar(
            sa.text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
        )
        if existing:
            raise RuntimeError("Fixture seed requires an empty disposable database")
        await connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext"))
        await connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await connection.run_sync(Base.metadata.create_all)

    async with async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
        sync_session_class=TenantSession,
    )() as session:
        await BootstrapService(session).seed_if_empty()
        team = await session.scalar(sa.select(Team).limit(1))
        token = tenant_id_ctx.set(team.id)
        await apply_tenant_context(session, team.id)
        await RoleSeedService(session).seed()
        await LocationSeedService(session).seed_if_empty()
        await StorefrontSystemActorService(session).ensure()
        coa = ChartOfAccountsSeedService(session)
        await coa.seed_if_empty()
        await coa.ensure_opening_equity()
        await coa.ensure_customer_deposits()
        await coa.ensure_storefront_gateway_clearing()
        await coa.ensure_category_chart()
        await coa.ensure_bank_accounts()
        location = await session.scalar(sa.select(Location).where(Location.name == "Kramerville"))
        sku = Sku(
            our_ref="LOCAL-CHECKOUT-SOFA",
            our_barcode="LOCAL-CHECKOUT-SOFA",
            name="Local checkout fixture sofa",
            design="Local checkout fixture",
            fabric="Synthetic sand",
            retail_ex_vat=Decimal("1000.00"),
            storefront_published=True,
        )
        session.add(sku)
        await session.flush()
        session.add_all(
            [
                LocationStock(
                    sku_id=sku.id,
                    location_id=location.id,
                    on_hand=50,
                    unit_cost_zar=Decimal("400.00"),
                ),
                SkuStock(sku_id=sku.id, on_order=0),
            ]
        )
        await session.commit()
        fixture = {
            "company_id": str(team.id),
            "sku_id": str(sku.id),
            "sku": sku.our_ref,
        }
        tenant_id_ctx.reset(token)

    async with engine.begin() as connection:
        await connection.execute(
            sa.text(
                "CREATE ROLE firstout_checkout_runtime LOGIN PASSWORD 'local-only-runtime' "
                "NOSUPERUSER NOBYPASSRLS"
            )
        )
        await connection.execute(
            sa.text("GRANT USAGE ON SCHEMA public TO firstout_checkout_runtime")
        )
        await connection.execute(
            sa.text(
                "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public "
                "TO firstout_checkout_runtime"
            )
        )
        await connection.execute(
            sa.text(
                "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO firstout_checkout_runtime"
            )
        )
        for table in Base.metadata.sorted_tables:
            if "team_id" not in table.c or table.name in ("users", "memberships"):
                continue
            name = engine.dialect.identifier_preparer.quote(table.name)
            await connection.execute(sa.text(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY"))
            await connection.execute(sa.text(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY"))
            predicate = "team_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
            await connection.execute(
                sa.text(
                    f"CREATE POLICY organisation_isolation ON {name} "
                    f"USING ({predicate}) WITH CHECK ({predicate})"
                )
            )
    (state / "fixture.json").write_text(json.dumps(fixture) + "\n")
    (state / "commerce.env").write_text(
        f"FIRSTOUT_OPS_URL=http://127.0.0.1:{api_port}/api/v1/ops-commerce/v1\n"
        f"FIRSTOUT_OPS_COMPANY_ID={fixture['company_id']}\n"
        "FIRSTOUT_OPS_TOKEN=local-checkout-machine-token\n"
    )
    await engine.dispose()
    print(f"Created one synthetic published SKU; integration settings: {state / 'commerce.env'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["seed", "serve"])
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--database", default="firstout_checkout_local")
    parser.add_argument("--postgres-port", type=int, default=15433)
    parser.add_argument("--api-port", type=int, default=18003)
    args = parser.parse_args()
    if not re.fullmatch(r"firstout_checkout_[a-z0-9_]+", args.database):
        parser.error("Only disposable firstout_checkout_* databases are allowed")
    if any(not 1024 <= port <= 65535 for port in (args.postgres_port, args.api_port)):
        parser.error("Ports must be between 1024 and 65535")
    state = args.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=True)
    if (state / ".env").exists():
        parser.error("State directory must not contain a .env file")
    backend = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend))
    os.chdir(state)
    # Pydantic reads .env relative to cwd. Start with only known local settings;
    # no inherited Railway, SMTP, Clerk, object-storage, or payment credentials.
    os.environ.clear()
    os.environ.update(
        {
            "PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin",
            "HOME": str(state),
            "JWT_SECRET": "local-only-checkout-jwt-secret-32char",
            "PAYMENT_REMINDER_TICKER": "false",
            "SEED_BOOT_FIXTURES": "false",
            "SEED_PLAYGROUND": "false",
            "CLERK_ENABLED": "false",
            "TENANT_SIGNUP_ENABLED": "false",
            "BILLING_DISABLED": "true",
            "BILLING_TEST_MODE": "true",
            "STORAGE_DIR": str(state / "storage"),
            "SEED_OWNER_EMAIL": "owner@example.com",
            "SEED_OWNER_PASSWORD": "local-only-checkout-owner",
        }
    )
    block_outbound_connections()
    if args.command == "seed":
        os.environ["DATABASE_URL"] = (
            f"postgresql+asyncpg://firstout:local-only-firstout@127.0.0.1:"
            f"{args.postgres_port}/{args.database}"
        )
        asyncio.run(seed(state, args.api_port))
    else:
        fixture = json.loads((state / "fixture.json").read_text())
        os.environ.update(
            {
                "DATABASE_URL": (
                    "postgresql+asyncpg://firstout_checkout_runtime:local-only-runtime@127.0.0.1:"
                    f"{args.postgres_port}/{args.database}"
                ),
                "TENANT_ISOLATION_MODE": "enforced",
                "FRONTEND_PROXY_SECRET": "local-checkout-proxy-secret",
                "OPS_COMMERCE_COMPANY_ID": fixture["company_id"],
                "OPS_COMMERCE_TOKEN": "local-checkout-machine-token",
                "OPS_COMMERCE_ALLOWED_HOST": "127.0.0.1",
            }
        )
        import uvicorn

        uvicorn.run("app.main:app", host="127.0.0.1", port=args.api_port, loop="asyncio")


if __name__ == "__main__":
    main()
