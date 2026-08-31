from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_location_service,
    require_location_mutate,
)
from app.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from app.services.locations import LocationService

locations_router = APIRouter(prefix="/api/v1/locations", tags=["locations"])


@locations_router.get("", response_model=list[LocationResponse])
async def list_locations(
    _: uuid.UUID = Depends(get_current_user_id),
    service: LocationService = Depends(get_location_service),
):
    return await service.list()


@locations_router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    body: LocationCreate,
    _: uuid.UUID = Depends(require_location_mutate),
    service: LocationService = Depends(get_location_service),
):
    return await service.create(body)


@locations_router.patch("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: uuid.UUID,
    body: LocationUpdate,
    _: uuid.UUID = Depends(require_location_mutate),
    service: LocationService = Depends(get_location_service),
):
    return await service.update(location_id, body)
