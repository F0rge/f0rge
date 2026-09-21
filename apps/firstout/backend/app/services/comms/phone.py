from __future__ import annotations

import re
from typing import Optional

_NON_DIGIT = re.compile(r"\D+")


def to_whatsapp_e164(raw: Optional[str], default_region: str = "ZA") -> Optional[str]:
    """Return +27 mobile E.164, or None for landlines / invalid values."""
    if not raw or default_region != "ZA":
        return None
    compact = raw.strip()
    if not compact:
        return None
    plus = compact.startswith("+")
    digits = _NON_DIGIT.sub("", compact)
    if not digits:
        return None
    national = _za_national_mobile(digits, had_plus=plus)
    if national is None:
        return None
    return f"+27{national}"


def _za_national_mobile(digits: str, *, had_plus: bool) -> Optional[str]:
    if digits.startswith("0027"):
        rest = digits[4:]
    elif digits.startswith("27") and len(digits) >= 11:
        rest = digits[2:]
    elif digits.startswith("0") and len(digits) == 10:
        rest = digits[1:]
    elif len(digits) == 9:
        rest = digits
    else:
        return None
    if len(rest) != 9 or not rest.isdigit():
        return None
    if rest.startswith("80"):
        return None
    if rest[0] not in {"6", "7", "8"}:
        return None
    if had_plus and not digits.startswith("27") and not digits.startswith("0027"):
        return None
    return rest
