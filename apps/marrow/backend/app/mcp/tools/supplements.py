from __future__ import annotations

import datetime
from typing import Any, Literal, Optional

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import select

from app.crud.supplement_catalog import SupplementCatalogCRUD
from app.mcp.observability import instrument_tool
from app.mcp.tools._common import _mcp_user_id, _parse_supplements, _validate_date
from app.models.entry import Entry
from app.models.supplement_catalog import SupplementCatalogItem
from app.schemas.entry import EntryUpdate
from app.services.entries import get_or_create_entry
from app.services.entry_orchestrator import EntryOrchestrator
from app.services.supplement_catalog import normalize_key
from app.utils.dates import local_today
from f0rge_core.exceptions import ValidationError
from f0rge_db.tenant import owned_by_user

SupplementMode = Literal["replace", "add", "remove"]
_MODES = ("replace", "add", "remove")


def _catalog_item_to_dict(item: SupplementCatalogItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "key": item.key,
        "label": item.label,
        "archived": item.archived,
        "sort_order": item.sort_order,
        "first_used_at": item.first_used_at.isoformat() if item.first_used_at else None,
        "last_used_at": item.last_used_at.isoformat() if item.last_used_at else None,
    }


def _normalize_keys(raw_keys: list[str]) -> list[str]:
    """Normalise and de-duplicate caller keys, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_keys:
        key = normalize_key(raw)
        if not key:
            raise ValidationError(f"Invalid supplement key {raw!r}; use a-z, 0-9 and underscores.")
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _compute_new_keys(mode: str, current: list[str], requested: list[str]) -> list[str]:
    if mode == "replace":
        # Same set in a different order is a no-op: keep the stored order.
        return current if set(requested) == set(current) else list(requested)
    if mode == "add":
        return current + [k for k in requested if k not in current]
    return [k for k in current if k not in requested]


def _validate_requested(
    mode: str,
    requested: list[str],
    current: list[str],
    catalog: dict[str, SupplementCatalogItem],
) -> None:
    valid = sorted(k for k, item in catalog.items() if not item.archived)
    # Keys already on the day may be legacy/archived (entries.supplements has no FK);
    # they stay removable/keepable, but cannot be newly introduced.
    unknown = [k for k in requested if k not in catalog and not (mode == "remove" and k in current)]
    if unknown:
        raise ValidationError(
            f"Unknown supplement key(s): {', '.join(unknown)}. "
            f"Valid keys: {', '.join(valid) if valid else '(none)'}."
        )
    if mode in ("add", "replace"):
        archived = [
            k for k in requested if k in catalog and catalog[k].archived and k not in current
        ]
        if archived:
            raise ValidationError(
                f"Archived supplement key(s) cannot be added: {', '.join(archived)}. "
                "Un-archive them in the Marrow app first."
            )


def register_supplements_tools(server: FastMCP) -> None:
    @server.tool()
    @instrument_tool("list_supplements")
    async def list_supplements(
        include_archived: bool = False, ctx: Context = None
    ) -> dict[str, Any]:
        """List your supplement catalog (keys to use with set_supplements), ordered by sort_order."""
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(user_id) as db:
            items = await SupplementCatalogCRUD(db).list(include_archived=include_archived)
            return {"supplements": [_catalog_item_to_dict(i) for i in items]}

    @server.tool()
    @instrument_tool("set_supplements")
    async def set_supplements(
        keys: list[str],
        date: Optional[str] = None,
        mode: SupplementMode = "replace",
        ctx: Context = None,
    ) -> dict[str, Any]:
        """Set which supplements you took on a day (date defaults to today, Europe/Luxembourg).

        mode: 'replace' (default) makes the day's list exactly `keys` (empty list clears it),
        'add' appends keys, 'remove' drops keys. Keys come from list_supplements; unknown keys
        are rejected and archived keys cannot be newly added. No-ops do not write.
        """
        if mode not in _MODES:
            raise ValidationError(f"mode must be one of: {', '.join(_MODES)}")
        parsed: datetime.date = _validate_date(date, "date") if date else local_today()
        requested = _normalize_keys(keys)
        user_id = _mcp_user_id(ctx)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_main_session(user_id) as db:
            catalog_items = await SupplementCatalogCRUD(db).list(include_archived=True)
            catalog = {i.key: i for i in catalog_items}

            # Lock the day row (if any) so a concurrent writer cannot interleave
            # between our read of the CSV and the update.
            locked = (
                await db.execute(
                    select(Entry)
                    .where(owned_by_user(Entry.user_id), Entry.date == parsed)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            previous = _parse_supplements(locked.supplements) if locked is not None else []

            _validate_requested(mode, requested, previous, catalog)
            new_keys = _compute_new_keys(mode, previous, requested)
            added = [k for k in new_keys if k not in previous]
            removed = [k for k in previous if k not in new_keys]

            if new_keys == previous:
                return {
                    "date": str(parsed),
                    "mode": mode,
                    "previous_supplements": previous,
                    "supplements": previous,
                    "added": [],
                    "removed": [],
                    "changed": False,
                    "created_day": False,
                }

            created_day = locked is None
            if created_day:
                await get_or_create_entry(db, parsed)
            response = await EntryOrchestrator(db).update_entry(
                parsed, EntryUpdate(supplements=",".join(new_keys))
            )
            return {
                "date": str(response.date),
                "mode": mode,
                "previous_supplements": previous,
                "supplements": _parse_supplements(response.supplements),
                "added": added,
                "removed": removed,
                "changed": True,
                "created_day": created_day,
            }
