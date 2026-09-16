from __future__ import annotations

import pytest

from tests.test_tenancy_routing import _raw_client

LEAK_PATHS = (
    "/api/v1/skus",
    "/api/v1/customers",
    "/api/v1/invoices",
    "/api/v1/quotes",
    "/api/v1/orders",
    "/api/v1/settings",
    "/api/v1/users",
    "/api/v1/reports/aged-ar",
    "/api/v1/portal/me",
    "/api/v1/nia/threads",
)


@pytest.mark.asyncio
async def test_unresolved_tenant_404s_on_leak_surfaces(platform_registry: str) -> None:
    async with _raw_client() as client:
        for path in LEAK_PATHS:
            resp = await client.get(path)
            assert resp.status_code == 404, path
            assert resp.json()["detail"] == "tenant_not_found"


@pytest.mark.no_db
def test_no_request_path_default_tenant() -> None:
    from pathlib import Path
    import inspect

    import app.tenancy.resolver as resolver

    source = inspect.getsource(resolver.resolve_tenant)
    assert "default_tenant" not in source
    db_source = Path(__file__).resolve().parents[1].joinpath("app/database.py").read_text()
    assert "async_session_maker()" not in db_source.split("def get_db")[1]


@pytest.mark.no_db
def test_async_session_maker_not_on_request_path() -> None:
    from pathlib import Path

    app_root = Path(__file__).resolve().parents[1] / "app"
    hits = []
    for path in app_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(app_root))
        for index, line in enumerate(text.splitlines(), start=1):
            if "async_session_maker(" in line and "create_engine_and_sessionmaker" not in line:
                hits.append(f"{rel}:{index}:{line.strip()}")
    assert hits == [], hits
