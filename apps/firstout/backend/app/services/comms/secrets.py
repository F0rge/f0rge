from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.exceptions import CommsEncryptionUnconfiguredError
from f0rge_core.exceptions import ValidationError


def _get_fernet() -> Fernet:
    key = settings.settings_encryption_key
    if not key:
        raise CommsEncryptionUnconfiguredError()
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise CommsEncryptionUnconfiguredError() from exc


def encrypt(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    try:
        return _get_fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise ValidationError("Could not decrypt stored secret") from exc
