"""Types shared by the MCP action registry and its domain handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
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
    effect: Literal["read", "write", "review"] = "read"
    related_tabs: tuple[str, ...] = ()


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
