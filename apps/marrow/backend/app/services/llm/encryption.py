from __future__ import annotations

import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.settings_encryption_key
    if not key:
        raise ValueError(
            "settings_encryption_key is not configured. "
            "Set the SETTINGS_ENCRYPTION_KEY environment variable."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> bytes:
    """Encrypt a plaintext string and return the Fernet token as bytes."""
    return _get_fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    """Decrypt a Fernet token and return the plaintext string."""
    return _get_fernet().decrypt(ciphertext).decode()


def hash_external_api_token(plaintext: str) -> str:
    """Return the sha256 hex digest of an external API token."""
    return hashlib.sha256(plaintext.encode()).hexdigest()
