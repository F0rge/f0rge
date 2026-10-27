from __future__ import annotations

import logging
from typing import Optional

from app.exceptions import (
    CommsEncryptionUnconfiguredError,
    CommsSmtpFailedError,
    CommsSmtpUnconfiguredError,
)
from app.models.team_settings import TeamSettings
from app.services.comms.smtp import SmtpConfig, load_smtp_config, send_message

logger = logging.getLogger(__name__)


def mailbox_or_none(team_settings: TeamSettings) -> Optional[SmtpConfig]:
    try:
        return load_smtp_config(team_settings)
    except (CommsSmtpUnconfiguredError, CommsEncryptionUnconfiguredError):
        return None


async def deliver_plain_message(
    config: SmtpConfig,
    *,
    to: str,
    subject: str,
    body_text: str,
) -> None:
    try:
        await send_message(config, to=to, subject=subject, body_text=body_text)
    except (CommsSmtpFailedError, CommsSmtpUnconfiguredError, CommsEncryptionUnconfiguredError):
        logger.warning("plain email was not sent")
    except Exception:
        logger.warning("plain email was not sent")
