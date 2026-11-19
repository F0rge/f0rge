from __future__ import annotations

import datetime
import uuid

from sqlalchemy import UUID, String, case, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import require_directory_tenant
from app.crud.mcp_token import activity_stream
from app.models.mcp_operation import McpOperation
from app.models.books_event import BooksEvent
from app.models.unit_cost_audit import UnitCostAudit
from app.models.user import User
from app.permissions import STOCK_COST_VIEW, USERS_MANAGE
from app.schemas.audit import AuditEventItem, AuditSource
from app.schemas.page import Page, PageParams
from app.services.permissions import PermissionService


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


class AuditHubService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_events(
        self, user_id: uuid.UUID, params: PageParams, source: AuditSource | None = None
    ) -> Page[AuditEventItem]:
        actor = func.coalesce(func.nullif(User.display_name, ""), User.email, "system").label(
            "actor"
        )
        team_id = require_directory_tenant()
        extra_columns = (
            cast(literal(None), String).label("origin"),
            cast(literal(None), UUID).label("token_id"),
            cast(literal(None), UUID).label("operation_id"),
        )
        books = (
            select(
                BooksEvent.id,
                BooksEvent.created_at.label("at"),
                literal("books").label("source"),
                actor,
                func.concat(BooksEvent.action, " ", BooksEvent.document_type).label("summary"),
                func.concat(
                    "/",
                    BooksEvent.document_type,
                    case(
                        (BooksEvent.document_type.in_(["payment", "journal"]), "s?record="),
                        else_="s/",
                    ),
                    BooksEvent.document_id,
                ).label("href"),
                *extra_columns,
            )
            .outerjoin(User, User.id == BooksEvent.actor_user_id)
            .where(BooksEvent.team_id == team_id)
        )
        queries = [books] if source in (None, "books") else []
        if source in (None, "cost") and await PermissionService(self.db).has_permission(
            user_id, STOCK_COST_VIEW
        ):
            queries.append(
                select(
                    UnitCostAudit.id,
                    UnitCostAudit.created_at.label("at"),
                    literal("cost").label("source"),
                    actor,
                    func.concat(UnitCostAudit.source, " unit cost").label("summary"),
                    func.concat("/catalogue/", UnitCostAudit.sku_id).label("href"),
                    *extra_columns,
                )
                .outerjoin(User, User.id == UnitCostAudit.changed_by_user_id)
                .where(UnitCostAudit.team_id == team_id)
            )
        if source in (None, "mcp"):
            manager = await PermissionService(self.db).has_permission(user_id, USERS_MANAGE)
            stream = activity_stream(team_id, None if manager else user_id)
            event = stream.c
            transfer_id = McpOperation.result["transfer_id"].as_string()
            document_id = McpOperation.result["id"].as_string()
            record_link = case(
                (transfer_id.is_not(None), literal("/transfers")),
                (
                    (event.action_name == "quotes_create_draft") & document_id.is_not(None),
                    literal("/quotes"),
                ),
                (
                    (event.action_name == "journals_create_draft") & document_id.is_not(None),
                    func.concat("/journals?record=", document_id),
                ),
            )
            activity = (
                select(
                    event.id,
                    event.occurred_at.label("at"),
                    literal("mcp").label("source"),
                    actor,
                    func.concat_ws(
                        " · ",
                        event.token_name,
                        func.replace(event.action, "_", " "),
                        func.replace(event.action_name, "_", " "),
                        func.coalesce(
                            McpOperation.result["transfer_number"].as_string(),
                            McpOperation.result["number"].as_string(),
                        ),
                        event.result,
                    ).label("summary"),
                    record_link.label("href"),
                    event.source.label("origin"),
                    event.token_id,
                    event.operation_id,
                )
                .select_from(stream)
                .outerjoin(User, User.id == event.user_id)
                .outerjoin(
                    McpOperation,
                    (McpOperation.id == event.operation_id)
                    & (McpOperation.team_id == event.team_id),
                )
            )
            queries.append(activity)
        if not queries:
            return Page(items=[], total=0)
        events = union_all(*queries).subquery()
        query = select(events)
        if params.q:
            query = query.where(
                or_(
                    *(
                        cast(column, String).icontains(params.q, autoescape=True)
                        for column in (
                            events.c.summary,
                            events.c.actor,
                            events.c.href,
                            events.c.operation_id,
                        )
                    )
                )
            )
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = (
            await self.db.execute(
                query.order_by(events.c.at.desc(), events.c.source, events.c.id)
                .offset(params.offset)
                .limit(params.limit)
            )
        ).mappings()
        return Page(
            items=[AuditEventItem(**{**row, "at": _as_utc(row["at"])}) for row in rows],
            total=total or 0,
        )
