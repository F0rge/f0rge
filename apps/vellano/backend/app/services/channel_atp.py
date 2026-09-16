from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.channel import ChannelListingCRUD, ChannelLocationMapCRUD, SalesChannelCRUD
from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.models.channel import CHANNEL_SLUG_SHOPIFY, ChannelAtpMode, ChannelLocationMap
from app.models.location import Location, LocationType
from app.models.stocktake import StocktakeStatus
from app.schemas.channel import AtpRow, ChannelLocationMapResponse
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class ChannelAtpService:
    """Available-to-promise from location_stock. Default mode is warehouse_only (Kramerville)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.channels = SalesChannelCRUD(db)
        self.maps = ChannelLocationMapCRUD(db)
        self.locations = LocationCRUD(db)
        self.location_stock = LocationStockCRUD(db)
        self.skus = SkuCRUD(db)
        self.teams = TeamCRUD(db)
        self.settings_crud = TeamSettingsCRUD(db)

    async def mode_and_location(self) -> tuple[ChannelAtpMode, Optional[uuid.UUID]]:
        settings = await self._settings()
        mode = ChannelAtpMode(settings.channel_atp_mode)
        location_id = settings.channel_atp_location_id
        if mode == ChannelAtpMode.WAREHOUSE_ONLY and location_id is None:
            location_id = await self._first_warehouse_id()
        return mode, location_id

    async def included_location_ids(self) -> list[uuid.UUID]:
        mode, atp_location_id = await self.mode_and_location()
        if mode == ChannelAtpMode.WAREHOUSE_ONLY:
            if atp_location_id is None:
                return []
            return [atp_location_id]
        shopify = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        if shopify is None:
            return []
        ids: list[uuid.UUID] = []
        for row in await self.maps.list_for_channel(shopify.id):
            if row.include_in_atp and not row.location.is_archived:
                ids.append(row.location_id)
        return ids

    async def available_for_sku(self, sku_id: uuid.UUID) -> int:
        mode, atp_location_id = await self.mode_and_location()
        if mode == ChannelAtpMode.MAPPED:
            total = 0
            for location_id in await self.included_location_ids():
                total += await self._on_hand(sku_id, location_id)
            return total
        if mode == ChannelAtpMode.WAREHOUSE_ONLY:
            if atp_location_id is None:
                return 0
            if await self._location_locked(atp_location_id):
                return 0
            return await self._on_hand(sku_id, atp_location_id)
        total = 0
        for location_id in await self.included_location_ids():
            if await self._location_locked(location_id):
                continue
            total += await self._on_hand(sku_id, location_id)
        return total

    async def list_atp(self, our_ref: Optional[str] = None) -> list[AtpRow]:
        if our_ref:
            sku = await self.skus.get_by_our_ref(our_ref)
            if sku is None:
                raise NotFoundError("SKU not found")
            skus = [sku]
        else:
            shopify = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
            if shopify is None:
                return []
            listings = await ChannelListingCRUD(self.db).list_for_channel(shopify.id)
            skus = [row.sku for row in listings]
        rows: list[AtpRow] = []
        for sku in skus:
            loc_detail = []
            for location_id in await self.included_location_ids():
                location = await self.locations.get_by_id(location_id)
                if location is None:
                    continue
                loc_detail.append(
                    {
                        "location_id": str(location.id),
                        "location_name": location.name,
                        "on_hand": await self._on_hand(sku.id, location.id),
                    }
                )
            rows.append(
                AtpRow(
                    sku_id=sku.id,
                    our_ref=sku.our_ref,
                    available=await self.available_for_sku(sku.id),
                    locations=loc_detail,
                )
            )
        return rows

    async def resolve_sale_location(self, shopify_location_gid: Optional[str] = None) -> Location:
        mode, atp_location_id = await self.mode_and_location()
        if mode == ChannelAtpMode.MAPPED and shopify_location_gid:
            shopify = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
            if shopify is not None:
                mapped = await self.maps.get_by_shopify_gid(shopify.id, shopify_location_gid)
                if mapped is not None and not mapped.location.is_archived:
                    return mapped.location
        if atp_location_id is not None:
            location = await self.locations.get_by_id(atp_location_id)
            if location is not None and not location.is_archived:
                return location
        warehouse_id = await self._first_warehouse_id()
        if warehouse_id is None:
            raise ValidationError("No warehouse location configured for channel ATP")
        location = await self.locations.get_by_id(warehouse_id)
        assert location is not None
        return location

    async def update_settings(
        self,
        atp_mode: Optional[ChannelAtpMode],
        atp_location_id: Optional[uuid.UUID],
        maps: Optional[list],
        atp_location_id_set: bool,
    ) -> None:
        settings = await self._settings()
        async with unit_of_work(self.db):
            if atp_mode is not None:
                settings.channel_atp_mode = atp_mode.value
            if atp_location_id_set:
                if atp_location_id is not None:
                    location = await self.locations.get_by_id(atp_location_id)
                    if location is None or location.is_archived:
                        raise ValidationError("Unknown or archived ATP location")
                    effective_mode = (
                        atp_mode
                        if atp_mode is not None
                        else ChannelAtpMode(settings.channel_atp_mode)
                    )
                    if (
                        effective_mode == ChannelAtpMode.WAREHOUSE_ONLY
                        and location.type != LocationType.WAREHOUSE
                    ):
                        raise ValidationError("warehouse_only ATP location must be a warehouse")
                settings.channel_atp_location_id = atp_location_id
            if maps is not None:
                shopify = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
                if shopify is None:
                    raise NotFoundError("Shopify channel not seeded")
                await self.maps.delete_for_channel(shopify.id)
                await self.db.flush()
                for item in maps:
                    location = await self.locations.get_by_id(item.location_id)
                    if location is None or location.is_archived:
                        raise ValidationError("Unknown or archived location in ATP map")
                    await self.maps.add_and_flush(
                        ChannelLocationMap(
                            channel_id=shopify.id,
                            location_id=item.location_id,
                            shopify_location_gid=item.shopify_location_gid,
                            include_in_atp=item.include_in_atp,
                        )
                    )

    async def map_responses(self) -> list[ChannelLocationMapResponse]:
        shopify = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
        if shopify is None:
            return []
        return [
            ChannelLocationMapResponse(
                id=row.id,
                location_id=row.location_id,
                location_name=row.location.name,
                location_type=row.location.type.value,
                shopify_location_gid=row.shopify_location_gid,
                include_in_atp=row.include_in_atp,
            )
            for row in await self.maps.list_for_channel(shopify.id)
        ]

    async def _on_hand(self, sku_id: uuid.UUID, location_id: uuid.UUID) -> int:
        row = await self.location_stock.get_by_sku_and_location(sku_id, location_id)
        return row.on_hand if row is not None else 0

    async def _location_locked(self, location_id: uuid.UUID) -> bool:
        from app.crud.stocktake import StocktakeCRUD

        row = await StocktakeCRUD(self.db).get_in_progress_for_location(location_id)
        return row is not None and row.status == StocktakeStatus.IN_PROGRESS

    async def _first_warehouse_id(self) -> Optional[uuid.UUID]:
        for location in await self.locations.list_all():
            if location.type == LocationType.WAREHOUSE and not location.is_archived:
                return location.id
        return None

    async def _settings(self):
        team = await self.teams.get_first()
        if team is None:
            raise NotFoundError("Team not found")
        return await self.settings_crud.get_or_create_for_team(team.id)
