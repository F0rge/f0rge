from __future__ import annotations

from pydantic import BaseModel


class PinLogin(BaseModel):
    pin: str


class AuthStatus(BaseModel):
    authenticated: bool
