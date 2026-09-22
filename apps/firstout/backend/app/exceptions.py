from __future__ import annotations

from f0rge_core.exceptions import DomainError


class ForbiddenError(DomainError):
    """Caller lacks a required permission. Mapped to HTTP 403."""


class NiaLlmUnconfiguredError(DomainError):
    """OpenRouter key missing. Mapped to HTTP 503 with code nia_llm_unconfigured."""

    def __init__(self) -> None:
        super().__init__("nia_llm_unconfigured")


class NiaCapExceededError(DomainError):
    """Monthly token cap reached or blocked (cap 0). Mapped to HTTP 429."""

    def __init__(self) -> None:
        super().__init__("nia_cap_exceeded")


class CommsEncryptionUnconfiguredError(DomainError):
    """SETTINGS_ENCRYPTION_KEY missing or invalid. Mapped to HTTP 503."""

    def __init__(self) -> None:
        super().__init__("comms_encryption_unconfigured")


class CommsSmtpUnconfiguredError(DomainError):
    """SMTP mailbox not saved. Mapped to HTTP 503."""

    def __init__(self) -> None:
        super().__init__("comms_smtp_unconfigured")


class CommsSmtpFailedError(DomainError):
    """SMTP provider rejected the send. Mapped to HTTP 502."""

    def __init__(self, message: str) -> None:
        super().__init__("comms_smtp_failed")
        self.message = message
