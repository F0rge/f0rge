"""WhatsApp Cloud API helpers: signature verify and webhook (Graph send is later)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.exceptions import ForbiddenError
from app.models.team_settings import TeamSettings
from app.services.comms.outbox import CommsOutboxService
from app.services.comms.secrets import decrypt
from f0rge_core.exceptions import ValidationError


def whatsapp_mode(row: TeamSettings) -> str:
    phone = (row.wa_phone_number_id or "").strip()
    if phone and row.wa_access_token_encrypted:
        return "cloud"
    return "click"


def wa_configured(row: TeamSettings) -> bool:
    return whatsapp_mode(row) == "cloud"


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
