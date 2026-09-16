from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.crud import TenantHostnameCRUD
from app.platform.models import Tenant, TENANT_STATUS_READY
from app.services.comms.secrets import decrypt, encrypt
from f0rge_core.exceptions import ValidationError

SLUG_PATTERN = re.compile(r"^[a-z0-9-]{3,32}$")


def normalise_hostname(raw: str) -> str:
    value = (raw or "").strip().lower().rstrip(".")
    if ":" in value:
        host, port = value.rsplit(":", 1)
        if port.isdigit():
            value = host
    if not value or value == "*" or "/" in value or " " in value:
        raise ValidationError("Invalid hostname")
    return value


def validate_slug(slug: str) -> str:
    value = (slug or "").strip().lower()
    if not SLUG_PATTERN.fullmatch(value):
        raise ValidationError("Invalid slug")
    return value


def encrypt_database_url(url: str) -> str:
    return encrypt(url).decode("ascii")


def decrypt_database_url(ciphertext: str) -> str:
    return decrypt(ciphertext.encode("ascii"))


async def resolve_tenant_by_hostname(db: AsyncSession, hostname: str) -> Optional[Tenant]:
    row = await TenantHostnameCRUD(db).get_by_hostname(normalise_hostname(hostname))
    if row is None or row.tenant is None:
        return None
    if row.tenant.status != TENANT_STATUS_READY:
        return None
    return row.tenant
