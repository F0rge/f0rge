"""APNs push delivery + device token registry (#391).

The sender is best-effort by design: any APNs failure is logged and swallowed
so the reminder loop keeps writing in-app notification rows (project rule —
delivery must never break the loop). Unconfigured APNs settings mean no
client is ever constructed and ``send_dose_reminder`` is a no-op.
"""

from __future__ import annotations

import logging
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.device_token import DeviceToken
from f0rge_core.exceptions import NotFoundError
from f0rge_db.tenant import current_user_id

logger = logging.getLogger(__name__)

_PRUNE_DESCRIPTIONS = ("Unregistered", "BadDeviceToken")

_client = None  # lazy singleton APNs client


def apns_configured() -> bool:
    return bool(settings.apns_key_id and settings.apns_team_id and settings.apns_private_key)


def _get_client():
    """Lazily build the aioapns client; ``None`` when APNs is unconfigured."""
    global _client
    if _client is None and apns_configured():
        from aioapns import APNs

        _client = APNs(
            key=settings.apns_private_key,
            key_id=settings.apns_key_id,
            team_id=settings.apns_team_id,
            topic=settings.apns_topic,
            use_sandbox=settings.apns_use_sandbox,
        )
    return _client


# ---------------------------------------------------------------------------
# Device token registry
# ---------------------------------------------------------------------------


async def register_device(db: AsyncSession, token: str, platform: str) -> DeviceToken:
    """Idempotently register ``token`` for the current user.

    Token takeover (the phone changed owners, e.g. Beatriz signs in on a
    device previously registered to Leo): the stale row belongs to another
    user and RLS hides it, so briefly assume the ``device_registrar`` service
    role to delete it before inserting our own row.
    """
    user_id = current_user_id()
    await db.execute(sa.text("SELECT set_config('app.service_role', 'device_registrar', true)"))
    try:
        await db.execute(
            sa.delete(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id != user_id)
        )
    finally:
        await db.execute(sa.text("SELECT set_config('app.service_role', '', true)"))
    await db.execute(
        pg_insert(DeviceToken)
        .values(user_id=user_id, token=token, platform=platform)
        .on_conflict_do_nothing(constraint="uq_device_tokens_token")
    )
    row = (
        await db.execute(
            sa.select(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id == user_id)
        )
    ).scalar_one()
    await db.commit()
    return row


async def unregister_device(db: AsyncSession, token: str) -> None:
    """Delete the current user's ``token`` row; another user's token is a 404."""
    # Explicit user scoping per repo convention (RLS is the backstop).
    result = await db.execute(
        sa.delete(DeviceToken).where(
            DeviceToken.token == token, DeviceToken.user_id == current_user_id()
        )
    )
    if result.rowcount == 0:
        raise NotFoundError("Device token not found")
    await db.commit()


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


async def send_dose_reminder(db: AsyncSession, user_id: uuid.UUID, payload: dict) -> None:
    """Push a dose reminder to every device of ``user_id``. Best-effort.

    Caller must hold the user's RLS GUC on ``db`` (the reminder tick does).
    ``payload`` is the in-app notification payload
    (treatment_id/treatment_name/slot/date).
    """
    client = _get_client()
    if client is None:
        return
    tokens = (
        (await db.execute(sa.select(DeviceToken.token).where(DeviceToken.user_id == user_id)))
        .scalars()
        .all()
    )
    if not tokens:
        return

    from aioapns import NotificationRequest, PushType

    message = {
        "aps": {
            "alert": {
                "title": "Dose reminder",
                "body": f"{payload['treatment_name']} — dose {payload['slot']}",
            },
            "sound": "default",
            "category": "DOSE_REMINDER",
        },
        "treatment_id": payload["treatment_id"],
        "slot": payload["slot"],
        "date": payload["date"],
    }
    for token in tokens:
        try:
            result = await client.send_notification(
                NotificationRequest(device_token=token, message=message, push_type=PushType.ALERT)
            )
        except Exception:
            logger.exception("APNs send failed for token %s…", token[:8])
            continue
        if result.status == "410" or result.description in _PRUNE_DESCRIPTIONS:
            await db.execute(
                sa.delete(DeviceToken).where(
                    DeviceToken.token == token, DeviceToken.user_id == user_id
                )
            )
            logger.info("Pruned dead device token %s… (%s)", token[:8], result.description)
