"""Compact action discovery. Every action is registered and authorised by Firstout."""

from __future__ import annotations

import re
import uuid

from app.config import settings
from app.services.mcp_action_types import Action, Arguments
from app.services.mcp_drafts import DRAFT_ACTIONS
from app.services.mcp_domains import READ_ACTIONS
from app.services.mcp_operations import lookup_operation
from app.services.mcp_transfers import TRANSFER_ACTIONS


class OperationLookup(Arguments):
    request_id: uuid.UUID


async def _lookup(db, token, args: OperationLookup) -> dict:
    return await lookup_operation(db, token, args.request_id, actions=ACTIONS.values())


ACTIONS = {
    action.name: action
    for action in (
        *READ_ACTIONS,
        *DRAFT_ACTIONS,
        *TRANSFER_ACTIONS,
        Action(
            name="operations_lookup",
            tab="Admin / MCP tokens",
            description="Look up a write receipt by request ID, including whether an earlier request was executed.",
            arguments=OperationLookup,
            permissions=(),
            handler=_lookup,
        ),
    )
}


def _words(text: str) -> set[str]:
    return {word.removesuffix("s") for word in re.findall(r"[a-z0-9]+", text.casefold())}


def search_actions(query: str, tab: str, granted: set[str], offset: int = 0) -> dict:
    permitted = [
        action
        for action in ACTIONS.values()
        if (not action.permissions or not granted.isdisjoint(action.permissions))
        and (settings.mcp_writes_enabled or action.effect == "read")
    ]
    if not query.strip() and not tab.strip():
        return {"domains": sorted({action.tab.split(" / ")[0] for action in permitted})}
    terms = _words(query) - {"a", "an", "the", "to", "and", "in", "my", "of", "for", "i"}
    tab_terms = _words(tab)
    matches = []
    for action in permitted:
        areas = [_words(label) for label in (action.tab, *action.related_tabs)]
        if not any(tab_terms <= area for area in areas):
            continue
        name = _words(action.name)
        score = (
            4 * len(terms & name)
            + 2 * max(len(terms & area) for area in areas)
            + len(terms & _words(action.description))
        )
        if not terms or score:
            matches.append((-score, action.name, action))
    page = [
        {
            "name": action.name,
            "tab": action.tab,
            "description": action.description,
            "effect": action.effect,
            "inputSchema": action.arguments.model_json_schema(),
        }
        for _, _, action in sorted(matches)[offset : offset + 3]
    ]
    return {"actions": page, "next_offset": offset + 3 if offset + 3 < len(matches) else None}
