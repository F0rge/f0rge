from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.channel import (
    ChannelApiKey,
    ChannelListing,
    ChannelLocationMap,
    ChannelOrder,
    ChannelOrderStatus,
    ChannelOutbox,
    ChannelOutboxKind,
    ChannelOutboxStatus,
    SalesChannel,
)
from f0rge_db.crud import BaseCRUD


class SalesChannelCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_slug(self, slug: str) -> Optional[SalesChannel]:
        return (
            await self.db.execute(select(SalesChannel).where(SalesChannel.slug == slug))
        ).scalar_one_or_none()

    async def list_all(self) -> list[SalesChannel]:
        result = await self.db.execute(select(SalesChannel).order_by(SalesChannel.slug))
        return list(result.scalars().all())


class ChannelLocationMapCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list_for_channel(self, channel_id: uuid.UUID) -> list[ChannelLocationMap]:
        result = await self.db.execute(
            select(ChannelLocationMap)
            .options(selectinload(ChannelLocationMap.location))
            .where(ChannelLocationMap.channel_id == channel_id)
        )
        return list(result.scalars().all())

    async def get_by_location(
        self, channel_id: uuid.UUID, location_id: uuid.UUID
    ) -> Optional[ChannelLocationMap]:
        return (
            await self.db.execute(
                select(ChannelLocationMap).where(
                    ChannelLocationMap.channel_id == channel_id,
                    ChannelLocationMap.location_id == location_id,
                )
            )
        ).scalar_one_or_none()

    async def get_by_shopify_gid(
        self, channel_id: uuid.UUID, gid: str
    ) -> Optional[ChannelLocationMap]:
        return (
            await self.db.execute(
                select(ChannelLocationMap)
                .options(selectinload(ChannelLocationMap.location))
                .where(
                    ChannelLocationMap.channel_id == channel_id,
                    ChannelLocationMap.shopify_location_gid == gid,
                )
            )
        ).scalar_one_or_none()

    async def delete_for_channel(self, channel_id: uuid.UUID) -> None:
        rows = await self.list_for_channel(channel_id)
        for row in rows:
            await self.db.delete(row)


class ChannelListingCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_sku(
        self, channel_id: uuid.UUID, sku_id: uuid.UUID
    ) -> Optional[ChannelListing]:
        return (
            await self.db.execute(
                select(ChannelListing).where(
                    ChannelListing.channel_id == channel_id,
                    ChannelListing.sku_id == sku_id,
                )
            )
        ).scalar_one_or_none()

    async def get_by_variant(
        self, channel_id: uuid.UUID, variant_id: str
    ) -> Optional[ChannelListing]:
        return (
            await self.db.execute(
                select(ChannelListing)
                .options(selectinload(ChannelListing.sku))
                .where(
                    ChannelListing.channel_id == channel_id,
                    ChannelListing.external_variant_id == variant_id,
                )
            )
        ).scalar_one_or_none()

    async def get_by_external_sku(
        self, channel_id: uuid.UUID, external_sku: str
    ) -> Optional[ChannelListing]:
        return (
            await self.db.execute(
                select(ChannelListing)
                .options(selectinload(ChannelListing.sku))
                .where(
                    ChannelListing.channel_id == channel_id,
                    ChannelListing.external_sku == external_sku,
                )
            )
        ).scalar_one_or_none()

    async def list_for_channel(self, channel_id: uuid.UUID) -> list[ChannelListing]:
        result = await self.db.execute(
            select(ChannelListing)
            .options(selectinload(ChannelListing.sku))
            .where(ChannelListing.channel_id == channel_id)
            .order_by(ChannelListing.created_at)
        )
        return list(result.scalars().all())

    async def count_for_channel(self, channel_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(ChannelListing)
            .where(ChannelListing.channel_id == channel_id)
        )
        return int(result.scalar_one())


class ChannelApiKeyCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_hash(self, key_hash: str) -> Optional[ChannelApiKey]:
        return (
            await self.db.execute(select(ChannelApiKey).where(ChannelApiKey.key_hash == key_hash))
        ).scalar_one_or_none()

    async def list_all(self) -> list[ChannelApiKey]:
        result = await self.db.execute(
            select(ChannelApiKey).order_by(ChannelApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, key_id: uuid.UUID) -> Optional[ChannelApiKey]:
        return (
            await self.db.execute(select(ChannelApiKey).where(ChannelApiKey.id == key_id))
        ).scalar_one_or_none()


class ChannelOrderCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, order_id: uuid.UUID) -> Optional[ChannelOrder]:
        return (
            await self.db.execute(
                select(ChannelOrder)
                .options(
                    selectinload(ChannelOrder.channel),
                    selectinload(ChannelOrder.invoice),
                    selectinload(ChannelOrder.customer),
                )
                .where(ChannelOrder.id == order_id)
            )
        ).scalar_one_or_none()

    async def lock_by_id(self, order_id: uuid.UUID) -> Optional[ChannelOrder]:
        locked = (
            await self.db.execute(
                select(ChannelOrder.id).where(ChannelOrder.id == order_id).with_for_update()
            )
        ).scalar_one_or_none()
        if locked is None:
            return None
        return await self.get_by_id(order_id)

    async def get_by_external(
        self, channel_id: uuid.UUID, external_order_id: str
    ) -> Optional[ChannelOrder]:
        return (
            await self.db.execute(
                select(ChannelOrder)
                .options(selectinload(ChannelOrder.channel), selectinload(ChannelOrder.invoice))
                .where(
                    ChannelOrder.channel_id == channel_id,
                    ChannelOrder.external_order_id == external_order_id,
                )
            )
        ).scalar_one_or_none()

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
        status: Optional[ChannelOrderStatus] = None,
        channel_id: Optional[uuid.UUID] = None,
    ) -> tuple[list[ChannelOrder], int]:
        filters = []
        if status is not None:
            filters.append(ChannelOrder.status == status)
        if channel_id is not None:
            filters.append(ChannelOrder.channel_id == channel_id)
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    ChannelOrder.external_order_id.ilike(pattern),
                    ChannelOrder.email.ilike(pattern),
                )
            )
        count_stmt = select(func.count(ChannelOrder.id))
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0
        stmt = (
            select(ChannelOrder)
            .options(selectinload(ChannelOrder.channel), selectinload(ChannelOrder.invoice))
            .order_by(ChannelOrder.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if filters:
            stmt = stmt.where(*filters)
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), int(total)


class ChannelOutboxCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_pending_inventory(self, sku_id: uuid.UUID) -> Optional[ChannelOutbox]:
        return (
            await self.db.execute(
                select(ChannelOutbox).where(
                    ChannelOutbox.sku_id == sku_id,
                    ChannelOutbox.kind == ChannelOutboxKind.INVENTORY_PUSH,
                    ChannelOutbox.status == ChannelOutboxStatus.PENDING,
                )
            )
        ).scalar_one_or_none()

    async def get_open_process_order(self, channel_order_id: uuid.UUID) -> Optional[ChannelOutbox]:
        return (
            await self.db.execute(
                select(ChannelOutbox)
                .where(
                    ChannelOutbox.channel_order_id == channel_order_id,
                    ChannelOutbox.kind == ChannelOutboxKind.PROCESS_ORDER,
                    ChannelOutbox.status.in_(
                        (ChannelOutboxStatus.PENDING, ChannelOutboxStatus.PROCESSING)
                    ),
                )
                .limit(1)
            )
        ).scalar_one_or_none()

    async def count_failed(self) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(ChannelOutbox)
            .where(ChannelOutbox.status == ChannelOutboxStatus.FAILED)
        )
        return int(result.scalar_one())

    async def list_recent(self, limit: int = 50) -> list[ChannelOutbox]:
        result = await self.db.execute(
            select(ChannelOutbox).order_by(ChannelOutbox.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
