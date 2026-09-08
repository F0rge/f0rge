from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.role import RoleCRUD
from app.models.role import Role, RolePermission
from app.permissions import (
    PERMISSION_CATALOG,
    ROLE_PRESET_NAMES,
    ROLE_PRESETS,
    SYSTEM_ROLE_SLUGS,
    SLUG_OWNER,
    slugify_role_name,
    validate_permission_keys,
)
from app.schemas.role import RoleCreate, RoleResponse, RoleUpdate
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class RoleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = RoleCRUD(db)

    async def list(self) -> list[RoleResponse]:
        return [self._to_response(role) for role in await self.crud.list_all()]

    async def create(self, data: RoleCreate) -> RoleResponse:
        try:
            keys = validate_permission_keys(data.permissions)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        slug = await self._unique_slug(data.name)
        role = Role(
            slug=slug,
            name=data.name.strip(),
            is_system=False,
            is_owner_preset=False,
            permissions=[RolePermission(key=key) for key in keys],
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(role)
        reloaded = await self.crud.get_by_id(role.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def update(self, role_id: uuid.UUID, data: RoleUpdate) -> RoleResponse:
        role = await self.crud.get_by_id(role_id)
        if role is None:
            raise NotFoundError("Role not found")
        if role.is_system:
            raise ConflictError("Cannot modify a system role")

        if data.name is not None:
            role.name = data.name.strip()
        if data.permissions is not None:
            try:
                keys = validate_permission_keys(data.permissions)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            role.permissions.clear()
            await self.db.flush()
            for key in keys:
                role.permissions.append(RolePermission(role_id=role.id, key=key))

        await self.crud.commit_refresh(role)
        reloaded = await self.crud.get_by_id(role.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def delete(self, role_id: uuid.UUID) -> None:
        role = await self.crud.get_by_id(role_id)
        if role is None:
            raise NotFoundError("Role not found")
        if role.is_system:
            raise ConflictError("Cannot delete a system role")
        assigned = await self.crud.count_users_with_slug(role.slug)
        if assigned > 0:
            raise ConflictError("Cannot delete a role that is still assigned")
        await self.crud.delete_and_commit(role)

    async def _unique_slug(self, name: str) -> str:
        base = slugify_role_name(name)
        slug = base
        suffix = 2
        while await self.crud.get_by_slug(slug) is not None:
            slug = slugify_role_name(name, suffix)
            suffix += 1
        return slug

    def _to_response(self, role: Role) -> RoleResponse:
        return RoleResponse(
            id=role.id,
            slug=role.slug,
            name=role.name,
            is_system=role.is_system,
            is_owner_preset=role.is_owner_preset,
            permissions=sorted(permission.key for permission in role.permissions),
        )


class RoleSeedService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = RoleCRUD(db)

    async def seed(self) -> None:
        async with unit_of_work(self.db):
            for slug in SYSTEM_ROLE_SLUGS:
                desired = (
                    frozenset(PERMISSION_CATALOG) if slug == SLUG_OWNER else ROLE_PRESETS[slug]
                )
                role = await self.crud.get_by_slug(slug)
                if role is None:
                    await self.crud.add_and_flush(
                        Role(
                            slug=slug,
                            name=ROLE_PRESET_NAMES[slug],
                            is_system=True,
                            is_owner_preset=slug == SLUG_OWNER,
                            permissions=[RolePermission(key=key) for key in sorted(desired)],
                        )
                    )
                    continue
                role.name = ROLE_PRESET_NAMES[slug]
                role.is_system = True
                role.is_owner_preset = slug == SLUG_OWNER
                existing = {permission.key for permission in role.permissions}
                if existing == desired:
                    continue
                role.permissions.clear()
                await self.db.flush()
                for key in sorted(desired):
                    role.permissions.append(RolePermission(role_id=role.id, key=key))
