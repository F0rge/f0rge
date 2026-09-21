from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.books_event import BooksEventCRUD
from app.crud.nia_audit import NiaAuditCRUD
from app.crud.unit_cost_audit import UnitCostAuditCRUD
from app.crud.user import UserCRUD
from app.models.books_event import BooksDocumentType
from app.models.user import User
from app.permissions import NIA_ADMIN, STOCK_COST_VIEW, USERS_MANAGE
from app.schemas.audit import AuditEventItem
from app.schemas.page import Page, PageParams
from app.services.permissions import PermissionService


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


class AuditHubService:
    _BOOKS_HREF: dict[BooksDocumentType, str] = {
        BooksDocumentType.INVOICE: "/invoices",
        BooksDocumentType.BILL: "/bills",
        BooksDocumentType.PAYMENT: "/payments",
        BooksDocumentType.JOURNAL: "/journals",
    }

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.books_crud = BooksEventCRUD(db)
        self.nia_crud = NiaAuditCRUD(db)
        self.cost_crud = UnitCostAuditCRUD(db)
        self.user_crud = UserCRUD(db)
        self.permissions = PermissionService(db)

    async def list_events(self, user_id: uuid.UUID, params: PageParams) -> Page[AuditEventItem]:
        include_nia = await self.permissions.has_any(user_id, (NIA_ADMIN, USERS_MANAGE))
        include_cost = await self.permissions.has_permission(user_id, STOCK_COST_VIEW)

        total = await self.books_crud.count_all()
        if include_nia:
            total += await self.nia_crud.count_all()
        if include_cost:
            total += await self.cost_crud.count_all()

        fetch_limit = params.offset + params.limit
        merged: list[AuditEventItem] = []
        merged.extend(await self._books_items(fetch_limit))
        if include_nia:
            merged.extend(await self._nia_items(fetch_limit))
        if include_cost:
            merged.extend(await self._cost_items(fetch_limit))

        merged.sort(key=lambda item: item.at, reverse=True)
        page = merged[params.offset : params.offset + params.limit]
        return Page(items=page, total=total)

    async def _books_items(self, limit: int) -> list[AuditEventItem]:
        rows = await self.books_crud.list_newest(limit)
        actor_cache: dict[uuid.UUID, str] = {}
        items: list[AuditEventItem] = []
        for row in rows:
            items.append(
                AuditEventItem(
                    at=_as_utc(row.created_at),
                    source="books",
                    actor=await self._actor(row.actor_user_id, actor_cache),
                    summary=f"{row.action.value} {row.document_type.value}",
                    href=f"{self._BOOKS_HREF[row.document_type]}/{row.document_id}",
                )
            )
        return items

    async def _nia_items(self, limit: int) -> list[AuditEventItem]:
        rows = await self.nia_crud.list_newest(limit)
        items: list[AuditEventItem] = []
        for row in rows:
            items.append(
                AuditEventItem(
                    at=_as_utc(row.created_at),
                    source="nia",
                    actor=self._user_label(row.user),
                    summary=f"Nia {row.tool_name} {row.decision}",
                    href="/",
                )
            )
        return items

    async def _cost_items(self, limit: int) -> list[AuditEventItem]:
        rows = await self.cost_crud.list_newest(limit)
        items: list[AuditEventItem] = []
        for row in rows:
            items.append(
                AuditEventItem(
                    at=_as_utc(row.created_at),
                    source="cost",
                    actor=self._user_label(row.changed_by),
                    summary=f"{row.source.value} unit cost",
                    href=f"/catalogue/{row.sku_id}",
                )
            )
        return items

    async def _actor(
        self,
        user_id: Optional[uuid.UUID],
        cache: dict[uuid.UUID, str],
    ) -> str:
        if user_id is None:
            return "system"
        if user_id in cache:
            return cache[user_id]
        user = await self.user_crud.get_by_id(user_id)
        label = self._user_label(user)
        cache[user_id] = label
        return label

    @staticmethod
    def _user_label(user: Optional[User]) -> str:
        if user is None:
            return "system"
        if user.display_name:
            return user.display_name
        return user.email
