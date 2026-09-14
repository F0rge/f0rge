"""WhatsApp Cloud API helpers: signature verify, webhook, and Graph send."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.exceptions import ForbiddenError
from app.models.team_settings import TeamSettings
from app.services.comms.outbox import CommsOutboxService
from app.services.comms.secrets import decrypt
from f0rge_core.exceptions import ConflictError, ExternalServiceError, ValidationError

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
GRAPH_TIMEOUT = 20.0


@dataclass(frozen=True)
class WhatsAppCloudConfig:
    phone_number_id: str
    access_token: str
    template_name: str
    template_lang: str


def whatsapp_mode(row: TeamSettings) -> str:
    phone = (row.wa_phone_number_id or "").strip()
    if phone and row.wa_access_token_encrypted:
        return "cloud"
    return "click"


def wa_configured(row: TeamSettings) -> bool:
    return whatsapp_mode(row) == "cloud"


def load_whatsapp_cloud(row: TeamSettings) -> WhatsAppCloudConfig:
    if not wa_configured(row):
        raise ConflictError("WhatsApp Cloud API is not connected")
    template = (row.wa_invoice_template_name or "").strip()
    if not template:
        raise ConflictError("WhatsApp template name is not configured")
    token = decrypt(row.wa_access_token_encrypted) if row.wa_access_token_encrypted else ""
    if not token:
        raise ConflictError("WhatsApp Cloud API is not connected")
    return WhatsAppCloudConfig(
        phone_number_id=(row.wa_phone_number_id or "").strip(),
        access_token=token,
        template_name=template,
        template_lang=(row.wa_template_lang or "en").strip() or "en",
    )


def verify_signature(app_secret: str, raw_body: bytes, header: Optional[str]) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], digest)


def verify_subscribe_challenge(
    mode: Optional[str],
    token: Optional[str],
    challenge: Optional[str],
) -> str:
    expected = settings.wa_verify_token
    if (mode or "") != "subscribe" or not expected or token != expected:
        raise ForbiddenError("WhatsApp webhook verify failed")
    if not challenge:
        raise ValidationError("hub.challenge is required")
    return challenge


async def send_cloud_document(
    config: WhatsAppCloudConfig,
    *,
    to_e164: str,
    body_params: list[str],
    pdf_bytes: bytes,
    pdf_filename: str,
    caption: str,
) -> str:
    to = to_e164.lstrip("+")
    headers = {"Authorization": f"Bearer {config.access_token}"}
    messages_url = f"{GRAPH_BASE}/{config.phone_number_id}/messages"
    media_url = f"{GRAPH_BASE}/{config.phone_number_id}/media"
    try:
        async with httpx.AsyncClient(timeout=GRAPH_TIMEOUT) as client:
            template_resp = await client.post(
                messages_url,
                headers=headers,
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "template",
                    "template": {
                        "name": config.template_name,
                        "language": {"code": config.template_lang},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {"type": "text", "text": value} for value in body_params
                                ],
                            }
                        ],
                    },
                },
            )
            _raise_graph(template_resp)
            media_resp = await client.post(
                media_url,
                headers=headers,
                files={
                    "file": (pdf_filename, pdf_bytes, "application/pdf"),
                    "type": (None, "application/pdf"),
                    "messaging_product": (None, "whatsapp"),
                },
            )
            _raise_graph(media_resp)
            media_id = str((media_resp.json() or {}).get("id") or "")
            if not media_id:
                raise ExternalServiceError("WhatsApp media upload returned no id")
            document_resp = await client.post(
                messages_url,
                headers=headers,
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "document",
                    "document": {
                        "id": media_id,
                        "filename": pdf_filename,
                        "caption": caption,
                    },
                },
            )
            _raise_graph(document_resp)
    except httpx.HTTPError as exc:
        raise ExternalServiceError("WhatsApp Cloud API unreachable") from exc
    return _message_id(document_resp) or _message_id(template_resp)


def _message_id(response: httpx.Response) -> str:
    payload = response.json() if response.content else {}
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if messages and isinstance(messages, list) and isinstance(messages[0], dict):
        return str(messages[0].get("id") or "")
    return ""


def _raise_graph(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    message = "WhatsApp Cloud API request failed"
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            message = str(error.get("message") or message)
    except ValueError:
        if response.text:
            message = response.text[:500]
    if 400 <= response.status_code < 500:
        raise ConflictError(message)
    raise ExternalServiceError(message)


class WhatsAppWebhookService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings_crud = TeamSettingsCRUD(db)
        self.team_crud = TeamCRUD(db)
        self.outbox = CommsOutboxService(db)

    def verify_challenge(
        self,
        mode: Optional[str],
        token: Optional[str],
        challenge: Optional[str],
    ) -> str:
        return verify_subscribe_challenge(mode, token, challenge)

    async def handle_post(self, raw_body: bytes, signature: Optional[str]) -> None:
        row = await self._team_settings()
        if row is not None and row.wa_app_secret_encrypted:
            secret = decrypt(row.wa_app_secret_encrypted)
            if not verify_signature(secret, raw_body, signature):
                raise ForbiddenError("WhatsApp webhook signature invalid")
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Invalid WhatsApp webhook body") from exc
        if not isinstance(payload, dict):
            return
        for message_id, status, error in _status_events(payload):
            await self.outbox.apply_provider_status(message_id, status, error)

    async def _team_settings(self) -> Optional[TeamSettings]:
        team = await self.team_crud.get_first()
        if team is None:
            return None
        return await self.settings_crud.get_by_team_id(team.id)


def _status_events(payload: dict) -> list[tuple[str, str, Optional[str]]]:
    events: list[tuple[str, str, Optional[str]]] = []
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            for item in value.get("statuses") or []:
                if not isinstance(item, dict):
                    continue
                message_id = item.get("id")
                status = item.get("status")
                if not message_id or not status:
                    continue
                error = None
                errors = item.get("errors") or []
                if errors and isinstance(errors[0], dict):
                    error = str(errors[0].get("title") or errors[0].get("message") or "")
                events.append((str(message_id), str(status), error or None))
    return events
