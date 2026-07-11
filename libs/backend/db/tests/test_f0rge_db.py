from __future__ import annotations

from f0rge_db.db_url import asyncpg_connect_args, resolve_database_url
from f0rge_db.rls import create_service_role_policy, enable_tenant_isolation

# ---------------------------------------------------------------------------
# db_url — pure string normalization (lifted from marrow's test_db_url.py)
# ---------------------------------------------------------------------------


def test_resolve_asyncpg_scheme() -> None:
    url = "postgres://user:pass@host:5432/db"
    assert resolve_database_url(url) == "postgresql+asyncpg://user:pass@host:5432/db"


def test_pgbouncer_rewritten_to_direct() -> None:
    pooled = "postgres://fly-user:secret@pgbouncer.abc123.flympg.net/fly-db"
    direct = resolve_database_url(pooled)
    assert "direct.abc123.flympg.net" in direct
    assert "pgbouncer." not in direct


def test_direct_url_override() -> None:
    pooled = "postgres://fly-user:secret@pgbouncer.abc123.flympg.net/fly-db"
    explicit = "postgres://fly-user:secret@direct.abc123.flympg.net/fly-db"
    assert resolve_database_url(pooled, direct_url=explicit) == (
        "postgresql+asyncpg://fly-user:secret@direct.abc123.flympg.net/fly-db"
    )


def test_pooler_disables_statement_cache() -> None:
    pooled = "postgres://u:p@pgbouncer.cluster.flympg.net/db"
    assert asyncpg_connect_args(pooled) == {"statement_cache_size": 0}


def test_direct_host_keeps_statement_cache() -> None:
    direct = "postgres://u:p@direct.cluster.flympg.net/db"
    assert asyncpg_connect_args(direct) == {}


# ---------------------------------------------------------------------------
# rls — helpers emit the same statements the app's inline loops used to
# ---------------------------------------------------------------------------


class _RecordingConn:
    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, clause) -> None:
        self.statements.append(" ".join(str(clause).split()))


async def test_enable_tenant_isolation_sql() -> None:
    conn = _RecordingConn()
    await enable_tenant_isolation(conn, ["entries"])
    assert conn.statements == [
        "ALTER TABLE entries ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE entries FORCE ROW LEVEL SECURITY",
        "CREATE POLICY tenant_isolation ON entries FOR ALL "
        "USING (user_id = current_setting('app.user_id', true)::uuid) "
        "WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)",
    ]


async def test_service_role_policy_all_sql() -> None:
    conn = _RecordingConn()
    await create_service_role_policy(
        conn, name="provisioner_copy", tables=["dietary_ingredients"], role="provisioner"
    )
    assert conn.statements == [
        "CREATE POLICY provisioner_copy ON dietary_ingredients FOR ALL "
        "USING (current_setting('app.service_role', true) = 'provisioner') "
        "WITH CHECK (current_setting('app.service_role', true) = 'provisioner')",
    ]


async def test_service_role_policy_select_has_no_with_check() -> None:
    conn = _RecordingConn()
    await create_service_role_policy(
        conn, name="mcp_auth_lookup", tables=["user_settings"], role="mcp_auth", command="SELECT"
    )
    assert conn.statements == [
        "CREATE POLICY mcp_auth_lookup ON user_settings FOR SELECT "
        "USING (current_setting('app.service_role', true) = 'mcp_auth')",
    ]
