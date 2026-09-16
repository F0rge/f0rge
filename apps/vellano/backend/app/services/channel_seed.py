from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.channel import ChannelLocationMapCRUD, SalesChannelCRUD
from app.crud.location import LocationCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.models.channel import (
    CHANNEL_SLUG_EMAIL,
    CHANNEL_SLUG_MANUAL,
    CHANNEL_SLUG_SHOPIFY,
    ChannelLocationMap,
    SalesChannel,
)
from app.models.location import LocationType
from f0rge_db.crud import unit_of_work

_SEED_CHANNELS: tuple[tuple[str, str], ...] = (
    (CHANNEL_SLUG_SHOPIFY, "Shopify"),
    (CHANNEL_SLUG_EMAIL, "Email"),
    (CHANNEL_SLUG_MANUAL, "Manual"),
)


class ChannelSeedService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.channels = SalesChannelCRUD(db)
        self.maps = ChannelLocationMapCRUD(db)
        self.locations = LocationCRUD(db)
        self.teams = TeamCRUD(db)
        self.settings = TeamSettingsCRUD(db)

    async def ensure(self) -> None:
        async with unit_of_work(self.db):
            for slug, name in _SEED_CHANNELS:
                if await self.channels.get_by_slug(slug) is None:
                    await self.channels.add_and_flush(
                        SalesChannel(slug=slug, name=name, enabled=True)
                    )

            shopify = await self.channels.get_by_slug(CHANNEL_SLUG_SHOPIFY)
            if shopify is None:
                return
            existing = {row.location_id for row in await self.maps.list_for_channel(shopify.id)}
            for location in await self.locations.list_all():
                if location.id in existing or location.is_archived:
                    continue
                await self.maps.add_and_flush(
                    ChannelLocationMap(
                        channel_id=shopify.id,
                        location_id=location.id,
                        include_in_atp=location.type == LocationType.WAREHOUSE,
                    )
                )

        team = await self.teams.get_first()
        if team is None:
            return
        settings = await self.settings.get_or_create_for_team(team.id)
        if settings.channel_atp_location_id is None:
            async with unit_of_work(self.db):
                for location in await self.locations.list_all():
                    if location.type == LocationType.WAREHOUSE and not location.is_archived:
                        settings.channel_atp_location_id = location.id
                        break
