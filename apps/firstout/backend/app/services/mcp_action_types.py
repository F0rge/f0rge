"""Types shared by the MCP action registry and its domain handlers."""

from __future__ import annotations

import inspect
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypeVar, get_type_hints

from fastapi import APIRouter
from fastapi.params import Depends
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, create_model
from pydantic_core import to_jsonable_python
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_token import McpToken
from app.schemas.page import PageParams


@dataclass(frozen=True)
class Action:
    name: str
    tab: str
    description: str
    arguments: type[BaseModel]
    # Empty allows any active staff member. Otherwise one listed permission is sufficient.
    permissions: tuple[str, ...]
    handler: Callable[[AsyncSession, McpToken, Any], Awaitable[dict]]
    effect: Literal["read", "write"] = "read"
    related_tabs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Fail closed at import rather than expose a loosely declared action.
        if self.effect == "write" and not self.permissions:
            raise ValueError(f"MCP write {self.name} must name a permission")
        if self.arguments.model_config.get("extra") != "forbid":
            raise ValueError(f"MCP action {self.name} arguments must forbid extra fields")


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


Endpoint = TypeVar("Endpoint", bound=Callable[..., Any])


def _endpoint_arguments(name: str, endpoint: Callable[..., Any]) -> type[BaseModel]:
    hints = get_type_hints(endpoint, include_extras=True)
    fields: dict[str, Any] = {}
    for param in inspect.signature(endpoint).parameters.values():
        if isinstance(param.default, Depends):
            continue
        # Only required UUID path/query parameters are derived. Bodies, optional filters and
        # Annotated parameters need a reviewed model.
        if hints.get(param.name) is not uuid.UUID or param.default is not param.empty:
            raise TypeError(
                f"MCP action {name} cannot derive '{param.name}'; pass a strict arguments= model"
            )
        fields[param.name] = (uuid.UUID, ...)
    return create_model(name.title().replace("_", "") + "Arguments", __base__=Arguments, **fields)


def mcp_action(
    name: str,
    tab: str,
    description: str,
    *,
    permissions: tuple[str, ...],
    handler: Callable[[AsyncSession, McpToken, Any], Awaitable[dict]],
    arguments: type[BaseModel] | None = None,
) -> Callable[[Endpoint], Endpoint]:
    """Mark an API endpoint as an MCP write.

    The endpoint is returned unchanged. MCP runs `handler`, not the endpoint, so the change
    stays in the transaction that saves its receipt and audit entry. Without `arguments`, they
    are derived from the endpoint's non-dependency parameters. The mark is inert until the
    endpoint's router is passed to `endpoint_actions` for the catalogue.
    """

    def mark(endpoint: Endpoint) -> Endpoint:
        action = Action(
            name=name,
            tab=tab,
            description=description,
            arguments=arguments or _endpoint_arguments(name, endpoint),
            permissions=permissions,
            handler=handler,
            effect="write",
        )
        setattr(endpoint, "mcp_action", action)
        return endpoint

    return mark


def endpoint_actions(router: APIRouter) -> tuple[Action, ...]:
    """Collect the marks on the router that declares the routes. A parent that only includes
    that router yields nothing."""
    marks = (
        getattr(getattr(route, "endpoint", None), "mcp_action", None) for route in router.routes
    )
    return tuple(action for action in marks if action is not None)


class PageArguments(Arguments):
    limit: int = Field(default=10, ge=1, le=25)
    offset: int = Field(default=0, ge=0, le=2_147_483_647)


SearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class FindRecords(PageArguments):
    query: SearchText | None = None

    def page(self) -> PageParams:
        return PageParams(q=self.query, limit=self.limit, offset=self.offset)


async def paged_rows(db: AsyncSession, statement: Select, args: PageArguments) -> dict:
    """Paginate at the database and encode fixed-point quantities as decimal strings."""
    result = await db.execute(statement.limit(args.limit + 1).offset(args.offset))
    rows = result.mappings().all()
    return {
        "items": [to_jsonable_python(dict(row)) for row in rows[: args.limit]],
        "next_offset": args.offset + args.limit if len(rows) > args.limit else None,
    }
