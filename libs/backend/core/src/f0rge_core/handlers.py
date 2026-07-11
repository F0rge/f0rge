from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from f0rge_core.exceptions import (
    ConflictError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)

STATUS_BY_EXCEPTION: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_400_BAD_REQUEST,
    ConflictError: status.HTTP_409_CONFLICT,
    UnauthorizedError: status.HTTP_401_UNAUTHORIZED,
    ExternalServiceError: status.HTTP_502_BAD_GATEWAY,
}


def register_exception_handlers(app: FastAPI) -> None:
    """Map each DomainError subclass to ``{"detail": ...}`` with its status code.

    Same behavior as the five inline ``@app.exception_handler`` blocks this
    replaces: one handler per concrete subclass, JSON body ``{"detail":
    exc.detail}``. A bare ``DomainError`` stays unhandled (500), as before.
    """
    for exc_type, status_code in STATUS_BY_EXCEPTION.items():

        async def _handler(
            _: Request, exc: DomainError, *, _status_code: int = status_code
        ) -> JSONResponse:
            return JSONResponse(status_code=_status_code, content={"detail": exc.detail})

        app.add_exception_handler(exc_type, _handler)
