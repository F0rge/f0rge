from __future__ import annotations

import datetime
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import unit_of_work
from app.crud.groups import GroupCRUD
from app.crud.social import SocialCRUD
from app.models.group import Group, GroupMember
from app.models.user import User
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from app.schemas.social import (
    GroupCreate,
    GroupDetailResponse,
    GroupInviteRequest,
    GroupListItem,
    GroupListResponse,
    GroupMemberItem,
    GroupRename,
    PublicUserCard,
)
from app.services.notifications import NotificationService
from app.services.social import SocialService
from f0rge_db.tenant import current_user_id


class GroupService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = GroupCRUD(db)
        self.social_crud = SocialCRUD(db)

    def _to_list_item(
        self,
        group: Group,
        membership: GroupMember,
        owner: User,
        member_count: int,
    ) -> GroupListItem:
        return GroupListItem(
            id=group.id,
            name=group.name,
            owner=SocialService.to_public_card(owner),
            member_count=member_count,
            my_status=membership.status,
            my_role=membership.role,
        )

    def _to_member_item(self, member: GroupMember, user: User) -> GroupMemberItem:
        return GroupMemberItem(
            handle=user.handle or "",
            display_name=user.display_name,
            avatar_default_index=user.avatar_default_index,
            role=member.role,
            status=member.status,
            joined_at=member.joined_at,
        )

    async def create_group(self, body: GroupCreate) -> GroupListItem:
        me = current_user_id()
        now = datetime.datetime.utcnow()
        group = Group(name=body.name.strip(), owner_id=me)
        owner_member = GroupMember(
            user_id=me,
            role="owner",
            status="joined",
            joined_at=now,
        )

        async with unit_of_work(self.db):
            group = await self.crud.add_group(group)
            owner_member.group_id = group.id
            owner_member = await self.crud.add_member(owner_member)

        owner = await self.social_crud.get_by_id(me)
        return self._to_list_item(group, owner_member, owner, member_count=1)

    async def list_groups(self) -> GroupListResponse:
        rows = await self.crud.list_my_groups()
        counts = await self.crud.count_joined_members([group.id for group, _, _ in rows])
        items = [
            self._to_list_item(group, membership, owner, counts.get(group.id, 0))
            for group, membership, owner in rows
        ]
        return GroupListResponse(groups=items)

    async def get_group(self, group_id: uuid.UUID) -> GroupDetailResponse:
        group = await self.crud.get_group_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")
        membership = await self.crud.get_my_membership(group_id)
        if membership is None:
            raise NotFoundError("Group not found")

        owner = await self.social_crud.get_by_id(group.owner_id)
        members = await self.crud.list_members_with_users(group_id)
        joined_count = sum(1 for member, _ in members if member.status == "joined")

        return GroupDetailResponse(
            id=group.id,
            name=group.name,
            owner=SocialService.to_public_card(owner)
            if owner
            else PublicUserCard(handle="", avatar_default_index=0),
            member_count=joined_count,
            my_status=membership.status,
            my_role=membership.role,
            members=[self._to_member_item(member, user) for member, user in members],
        )

    async def rename_group(self, group_id: uuid.UUID, body: GroupRename) -> GroupListItem:
        group = await self.crud.get_group_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")
        membership = await self.crud.get_my_membership(group_id)
        if membership is None or membership.role != "owner":
            raise ValidationError("Only the owner can rename")

        group.name = body.name.strip()
        owner = await self.social_crud.get_by_id(group.owner_id)
        counts = await self.crud.count_joined_members([group_id])

        async with unit_of_work(self.db):
            await self.crud.flush()

        return self._to_list_item(
            group,
            membership,
            owner,
            counts.get(group_id, 0),
        )

    async def delete_group(self, group_id: uuid.UUID) -> None:
        group = await self.crud.get_group_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")
        membership = await self.crud.get_my_membership(group_id)
        if membership is None or membership.role != "owner":
            raise ValidationError("Only the owner can delete the group")

        async with unit_of_work(self.db):
            await self.crud.delete_group(group)

    async def invite_to_group(
        self,
        group_id: uuid.UUID,
        body: GroupInviteRequest,
        social: SocialService,
        notifications: NotificationService,
    ) -> GroupMemberItem:
        me = current_user_id()
        group = await self.crud.get_group_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")

        my_membership = await self.crud.get_my_membership(group_id)
        if my_membership is None or my_membership.status != "joined":
            raise ValidationError("Only joined members can invite")

        invitee = await self.social_crud.get_by_handle(body.handle)
        if invitee is None or invitee.handle is None:
            raise NotFoundError("No user with that handle")
        if invitee.id == me:
            raise ValidationError("You can't invite yourself")

        await social.assert_connected(invitee.id)

        existing = await self.crud.get_membership_for_user(group_id, invitee.id)
        if existing is not None:
            if existing.status == "invited":
                raise ConflictError("Already invited")
            raise ConflictError("Already a member")

        member = GroupMember(
            group_id=group_id,
            user_id=invitee.id,
            role="member",
            status="invited",
            invited_by=me,
        )
        inviter = await self.social_crud.get_by_id(me)

        async with unit_of_work(self.db):
            try:
                member = await self.crud.add_member(member)
            except IntegrityError as exc:
                raise ConflictError("Already invited") from exc
            await notifications.notify(
                invitee.id,
                "group_invite",
                {
                    "group_id": str(group_id),
                    "group_name": group.name,
                    "handle": inviter.handle if inviter else "",
                },
            )

        return self._to_member_item(member, invitee)

    async def accept_group_invite(
        self,
        group_id: uuid.UUID,
        notifications: NotificationService,
    ) -> GroupMemberItem:
        me = current_user_id()
        group = await self.crud.get_group_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")

        membership = await self.crud.get_my_membership(group_id)
        if membership is None or membership.status != "invited":
            raise ValidationError("No pending invite for this group")

        membership.status = "joined"
        membership.joined_at = datetime.datetime.utcnow()
        me_user = await self.social_crud.get_by_id(me)

        async with unit_of_work(self.db):
            await self.crud.flush()
            await notifications.notify(
                group.owner_id,
                "group_invite_accepted",
                {
                    "group_id": str(group_id),
                    "group_name": group.name,
                    "handle": me_user.handle if me_user else "",
                },
            )

        return self._to_member_item(membership, me_user)

    async def remove_member(self, group_id: uuid.UUID, handle: str) -> None:
        me = current_user_id()
        group = await self.crud.get_group_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")

        target = await self.social_crud.get_by_handle(handle)
        if target is None or target.handle is None:
            raise NotFoundError("No user with that handle")

        target_membership = await self.crud.get_membership_for_user(group_id, target.id)
        if target_membership is None:
            raise NotFoundError("Member not found")

        my_membership = await self.crud.get_my_membership(group_id)
        if my_membership is None:
            raise NotFoundError("Group not found")

        if target.id == me:
            if my_membership.role == "owner":
                raise ValidationError("Transfer or delete the group instead")
            async with unit_of_work(self.db):
                await self.crud.delete_member(target_membership)
            return

        if my_membership.role != "owner":
            raise ValidationError("Only the owner can remove members")

        async with unit_of_work(self.db):
            await self.crud.delete_member(target_membership)
