from __future__ import annotations

import datetime
import uuid

from sqlalchemy import String, case, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.books_event import BooksEvent
from app.models.unit_cost_audit import UnitCostAudit
from app.models.user import User
from app.permissions import STOCK_COST_VIEW
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
        books = select(
            BooksEvent.id,
            BooksEvent.created_at.label("at"),
            literal("books").label("source"),
            actor,
            func.concat(BooksEvent.action, " ", BooksEvent.document_type).label("summary"),
            func.concat(
                "/",
                BooksEvent.document_type,
                case(
                    (BooksEvent.document_type.in_(["payment", "journal"]), "s?record="), else_="s/"
                ),
                BooksEvent.document_id,
            ).label("href"),
        ).outerjoin(User, User.id == BooksEvent.actor_user_id)
        queries = [books] if source != "cost" else []
        if source != "books" and await PermissionService(self.db).has_permission(
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
                ).outerjoin(User, User.id == UnitCostAudit.changed_by_user_id)
            )
        if not queries:
            return Page(items=[], total=0)
        events = union_all(*queries).subquery()
        query = select(events)
        if params.q:
            query = query.where(
                or_(
                    *(
                        cast(column, String).icontains(params.q, autoescape=True)
                        for column in (events.c.summary, events.c.actor, events.c.href)
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
