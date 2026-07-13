from __future__ import annotations

import datetime
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import unit_of_work
from app.crud.social import SocialCRUD, _pair_ids
from app.models.connection import Connection
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from app.schemas.social import (
    ConnectionItem,
    ConnectionListResponse,
    PublicUserCard,
    validate_handle_format,
)
from app.services.notifications import NotificationService
from f0rge_db.tenant import current_user_id


class SocialService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SocialCRUD(db)

    @staticmethod
    def to_public_card(user) -> PublicUserCard:
        return PublicUserCard(
            handle=user.handle or "",
            display_name=user.display_name,
            avatar_default_index=user.avatar_default_index,
        )

    async def check_handle_available(self, handle: str) -> bool:
        try:
            normalized = validate_handle_format(handle)
        except Exception:
            return False
        return not await self.crud.is_handle_taken(normalized)

    async def lookup_by_handle(self, handle: str) -> PublicUserCard:
        user = await self.crud.get_by_handle(handle)
        if user is None or user.handle is None:
            raise NotFoundError("No user with that handle")
        return self.to_public_card(user)

    async def assert_handle_available(
        self, handle: str, exclude_user_id: uuid.UUID | None = None
    ) -> str:
        normalized = validate_handle_format(handle)
        existing = await self.crud.get_by_handle(normalized)
        if existing is not None and (exclude_user_id is None or existing.id != exclude_user_id):
            raise ConflictError("Handle already taken")
        return normalized

    async def set_user_handle(self, user, handle: str):
        normalized = await self.assert_handle_available(handle, exclude_user_id=user.id)
        user.handle = normalized
        try:
            return await self.crud.commit_refresh(user)
        except IntegrityError as exc:
            raise ConflictError("Handle already taken") from exc

    async def assert_connected(self, other_user_id: uuid.UUID) -> None:
        row = await self.crud.get_accepted_connection(other_user_id)
        if row is None:
            raise ValidationError("You can only do this with connected users")

    async def list_connections(self) -> ConnectionListResponse:
        me = current_user_id()
        accepted: list[ConnectionItem] = []
        pending_incoming: list[ConnectionItem] = []
        pending_outgoing: list[ConnectionItem] = []

        for connection, other in await self.crud.list_connections_for_user():
            item = ConnectionItem(
                id=connection.id,
                user=self.to_public_card(other),
                since=connection.responded_at,
                created_at=connection.created_at,
            )
            if connection.status == "accepted":
                accepted.append(item)
            elif connection.requester_id == me:
                pending_outgoing.append(item)
            else:
                pending_incoming.append(item)

        return ConnectionListResponse(
            accepted=accepted,
            pending_incoming=pending_incoming,
            pending_outgoing=pending_outgoing,
        )

    async def send_connection_request(
        self, handle: str, notifications: NotificationService
    ) -> ConnectionItem:
        me = current_user_id()
        target = await self.crud.get_by_handle(handle)
        if target is None or target.handle is None:
            raise NotFoundError("No user with that handle")
        if target.id == me:
            raise ValidationError("You can't connect with yourself")

        existing = await self.crud.get_connection_by_pair(me, target.id)
        if existing is not None:
            if existing.status == "pending":
                raise ConflictError("Request already pending")
            raise ConflictError("Already connected")

        low, high = _pair_ids(me, target.id)
        connection = Connection(
            user_low=low,
            user_high=high,
            requester_id=me,
            status="pending",
        )

        sender = await self.crud.get_by_id(me)
        async with unit_of_work(self.db):
            try:
                connection = await self.crud.add_connection(connection)
            except IntegrityError as exc:
                raise ConflictError("Request already pending") from exc
            await notifications.notify(
                target.id,
                "connection_request",
                {
                    "handle": sender.handle if sender else "",
                    "display_name": sender.display_name if sender else None,
                    "connection_id": str(connection.id),
                },
            )

        return ConnectionItem(
            id=connection.id,
            user=self.to_public_card(target),
            created_at=connection.created_at,
        )

    async def accept_connection(
        self, connection_id: uuid.UUID, notifications: NotificationService
    ) -> ConnectionItem:
        me = current_user_id()
        connection = await self.crud.get_connection_by_id(connection_id)
        if connection is None:
            raise NotFoundError("Connection not found")
        if connection.status != "pending":
            raise ConflictError("Connection is not pending")
        if connection.requester_id == me:
            raise ValidationError("Only the recipient can accept")

        connection.status = "accepted"
        connection.responded_at = datetime.datetime.utcnow()
        requester = await self.crud.get_by_id(connection.requester_id)
        me_user = await self.crud.get_by_id(me)

        async with unit_of_work(self.db):
            await self.crud.flush()
            await notifications.mark_resolved(
                "connection_request", "connection_id", str(connection.id)
            )
            await notifications.notify(
                connection.requester_id,
                "connection_accepted",
                {
                    "handle": me_user.handle if me_user else "",
                    "display_name": me_user.display_name if me_user else None,
                    "connection_id": str(connection.id),
                },
            )

        return ConnectionItem(
            id=connection.id,
            user=self.to_public_card(requester)
            if requester
            else PublicUserCard(handle="", avatar_default_index=0),
            since=connection.responded_at,
        )

    async def delete_connection(self, connection_id: uuid.UUID) -> None:
        from app.services.meal_tags import MealTagService

        connection = await self.crud.get_connection_by_id(connection_id)
        if connection is None:
            raise NotFoundError("Connection not found")
        me = current_user_id()
        other = connection.user_high if connection.user_low == me else connection.user_low
        async with unit_of_work(self.db):
            await MealTagService(self.db).cancel_pending_for_connection(me, other)
            await self.crud.delete_connection(connection)
