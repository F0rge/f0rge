"""Compact action discovery. Every action is registered and authorised by Firstout."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable

from fastapi import FastAPI

from app.config import settings
from app.services.mcp_action_types import Action, Arguments
from app.services.mcp_drafts import DRAFT_ACTIONS
from app.services.mcp_domains import READ_ACTIONS
from app.services.mcp_operations import lookup_operation
from app.services.mcp_routes import marked_actions, route_actions
from app.services.mcp_transfers import TRANSFER_ACTIONS


class OperationLookup(Arguments):
    request_id: uuid.UUID


async def _lookup(db, token, args: OperationLookup) -> dict:
    return await lookup_operation(db, token, args.request_id, actions=ACTIONS.values())


def catalogue(actions: Iterable[Action]) -> dict[str, Action]:
    by_name: dict[str, Action] = {}
    for action in actions:
        if action.name in by_name:
            raise ValueError(f"Duplicate MCP action name: {action.name}")
        by_name[action.name] = action
    return by_name


ACTIONS = catalogue(
    (
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
)


def register_route_actions(app: FastAPI) -> None:
    """Add the app's `mcp_action` marks, then one action per offered API route.

    Call once, after every router is included; until then the registry is incomplete.
    Marked names are reserved first so route names do not depend on registration order.
    """
    # A second call repeats every mark and route name, which the duplicate guard refuses.
    actions = catalogue((*ACTIONS.values(), *marked_actions(app)))
    hand_written = frozenset(name for name, action in actions.items() if action.route is None)
    ACTIONS.update(catalogue((*actions.values(), *route_actions(app, hand_written))))


def _permitted(granted: set[str]) -> list[Action]:
    return [
        action
        for action in ACTIONS.values()
        if (not action.permissions or not granted.isdisjoint(action.permissions))
        and (settings.mcp_writes_enabled or action.effect == "read")
    ]


def actions_index(granted: set[str]) -> str:
    """Every action these permissions allow, as one line each under its sidebar tab.

    Plain text costs a model fewer tokens than JSON's repeated keys and punctuation.
    """
    lines = ["Firstout actions you can run now. Call find_actions for an action's inputs."]
    tab = None
    for action in sorted(_permitted(granted), key=lambda item: (item.tab, item.name)):
        if action.tab != tab:
            tab = action.tab
            lines.append(f"\n## {tab}")
        lines.append(f"{action.name} ({action.effect}): {action.description}")
    return "\n".join(lines)


def _words(text: str) -> set[str]:
    return {word.removesuffix("s") for word in re.findall(r"[a-z0-9]+", text.casefold())}


# Staff words -> the catalogue's word for the same thing. A query term also matches its synonym.
SYNONYMS = {
    "product": "sku",
    "item": "sku",
    "close": "lock",
    "record": "create",
    "raise": "create",
    "add": "create",
    "new": "create",
    "vat": "vat201",
}


def search_actions(query: str, tab: str, granted: set[str], offset: int = 0) -> dict:
    permitted = _permitted(granted)
    if not query.strip() and not tab.strip():
        return {"domains": sorted({action.tab.split(" / ")[0] for action in permitted})}
    terms = _words(query) - {"a", "an", "the", "to", "and", "in", "my", "of", "for", "i"}
    terms |= {SYNONYMS[term] for term in terms if term in SYNONYMS}
    tab_terms = _words(tab)
    matches = []
    for action in permitted:
        areas = [_words(label) for label in (action.tab, *action.related_tabs)]
        if not any(tab_terms <= area for area in areas):
            continue
        name = _words(action.name)
        described = _words(action.description)
        if action.route is not None:
            # A route's method and path, and a summary made from its name, say nothing new.
            described -= name | _words(f"{action.route.method} {action.route.path}")
        score = (
            4 * len(terms & name)
            + 2 * max(len(terms & area) for area in areas)
            + len(terms & described)
        )
        if not terms or score:
            # On equal relevance a hand-written action ranks before the route it mirrors.
            matches.append((-score, action.route is not None, action.name, action))
    page = [
        {
            "name": action.name,
            "tab": action.tab,
            "description": action.description,
            "effect": action.effect,
            "inputSchema": action.arguments.model_json_schema(),
        }
        for *_, action in sorted(matches)[offset : offset + 3]
    ]
    return {"actions": page, "next_offset": offset + 3 if offset + 3 < len(matches) else None}
