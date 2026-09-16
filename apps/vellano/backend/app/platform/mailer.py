from __future__ import annotations

import logging

from app.config import settings
from app.services.comms.smtp import SmtpConfig, send_message

logger = logging.getLogger(__name__)


def verify_url(token: str) -> str:
    base = settings.landing_base_url.rstrip("/")
    return f"{base}/verify?token={token}"


async def send_verify_email(*, to: str, token: str) -> None:
    url = verify_url(token)
    if settings.platform_mail_mode == "log" or not settings.platform_smtp_host:
        logger.info("platform verify link for %s: %s", to, url)
        return
    config = SmtpConfig(
        host=settings.platform_smtp_host,
        port=settings.platform_smtp_port,
        security="starttls" if settings.platform_smtp_use_tls else "plain",
        username=settings.platform_smtp_username or None,
        password=settings.platform_smtp_password or None,
        from_address=settings.platform_smtp_from_email,
        from_name=settings.platform_smtp_from_name or None,
        reply_to=None,
    )
    await send_message(
        config,
        to=to,
        subject="Verify your Stockroom workspace",
        body_text=f"Confirm your email to finish creating your company:\n\n{url}\n",
    )
