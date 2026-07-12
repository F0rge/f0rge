from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from f0rge_core.exceptions import (
    ConflictError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from f0rge_core.handlers import register_exception_handlers

CASES = [
    (NotFoundError, 404),
    (ValidationError, 400),
    (ConflictError, 409),
    (UnauthorizedError, 401),
    (ExternalServiceError, 502),
]


def test_exceptions_round_trip() -> None:
    for exc_type, _ in CASES:
        exc = exc_type("boom")
        assert isinstance(exc, DomainError)
        assert exc.detail == "boom"
        assert str(exc) == "boom"


@pytest.mark.parametrize("exc_type,expected_status", CASES)
def test_handler_registration(exc_type: type[DomainError], expected_status: int) -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise exc_type("it broke")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == expected_status
    assert resp.json() == {"detail": "it broke"}
