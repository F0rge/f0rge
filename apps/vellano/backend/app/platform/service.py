from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.platform.crud import TenantHostnameCRUD
from app.platform.models import Tenant, TENANT_STATUS_READY
from app.services.comms.secrets import decrypt, encrypt
from f0rge_core.exceptions import ValidationError

SLUG_PATTERN = re.compile(r"^[a-z0-9-]{3,32}$")
ROLE_DB_PATTERN = re.compile(r"^[a-z0-9_]{3,40}$")
RESERVED_SLUGS = frozenset(
    {
        "www",
        "api",
        "app",
        "admin",
        "mail",
        "platform",
        "vellano",
        "stockroom",
        "status",
        "docs",
    }
)
BLOCKED_EMAIL_TLDS = frozenset({"local", "localhost", "invalid", "internal", "lan"})


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
    if not SLUG_PATTERN.fullmatch(value) or value.startswith("-") or value.endswith("-"):
        raise ValidationError("Invalid slug")
    return value


def slug_availability_reason(slug: str) -> Optional[str]:
    try:
        value = validate_slug(slug)
    except ValidationError:
        return "invalid"
    if value in RESERVED_SLUGS:
        return "reserved"
    return None


def tenant_role_name(slug: str) -> str:
    name = f"tenant_{validate_slug(slug).replace('-', '_')}"
    if not ROLE_DB_PATTERN.fullmatch(name):
        raise ValidationError("Invalid slug")
    return name


def workspace_origin(slug: str) -> str:
    host = f"{validate_slug(slug)}.{settings.tenant_base_domain}"
    if settings.cookie_secure:
        return f"https://{host}"
    if settings.tenant_base_domain == "localhost":
        return f"http://{host}:3003"
    return f"http://{host}"


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
