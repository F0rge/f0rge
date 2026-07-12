from __future__ import annotations

from f0rge_testing import async_url, postgres_container_fixture, savepoint_session


class _FakeContainer:
    def __init__(self, url: str) -> None:
        self._url = url

    def get_connection_url(self) -> str:
        return self._url


def test_async_url_swaps_psycopg2() -> None:
    c = _FakeContainer("postgresql+psycopg2://test:test@localhost:55432/test")
    assert async_url(c) == "postgresql+asyncpg://test:test@localhost:55432/test"


def test_async_url_bare_scheme() -> None:
    c = _FakeContainer("postgresql://test:test@localhost:55432/test")
    assert async_url(c) == "postgresql+asyncpg://test:test@localhost:55432/test"


def test_container_factory_returns_session_scoped_fixture() -> None:
    fixture = postgres_container_fixture("pgvector/pgvector:pg16")
    assert fixture._fixture_function_marker.scope == "session"


def test_savepoint_session_is_async_contextmanager() -> None:
    # Container-backed behavior (savepoint rollback) is exercised end-to-end
    # by the marrow suite; here we only pin the public shape.
    cm = savepoint_session.__wrapped__
    import inspect

    assert inspect.isasyncgenfunction(cm)
