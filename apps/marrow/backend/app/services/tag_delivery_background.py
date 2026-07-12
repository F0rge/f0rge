from __future__ import annotations

import uuid

from app.services.tag_delivery import TagDeliveryService


async def deliver_tags_for_source_background(source_photo_id: int, tagger_id: uuid.UUID) -> None:
    """FastAPI BackgroundTasks entry point after analysis confirm."""
    await TagDeliveryService().deliver_for_source(source_photo_id, tagger_id)
