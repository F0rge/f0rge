from __future__ import annotations

from app.db_url import asyncpg_connect_args, resolve_database_url


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
