from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def _to_asyncpg_scheme(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


def _prefer_direct_mpg_url(url: str) -> str:
    """Use the direct MPG host when Fly provides a pooled PgBouncer URL.

    Fly Managed Postgres attach sets DATABASE_URL to PgBouncer
    (``pgbouncer.<cluster>.flympg.net``). asyncpg prepared statements break
    through transaction pooling, so prefer ``direct.<cluster>.flympg.net``.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if "pgbouncer." in host:
        direct_host = host.replace("pgbouncer.", "direct.", 1)
        netloc = parsed.netloc.replace(host, direct_host, 1)
        return urlunparse(parsed._replace(netloc=netloc))
    if ".pooler." in host:
        direct_host = host.replace(".pooler.", ".", 1)
        netloc = parsed.netloc.replace(host, direct_host, 1)
        return urlunparse(parsed._replace(netloc=netloc))
    return url


def _uses_pooler(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return "pgbouncer." in host or ".pooler." in host


def resolve_database_url(url: str, *, direct_url: str = "") -> str:
    """Normalize a Fly/local DATABASE_URL for SQLAlchemy asyncpg."""
    if direct_url:
        return _to_asyncpg_scheme(direct_url)
    return _to_asyncpg_scheme(_prefer_direct_mpg_url(url))


def asyncpg_connect_args(url: str) -> dict:
    """Extra connect_args for create_async_engine when using asyncpg."""
    args: dict = {}
    if _uses_pooler(_to_asyncpg_scheme(url)):
        # Fallback if direct rewrite was not possible.
        args["statement_cache_size"] = 0
    return args
