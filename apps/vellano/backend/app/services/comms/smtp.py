from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Optional

from app.exceptions import CommsSmtpFailedError, CommsSmtpUnconfiguredError
from app.models.team_settings import TeamSettings
from app.services.comms.secrets import decrypt

SMTP_TIMEOUT_SECONDS = 10
_SMTP_SECURITIES = frozenset({"starttls", "ssl", "plain"})


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    security: str
    username: Optional[str]
    password: Optional[str]
    from_address: str
    from_name: Optional[str]
    reply_to: Optional[str]


def load_smtp_config(settings: TeamSettings) -> SmtpConfig:
    host = (settings.smtp_host or "").strip()
    from_address = (settings.smtp_from_address or "").strip()
    if not host or not from_address:
        raise CommsSmtpUnconfiguredError()
    security = settings.smtp_security or "starttls"
    if security not in _SMTP_SECURITIES:
        raise CommsSmtpUnconfiguredError()
    port = settings.smtp_port
    if port is None:
        port = 465 if security == "ssl" else 587
    password = None
    if settings.smtp_password_encrypted:
        password = decrypt(settings.smtp_password_encrypted)
    username = (settings.smtp_username or "").strip() or None
    from_name = (settings.smtp_from_name or "").strip() or None
    reply_to = (settings.smtp_reply_to or "").strip() or None
    return SmtpConfig(
        host=host,
        port=int(port),
        security=security,
        username=username,
        password=password,
        from_address=from_address,
        from_name=from_name,
        reply_to=reply_to,
    )


async def send_message(
    config: SmtpConfig,
    *,
    to: str,
    subject: str,
    body_text: str,
    pdf_bytes: Optional[bytes] = None,
    pdf_filename: Optional[str] = None,
) -> Optional[str]:
    try:
        return await asyncio.to_thread(
            _send_sync,
            config,
            to,
            subject,
            body_text,
            pdf_bytes,
            pdf_filename,
        )
    except CommsSmtpFailedError:
        raise
    except Exception as exc:
        raise CommsSmtpFailedError(_safe_smtp_message(exc)) from exc


def _send_sync(
    config: SmtpConfig,
    to: str,
    subject: str,
    body_text: str,
    pdf_bytes: Optional[bytes],
    pdf_filename: Optional[str],
) -> Optional[str]:
    message = EmailMessage()
    if config.from_name:
        message["From"] = formataddr((config.from_name, config.from_address))
    else:
        message["From"] = config.from_address
    message["To"] = to
    message["Subject"] = subject
    if config.reply_to:
        message["Reply-To"] = config.reply_to
    message["Message-ID"] = make_msgid()
    message.set_content(body_text)
    if pdf_bytes:
        message.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=pdf_filename or "document.pdf",
        )
    try:
        if config.security == "ssl":
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                config.host,
                config.port,
                timeout=SMTP_TIMEOUT_SECONDS,
                context=ssl.create_default_context(),
            )
        else:
            client = smtplib.SMTP(config.host, config.port, timeout=SMTP_TIMEOUT_SECONDS)
        with client:
            if config.security == "starttls":
                client.ehlo()
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            if config.username:
                client.login(config.username, config.password or "")
            client.send_message(message)
    except smtplib.SMTPException as exc:
        raise CommsSmtpFailedError(_safe_smtp_message(exc)) from exc
    return message["Message-ID"]


def _safe_smtp_message(exc: BaseException) -> str:
    text = str(exc).replace("\n", " ").strip() or exc.__class__.__name__
    return text[:500]
